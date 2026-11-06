"""Uji FPGA fisik lewat UART, tanpa MQTT/sensor/WiFi.

  ml/.venv/bin/python edge/bridge/test_fpga_uart.py --check-vectors
  ml/.venv/bin/python edge/bridge/test_fpga_uart.py --port /dev/ttyUSB2 --samples 20

Port wajib dipilih eksplisit sesudah kabel dan level logika diverifikasi.
--check-vectors hanya memeriksa data acuan; bukan uji hardware.
"""
import argparse
import csv
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
from golden_model import GoldenModelINT8


def crc8(data):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 7) & 255 if c & 128 else (c << 1) & 255
    return c


def response(ser, timeout):
    end = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < end:
        buf.extend(ser.read(1))
        while len(buf) >= 2 and buf[:2] != b"\x55\xaa":
            del buf[0]
        if len(buf) == 7:
            return bytes(buf)
    raise TimeoutError("FPGA tidak mengirim frame lengkap")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--port", help="Port adaptor UART yang benar, bukan otomatis port JTAG")
    mode.add_argument("--check-vectors", action="store_true", help="Cek acuan secara offline, tanpa mengakses papan")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--timeout", type=float, default=0.1)
    ap.add_argument("--report", type=Path, help="Simpan hasil hardware ke JSON")
    args = ap.parse_args()
    if args.samples <= 0 or args.timeout <= 0 or args.baud <= 0:
        ap.error("samples, timeout, dan baud harus positif")
    source = ROOT / "ml/forecast/model/export/test_vectors.csv"
    with source.open() as f:
        rows = list(csv.DictReader(f))
    model = ROOT / "ml/forecast/model/mlp_int8.json"
    gm = GoldenModelINT8(model_path=str(model))
    # Verifikasi seluruh acuan sebelum membuka port serial.
    for row in rows:
        out, h1, h2 = gm.forward([int(row[f"x{k}"]) for k in range(16)])
        if out != int(row["out_q"]) or h1 != [int(row[f"h1_{k}"]) for k in range(32)] or h2 != [int(row[f"h2_{k}"]) for k in range(16)]:
            raise ValueError(f"Bobot dan test vector berbeda pada idx={row['idx']}")
    if args.check_vectors:
        print(f"LULUS acuan offline: {len(rows)} vektor cocok dengan model. Papan TIDAK diuji.")
        return 0
    if args.samples > len(rows):
        ap.error(f"Tersedia {len(rows)} sampel; --samples tidak boleh lebih besar")
    import serial
    selected = random.Random(7).sample(rows, args.samples)
    print(f"UJI HARDWARE port={args.port}, baud={args.baud}, sampel={len(selected)}", flush=True)
    results = []
    with serial.Serial(args.port, args.baud, timeout=min(args.timeout, 0.01), write_timeout=1) as ser:
        time.sleep(0.1)
        for row in selected:
            item = {"idx": int(row["idx"]), "expected_q": int(row["out_q"]), "ok": False}
            try:
                payload = bytes(int(row[f"x{k}"]) & 255 for k in range(16))
                ser.reset_input_buffer()
                start = time.monotonic()
                frame = b"\xaa\x55" + payload + bytes([crc8(payload)])
                if ser.write(frame) != len(frame):
                    raise IOError("Paket kirim tidak lengkap")
                ser.flush()
                rx = response(ser, args.timeout)
                item["roundtrip_us"] = round((time.monotonic() - start) * 1e6, 1)
                item["rx_hex"] = rx.hex()
                if crc8(rx[2:6]) != rx[6]:
                    raise ValueError("CRC balasan salah")
                item.update(status=rx[2], actual_q=rx[3], cycles=int.from_bytes(rx[4:6], "big"))
                if item["status"] != 0:
                    raise ValueError(f"Status FPGA 0x{item['status']:02x}")
                if item["actual_q"] != item["expected_q"]:
                    raise ValueError("Prediksi berbeda dari golden model")
                if item["cycles"] != 309:
                    raise ValueError("Jumlah siklus berbeda dari 309")
                item["ok"] = True
            except (TimeoutError, ValueError, OSError, serial.SerialException) as exc:
                item["error"] = str(exc)
            results.append(item)
            print(json.dumps(item), flush=True)
            time.sleep(0.01)
    passed = sum(r["ok"] for r in results)
    report = {"kind": "hardware UART", "port": args.port, "baud": args.baud,
              "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "passed": passed, "total": len(results), "results": results}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{'LULUS' if passed == len(results) else 'GAGAL'} HARDWARE: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
