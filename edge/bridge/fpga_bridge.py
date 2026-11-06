"""Jembatan demo: data live turbin -> akselerator FPGA Tang Nano 4K -> dashboard.

Sampai ESP32 dirakit, laptop memegang peran ESP32 untuk FPGA:
  1. dengar WEC/prediksi (mesin ML Node-RED, tiap menit) yang memuat xq = 16 byte fitur INT8 dan out_q (hasil CPU)
  2. kirim paket ke FPGA lewat USB-TTL (921600 8N1; TXD -> pin 44, RXD <- pin 46, GND):
     [0xAA, 0x55, 16 fitur INT8, CRC8] -> [0x55, 0xAA, status, prediksi, siklus MSB, LSB, CRC8]
     (hw/rtl/top_soc.v di branch feature/fpga; CRC-8 polinomial 0x07, awal 0x00)
  3. bandingkan dengan out_q CPU, lalu kirim WEC/fpga -> dashboard /dashboard/hackathon menampilkan "Chip"

Mode --sim memakai golden model (ml/golden_model.py) sebagai pengganti papan, dan dashboard menandainya "simulasi".

Pemakaian:
  ml/.venv/bin/python edge/bridge/fpga_bridge.py --port /dev/ttyUSB0      # papan sungguhan
  ml/.venv/bin/python edge/bridge/fpga_bridge.py --sim                    # tanpa papan
  tambah --sekali untuk satu kali kirim lalu keluar (cek sambungan)
"""

import os
import argparse
import json
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
from golden_model import GoldenModelINT8  # noqa: E402

BROKER, PORT, USER, PASS = "citaitb.com", 1883, "cita", os.environ.get("MQTT_PASS", "")
MODEL = ROOT / "ml" / "forecast" / "model" / "mlp_int8.json"


def crc8(data):
    c = 0
    for x in data:
        c ^= x
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


class Fpga:
    def __init__(self, port, baud=921600, timeout=0.05):
        import serial
        self.port = port
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.1)
        self.ser.reset_input_buffer()

    def infer(self, xq):
        payload = bytes(v & 0xFF for v in xq)
        frame = b"\xAA\x55" + payload + bytes([crc8(payload)])
        for _ in range(2):                         # coba ulang sekali bila CRC/status salah
            self.ser.reset_input_buffer()
            t0 = time.perf_counter()
            self.ser.write(frame)
            rx = self.ser.read(7)
            us = (time.perf_counter() - t0) * 1e6
            if len(rx) == 7 and rx[0] == 0x55 and rx[1] == 0xAA and crc8(rx[2:6]) == rx[6]:
                if rx[2] == 0x00:
                    return rx[3], (rx[4] << 8) | rx[5], us
                print(time.strftime("%H:%M:%S"), f"FPGA status 0x{rx[2]:02X} (E1 = CRC salah, E2 = timeout)", flush=True)
        return None


class Sim:
    port = "simulasi"

    def __init__(self):
        self.gm = GoldenModelINT8(model_path=str(MODEL))

    def infer(self, xq):
        t0 = time.perf_counter()
        out = self.gm.forward(list(xq))[0]
        return out, 309, (time.perf_counter() - t0) * 1e6     # 309 siklus = hasil iverilog RTL (hw/sim/run_regression.py)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--port", help="port USB-TTL, mis. /dev/ttyUSB0")
    g.add_argument("--sim", action="store_true", help="pakai golden model, tanpa papan")
    ap.add_argument("--baud", type=int, default=921600, help="harus sama dengan BAUDRATE di top_soc.v")
    ap.add_argument("--sekali", action="store_true", help="proses satu prediksi lalu keluar")
    args = ap.parse_args()
    dev = Sim() if args.sim else Fpga(args.port, args.baud)
    gm = GoldenModelINT8(model_path=str(MODEL))
    done = threading.Event()
    seen = set()

    def on_message(c, u, m):
        try:
            d = json.loads(m.payload)
        except ValueError:
            return
        xq, t = d.get("xq"), d.get("t")
        if not isinstance(xq, list) or len(xq) != 16 or t in seen:
            return
        seen.add(t)
        cpu = d.get("out_q")
        if cpu is None:
            cpu = gm.forward(xq)[0]
        r = dev.infer(xq)
        if r is None:
            print(time.strftime("%H:%M:%S"), "FPGA tidak menjawab dengan paket valid", flush=True)
            return
        out, cyc, us = r
        msg = {"t": t, "out_q_fpga": out, "out_q_cpu": cpu, "cocok": out == cpu, "cycles": cyc, "us": round(us, 1),
               "watt": round(out * gm.output_scale, 2), "sumber": "simulasi" if args.sim else "tang-nano-4k", "port": dev.port}
        c.publish("WEC/fpga", json.dumps(msg), retain=True)
        print(time.strftime("%H:%M:%S"), json.dumps(msg), flush=True)
        if args.sekali:
            done.set()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wec-fpga-bridge-{int(time.time())}")
    c.username_pw_set(USER, PASS)
    c.on_message = on_message
    c.on_connect = lambda c, u, f, rc, p=None: c.subscribe("WEC/prediksi")
    c.connect(BROKER, PORT, 30)
    c.loop_start()
    print("menunggu WEC/prediksi ... (Ctrl+C untuk berhenti)", flush=True)
    try:
        while not done.wait(1):
            pass
    except KeyboardInterrupt:
        pass
    time.sleep(0.5)
    c.loop_stop()


if __name__ == "__main__":
    main()
