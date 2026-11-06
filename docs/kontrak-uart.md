# Kontrak UART: ESP32 ↔ FPGA

Status: bagian **"Yang berjalan sekarang"** mengikuti RTL di branch `feature/integrasi` (`hw/rtl/top_soc.v`), dan firmware `edge/esp32/src/fpga_link.cpp` memakai format ini. Bagian **"Usulan"** di bawahnya belum diterapkan. Perubahan file ini wajib disetujui pemilik `edge/` dan `hw/`.

## Yang berjalan sekarang (RTL `feature/fpga` 21 Okt 2026, commit 81b1607)
**Catatan perakitan 21 Okt:** bank 1 (pin 44/46) diukur 3,3 V di papan; ESP32-S3 tersambung langsung dan uji HIL lulus
(5.373/5.373 identik, `demo/hil-2026-10-21.txt`). Lihat [`demo/perakitan-hardware.md`](demo/perakitan-hardware.md).

| Arah | Isi |
|---|---|
| ESP32 → FPGA (19 byte) | `0xAA 0x55`, 16 byte fitur INT8 bertanda (urutan `docs/kontrak-kuantisasi.md`), CRC-8 atas 16 byte fitur |
| FPGA → ESP32 (7 byte) | `0x55 0xAA`, status (`0x00` OK, `0xE1` CRC salah, `0xE2` timeout), prediksi INT8 (0–127), siklus MSB, siklus LSB, CRC-8 atas 4 byte status..siklus LSB |
| CRC-8 | polinomial `0x07` (x⁸+x²+x+1), nilai awal `0x00` (`hw/sim/crc8_util.py`) |
| Fisik | **921600** 8N1, 3,3 V. FPGA rx = pin 44, tx = pin 46, `rst_n` = pin 14 (aktif rendah) |

- FPGA membuang paket yang CRC-nya salah dan membalas status `0xE1`. Watchdog sekitar 10 ms mengembalikan penerima ke kondisi menunggu sinkron kalau paket terputus.
- ESP32 (`edge/esp32/src/fpga_link.cpp`) dan jembatan laptop (`edge/bridge/fpga_bridge.py`): batas waktu 20 ms, byte sebelum `0x55 0xAA` dibuang, coba ulang sekali, lalu memakai cadangan CPU bit-exact (`mlp_int8.h`). Uji: `edge/esp32/test/run_native.py` (300 paket kirim + 300 balasan, termasuk CRC rusak dan status E1/E2: 0 beda).
- Usulan dua model (`docs/usulan-rtl-dua-model.md`): `model_id` disisipkan setelah `0xAA 0x55` dan ikut dihitung CRC. Di firmware sudah siap lewat `FPGA_DUAL_MODEL 1`.
- Format lama (16 byte mentah → 3 byte, 115200) tidak lagi dipakai.

---

# Usulan awal (belum diterapkan)

## Sambungan
- UART, 115200 bps, 8N1, logika 3,3 V
- Kabel: TX ESP32 → RX FPGA, RX ESP32 ← TX FPGA, ground bersama
- Pin yang dipakai: TBD (tergantung papan)

## Susunan paket
| Bagian | Ukuran | Isi |
|---|---|---|
| Penanda awal | 1 byte | `0xAA` (ESP32 → FPGA) atau `0x55` (FPGA → ESP32) |
| Jenis | 1 byte | 1 = fitur, 2 = hasil, 3 = status/galat |
| Panjang | 1 byte | Jumlah byte isi |
| Isi | N byte | Lihat di bawah |
| CRC-8 | 1 byte | Dihitung dari jenis, panjang, dan isi. Polinomial: TBD |

## Isi paket fitur (jenis 1)
- N fitur, masing-masing 1 byte INT8, urutan sesuai `docs/kontrak-kuantisasi.md`
- N: TBD (usulan 16)

## Isi paket hasil (jenis 2)
- 1 byte INT8: prediksi daya 1 jam ke depan (skala di `docs/kontrak-kuantisasi.md`)
- 4 byte: jumlah siklus yang dipakai untuk menghitung (urutan byte: TBD)

## Urutan
1. ESP32 mengirim paket fitur (usulan: tiap 1 menit).
2. FPGA memeriksa CRC, menghitung, lalu mengirim paket hasil.
3. Kalau CRC salah, FPGA mengirim paket jenis 3.
4. Kalau tidak ada balasan dalam batas waktu (TBD), ESP32 memakai model cadangannya.
