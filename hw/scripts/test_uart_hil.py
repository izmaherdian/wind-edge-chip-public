#!/usr/bin/env python3
"""
Hardware-in-the-Loop (HIL) UART Test & Debug Script
untuk Akselerator FPGA WindEdgeChip pada Sipeed Tang Nano 4K

Mendukung Protokol Berbingkai Paket (Packet Framing) & CRC-8:
- Host -> FPGA (19 Byte): [0xAA, 0x55, 16 Byte Fitur INT8, CRC8 Payload]
- FPGA -> Host (7 Byte):  [0x55, 0xAA, Status, Prediksi INT8, Cycle MSB, Cycle LSB, CRC8]
- Kecepatan Baudrate: 921600 bps (Default High-Speed) atau 115200 bps (Legacy).
"""

import sys
import os
import time
import argparse

# Setup path ke modul ml/ dan hw/sim/
base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
sys.path.append(os.path.join(project_root, "ml"))
sys.path.append(os.path.join(project_root, "hw", "sim"))

try:
    from golden_model import GoldenModelINT8
except ImportError:
    print("[ERROR] Modul golden_model.py tidak ditemukan di folder ml/.")
    sys.exit(1)

try:
    from crc8_util import crc8
except ImportError:
    # Fallback implementasi CRC-8 CCITT (0x07)
    def crc8(data: bytes, init: int = 0x00, poly: int = 0x07) -> int:
        c = init
        for b in data:
            c ^= b
            for _ in range(8):
                if c & 0x80:
                    c = ((c << 1) ^ poly) & 0xFF
                else:
                    c = (c << 1) & 0xFF
        return c

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] Library 'pyserial' belum terinstal.")
    print("        Silakan jalankan: pip install pyserial")
    sys.exit(1)


def auto_detect_port():
    """Mendeteksi COM port perangkat USB FTDI / Tang Nano 4K secara otomatis."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "ftdi" in desc or "0403:6010" in hwid or "usb serial port" in desc or "tang" in desc:
            return p.device
    if ports:
        return ports[0].device
    return "COM13"


def parse_signed_int8(val_byte):
    """Mengonversi nilai byte tak bertanda (0..255) ke signed 8-bit integer (-128..127)."""
    if val_byte > 127:
        return val_byte - 256
    return val_byte


def run_hil_test(port, baudrate, num_samples=5):
    print("=" * 80)
    print("   HARDWARE-IN-THE-LOOP (HIL) TEST — TANG NANO 4K FPGA ACCELERATOR")
    print("   Protokol: Bingkai Paket [0xAA 0x55] + Hardware CRC-8 (Poly 0x07)")
    print("=" * 80)
    print(f" Port Serial   : {port}")
    print(f" Baudrate      : {baudrate:,} bps (8-N-1)")
    print(f" Target Board  : Sipeed Tang Nano 4K (GW1NSR-LV4C)")
    print(f" Clock Fisik   : 27 MHz (1 cycle = ~37.037 ns)")
    print("=" * 80)

    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=1.0)
    except Exception as e:
        print(f"\n[GAGAL] Tidak dapat membuka port serial {port}: {e}")
        print("Tip: Pastikan board terhubung via USB dan port tidak sedang dibuka software lain.")
        return False

    gm = GoldenModelINT8()

    # Kumpulan skenario data uji realistis turbin angin (16 fitur INT8 ter-normalisasi)
    test_vectors = [
        # Skenario 1: Angin Sedang Stabil (Daya Turbin Normal)
        [1, 2, -1, 0, 1, -1, 2, 0, -1, 1, 0, 1, -1, 0, 1, 2],
        # Skenario 2: Kondisi Angin Tenang / Idle (Baseline bias turbin)
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        # Skenario 3: Angin Lemah / Rendah (Daya di bawah rata-rata)
        [-3, -2, -3, -2, -4, -3, -2, -3, -2, -3, -4, -2, -3, -2, -3, -4],
        # Skenario 4: Hembusan Angin Meningkat (Wind Gust / Akselerasi Daya)
        [2, 3, 2, 4, 3, 4, 5, 4, 5, 6, 5, 6, 7, 6, 7, 8],
        # Skenario 5: Kasus Ekstrem / Uji Stres (Validasi Batas Proteksi Saturasi 127)
        [127, -128, 64, -64, 32, -32, 16, -16, 8, -8, 4, -4, 2, -2, 1, -1],
    ]

    while len(test_vectors) < num_samples:
        import random
        rnd_vec = [random.randint(-50, 50) for _ in range(16)]
        test_vectors.append(rnd_vec)
    test_vectors = test_vectors[:num_samples]

    passed_count = 0
    total_cycles = []

    print(f"\nMenjalankan pengujian {len(test_vectors)} paket inferensi ke FPGA hardware...\n")
    print(f"{'No':<4} | {'Expected':<10} | {'FPGA HW':<10} | {'Status':<10} | {'Cycles':<8} | {'Latency':<10} | {'CRC8':<8} | {'Hasil'}")
    print("-" * 84)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    for idx, features in enumerate(test_vectors, 1):
        expected_pred, _, _ = gm.forward(features)

        # 1. Format payload 16 byte
        payload = bytes([(x + 256) % 256 for x in features])
        tx_crc = crc8(payload)

        # 2. Bingkai 19-byte [0xAA, 0x55, 16B payload, 1B CRC8]
        tx_frame = bytes([0xAA, 0x55]) + payload + bytes([tx_crc])

        # 3. Transmisi ke FPGA
        ser.write(tx_frame)
        ser.flush()

        # 4. Terima frame balasan 7-byte [0x55, 0xAA, STATUS, PRED, CYC_H, CYC_L, CRC8]
        rx_data = ser.read(7)

        if len(rx_data) < 7:
            print(f"{idx:<4} | {expected_pred:<10} | {'TIMEOUT':<10} | {'TIMEOUT':<10} | {'-':<8} | {'-':<10} | {'-':<8} | GAGAL (Timeout)")
            continue

        if rx_data[0] != 0x55 or rx_data[1] != 0xAA:
            print(f"{idx:<4} | {expected_pred:<10} | {'BAD_SYNC':<10} | {'SYNC_ERR':<10} | {'-':<8} | {'-':<10} | {'-':<8} | GAGAL (Header Salah)")
            continue

        status_code = rx_data[2]
        raw_pred = rx_data[3]
        actual_pred = parse_signed_int8(raw_pred)
        cycle_msb = rx_data[4]
        cycle_lsb = rx_data[5]
        cycles = (cycle_msb << 8) | cycle_lsb
        total_cycles.append(cycles)
        rx_crc = rx_data[6]

        expected_rx_crc = crc8(rx_data[2:6])
        crc_valid = (rx_crc == expected_rx_crc)

        latency_us = (cycles / 27000000.0) * 1e6

        status_name = "OK (0x00)" if status_code == 0x00 else f"ERR(0x{status_code:02X})"
        crc_str = "MATCH" if crc_valid else "CORRUPT"

        is_pass = (status_code == 0x00 and actual_pred == expected_pred and crc_valid)
        if is_pass:
            result_str = "LULUS (MATCH)"
            passed_count += 1
        else:
            result_str = "MISMATCH"

        print(f"{idx:<4} | {expected_pred:<10} | {actual_pred:<10} | {status_name:<10} | {cycles:<8} | {latency_us:>6.2f} us | {crc_str:<8} | {result_str}")
        time.sleep(0.005)

    ser.close()

    print("-" * 84)
    print(f"Hasil Pengujian : {passed_count}/{len(test_vectors)} Paket Lolos Verifikasi Framing & Hardware")
    if total_cycles:
        avg_cycles = sum(total_cycles) / len(total_cycles)
        avg_latency = (avg_cycles / 27000000.0) * 1e6
        print(f"Rata-rata Siklus: {avg_cycles:.1f} clock ({avg_latency:.2f} us)")
    print("=" * 84)

    return passed_count == len(test_vectors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tang Nano 4K Framed UART HIL Debugger")
    parser.add_argument("--port", type=str, default=None, help="COM port (contoh: COM13 atau /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=921600, help="Baudrate serial UART (default: 921600)")
    parser.add_argument("--samples", type=int, default=5, help="Jumlah sampel uji inferensi (default: 5)")
    args = parser.parse_args()

    port = args.port or auto_detect_port()
    run_hil_test(port=port, baudrate=args.baud, num_samples=args.samples)
