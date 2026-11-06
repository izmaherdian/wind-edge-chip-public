# Usulan RTL: dua model di akselerator MAC4 (prediksi daya + status turbin)

Status: **usulan untuk Alif** (20 Okt 2026). Belum diterapkan di `hw/rtl/`.

## Latar
Akselerator sekarang menjalankan satu MLP 16-32-16-1 INT8 (fitur 2, prediksi daya 1 jam). Fitur 1 (status turbin) sekarang punya model INT8 dengan **topologi dan aritmetika yang sama**: MLP "kurva daya wajar", `ml/status/model/powercurve_int8.json`.

Bobot fitur 1 sudah diuji di RTL Verilog yang ada, dengan cara mengganti `weights32.hex`/`bias.hex`: 600 vektor nyata, 2.000 vektor acak, dan 30 vektor lewat UART, semuanya LULUS (0 beda, 309 siklus). Jadi datapath tidak perlu diubah. Yang perlu ditambah hanya cara **memilih set bobot**.

## Perubahan yang diusulkan
| Bagian | Sekarang | Usulan |
|---|---|---|
| `weights_rom.v` | 260 word × 32 bit (1 model) | 520 word (2 model). Masih 1–2 BSRAM; Tang Nano 4K punya 10 dan baru terpakai 2 |
| Memori bias | 49 × INT32 | 98 × INT32 |
| Alamat | `weight_addr`, `bias_addr` | `+ model_id × 260` dan `+ model_id × 49` (offset konstan) |
| Paket UART masuk | 16 byte fitur | **17 byte**: byte 0 = `model_id` (0 = prediksi daya, 1 = kurva daya), lalu 16 byte fitur |
| Paket UART keluar | 3 byte | tetap 3 byte (prediksi INT8 + siklus 16-bit) |
| Siklus | 309 | tetap 309 per model |

Alternatif tanpa mengubah format paket: `model_id` diambil dari pin GPIO yang dikendalikan ESP32. Lebih sederhana, tapi butuh satu kabel tambahan.

## Alur per menit di ESP32
1. Susun 16 fitur prediksi, kirim `[0x00, f0..f15]`, lalu terima prediksi daya 1 jam.
2. Susun 16 fitur kurva daya, kirim `[0x01, g0..g15]`, lalu terima daya wajar. Setelah itu hitung rasio rata-rata 30 menit (aktual / wajar):
   - di bawah 0,42 → "Di bawah normal";
   - di atas 1,463 → "Di atas normal (cek sensor)";
   - selain itu "Normal".

   Ambang ini ada di `powercurve_int8.json`.
3. Total waktu hitung FPGA kurang dari 25 µs per menit. Kalau FPGA tidak membalas, ESP32 menghitung sendiri dengan `mlp_int8.h` dan `mlp_powercurve_int8.h` (bit-exact).

## Verifikasi setelah diterapkan
- Golden model: `GoldenModelINT8(model_path=...)` untuk tiap model. Fungsinya sudah ada di `ml/golden_model.py`.
- Test vector:
  - `ml/forecast/model/export/test_vectors.csv` (model 0);
  - `ml/status/model/export/test_vectors.csv` (model 1).
- Testbench perlu menerima byte `model_id`.
