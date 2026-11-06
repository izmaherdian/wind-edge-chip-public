# Kontrak kuantisasi: model AI ↔ chip

Status: **terisi dari model hasil training 20 Okt 2026** (`ml/forecast/train_mlp.py`, branch `feature/ml`). Perubahan file ini wajib disetujui pemilik `ml/` dan `hw/`.

## Ringkasan
| Hal | Nilai |
|---|---|
| Tugas | Prediksi **rata-rata daya 60 menit ke depan** (W), diperbarui tiap 1 menit |
| Topologi | 16 → 32 → 16 → 1, ReLU di semua lapisan (termasuk keluaran) |
| Format bobot / bias | INT8 bertanda (rentang terpakai ±5) / INT32 |
| Susunan `weights.hex` | Per lapisan, per neuron j, lalu per input i; 2 hex per baris (1.040 baris) |
| Susunan `bias.hex` | b1[0..31], b2[0..15], b3[0]; 8 hex per baris (49 baris) |
| Requantize (semua lapisan) | `out = clamp(((acc + bias) * 32) >>> 8, 0, 127)`, sama dengan `post_process.v` (M=32, S=8) |
| Pembulatan | Floor (geser aritmetika ke kanan), tanpa pembulatan ke terdekat |
| Masukan | 16 × INT8 bertanda, tanpa zero point |
| Skala keluaran | `watt = out × 0.972076` (0…127 → 0…123.5 W) |
| Siklus per prediksi | 309 di RTL Verilog (iverilog, `hw/sim/run_regression.py`); cermin Python `sim_rtl.py` menghitung 310 |

File: `ml/forecast/model/export/` (`weights.hex`, `bias.hex`, `test_vectors.csv`, `mlp_int8.h`). Golden model: `ml/golden_model.py` (otomatis memuat bobot ini).

## Fitur dan skala (urutan = urutan byte di paket ESP32 → FPGA)
ESP32 menghitung `x_q = clamp(round((x − center) / scale), −128, 127)`.

| # | Fitur | Arti | center | scale |
|---|---|---|---|---|
| 0 | `p_now` | daya rata-rata menit ini (W) | 0 | 1.46848 |
| 1 | `p_lag5` | daya 5 menit lalu (W) | 0 | 1.46347 |
| 2 | `p_lag15` | daya 15 menit lalu (W) | 0 | 1.42816 |
| 3 | `p_lag30` | daya 30 menit lalu (W) | 0 | 1.46848 |
| 4 | `p_lag60` | daya 60 menit lalu (W) | 0 | 1.51175 |
| 5 | `p_mean60` | rata-rata daya 60 menit terakhir (W) | 0 | 0.995393 |
| 6 | `w_now` | angin stasiun, median menit ini (m/s) | 0 | 0.056811 |
| 7 | `w_mean10` | rata-rata angin 10 menit (m/s) | 0 | 0.0547705 |
| 8 | `w_mean60` | rata-rata angin 60 menit (m/s) | 0 | 0.0512267 |
| 9 | `w3_mean10` | rata-rata v³ 10 menit (m³/s³) | 0 | 2.68654 |
| 10 | `dir_sin` | sin arah angin (rata-rata vektor 10 menit) | 0 | 0.00787402 |
| 11 | `dir_cos` | cos arah angin | 0 | 0.00787402 |
| 12 | `hour_sin` | sin(2π·jam WIB/24) | 0 | 0.00787402 |
| 13 | `hour_cos` | cos(2π·jam WIB/24) | 0 | 0.00787402 |
| 14 | `rho` | kerapatan udara (kg/m³) | 1.07467 | 0.000385961 |
| 15 | `om_wind_next` | prakiraan angin Open-Meteo 10 m, rata-rata t…t+60 (m/s) | 0 | 0.0280807 |

Mode offline (tanpa internet): fitur 15 (`om_wind_next`) belum punya pengganti. Model khusus offline ada di tabel perbandingan (`ml/results/`).

## Uji kesamaan
- `test_vectors.csv`: 597 sampel nyata dari data test (1–20 Okt), berisi input, h1, h2, dan keluaran.
- Golden model = integer numpy = PyTorch QAT: 0 beda (16.255 sampel test).
- Golden model = cermin RTL Python Alif (`sim_rtl.py`): 0 beda (597 vektor).
- **RTL Verilog (iverilog 12):** `hw/sim/run_regression.py` 2.000 vektor acak + 16 SoC, `hw/sim/run_regression_real.py` 597 vektor nyata + 50 SoC: semua LULUS (branch `feature/integrasi`, 20 Okt 2026).
- Bitstream Tang Nano 4K dengan bobot ini: LUT 24%, Fmax 85,7 MHz, flash SRAM CRC sukses. Uji HIL lewat UART (pin 44/46) menunggu adaptor USB-TTL/ESP32.

## Usulan perbaikan RTL (bukan syarat)
Karena M/S sama untuk semua lapisan, bobot hanya memakai rentang ±5 dari ±127. **Sudah diuji 21 Okt** (`ml/forecast/eksperimen_ms_per_lapisan.py`, hasil `ml/results/eksperimen_ms_per_lapisan.json`): M per lapisan (S = 8) membuat bobot memakai rentang sampai ±45, tetapi galat uji hampir sama (MAE 5,45–5,65 W, RMSE 10,12–10,46 W untuk 7 kombinasi), sebesar selisih antar-pelatihan dengan konfigurasi yang sama. Kesimpulan: **tidak perlu jadi prioritas RTL**; M = 32/S = 8 sekarang cukup.
