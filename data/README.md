# data/ — Petunjuk data

Data **tidak disimpan di git**. Semua data ada di Google Drive tim.

- Tautan Drive: TBD (Genis)
- Untuk mendapat akses, kirim email Google kamu ke Genis.

Cara pakai:
1. Unduh data dari Drive ke `data/raw/` di laptop.
2. Jangan mengubah isi `data/raw/`.
3. Hasil olahan disimpan di `data/processed/` (juga tidak masuk git).

## Database turbin (`data/raw/turbine-database/`)

Dari Genis, 20 Okt 2026. Nama file asli di Drive tidak cocok dengan isinya: formatnya campur DD-MM dan MM-DD, dan beberapa rentangnya salah. Karena itu file-file ini diberi nama baru `AWAL_AKHIR.csv` (tanggal ISO, 2026), sesuai baris pertama dan terakhir di setiap file.

Semua file sudah diseragamkan menjadi **CSV**: pemisah koma, UTF-8, akhir baris `\n`, header di baris pertama, dan tanpa baris kosong. File xlsx dikonversi dengan nilai sel yang sama persis. CSV dari Drive yang memakai pemisah `;` identik dengan versi xlsx-nya, jadi hanya disimpan satu. CSV 1–20 Okt diberi header yang sama dengan file 14 Sep – 1 Okt. Kalau kamu mengunduh dari Drive, minta saja salinan CSV yang sudah jadi ke Izma.

| Nama di `data/raw/turbine-database/` | Asal di Drive | Baris data | Kolom |
|---|---|---|---|
| `2026-01-13_2026-02-20.csv` | `Turbine Database 01-13-26 to 01-13-26.csv` | 221.595 | 6 (lama) |
| `2026-02-27_2026-03-07.csv` | `Turbine Database 02-27-26 to 03-30-26.csv` | 114.825 | 6 (lama) |
| `2026-03-30_2026-04-25.csv` | `Turbine Database 30-03-26 to 25-04-26.xlsx` (dan `.csv` yang sama) | 383.617 | 12 |
| `2026-04-26_2026-05-26.csv` | `Turbine Database 25-04-26 to 26-05-26.xlsx` | 384.608 | 12 |
| `2026-05-26_2026-06-15.csv` | `Turbine Database 26-05-26 to 15-06-26.xlsx` | 343.477 | 13 (+`ML_Status`) |
| `2026-06-15_2026-07-06.csv` | `Turbine Database 15-06-26 -6-07-26.xlsx` | 331.061 | 14 (+`ML_Status`, `Validasi`) |
| `2026-07-30_2026-08-21.csv` | `Turbine Database 30_7_26-26_8_26.xlsx` | 384.571 | 13 |
| `2026-09-14_2026-10-01.csv` | `Turbine Database 14-09-26 to 01-10-26.xlsx` | 88.358 | 13 |
| `2026-10-01_2026-10-20.csv` | `Turbine Database 09-14-26 to 10-01-26.csv` | 302.772 | 13 |

`Database Wind turbine - Google Spreadsheet copy.pdf` di Drive tidak dipakai. Isinya cetakan 139 baris (22 Jan 2026, 14.58.13–15.02.03), dan semua baris itu sudah ada di `2026-01-13_2026-02-20.csv`.

**Peringatan: ada nilai yang rusak karena Excel membacanya sebagai tanggal.** Di beberapa file yang aslinya xlsx, angka desimal seperti `17.9` dibaca Excel sebagai tanggal (17 Sep) dan tersimpan sebagai nomor seri, misalnya `46282`. Nilai aslinya tidak bisa dipulihkan dengan pasti, karena `1.05` dan `1.5` sama-sama menjadi 1 Mei. Jumlah sel bernilai 45.000–47.000 per file:

| File | Kolom yang rusak (jumlah sel) |
|---|---|
| `2026-04-26_2026-05-26.csv` | Angin Arduino 13.396 |
| `2026-05-26_2026-06-15.csv` | Curah Hujan 309.251, Kelembapan 43 |
| `2026-06-15_2026-07-06.csv` | Curah Hujan 283.450, Kelembapan 124 |
| `2026-07-30_2026-08-21.csv` | **Suhu 334.380, Curah Hujan 273.125, Daya 119.106, Angin Stasiun 35.979, Tegangan 16.339, Angin Arduino 8.261, Arus 7.572** |
| `2026-09-14_2026-10-01.csv` | Curah Hujan 29.323 |

File 13 Jan – 25 Apr dan 1–20 Okt bersih. Solusi terbaik: Genis mengekspor ulang periode-periode ini **langsung dari Google Sheets sebagai CSV** (File → Download → CSV), tanpa dibuka di Excel. Sampai itu ada, anggap sel bernilai di atas 45.000 sebagai data hilang (NaN).

Catatan:
- **Celah data:** 20–27 Feb, 7–30 Mar, 6–30 Jul, dan 21 Agu – 14 Sep tidak ada.
- File 27 Feb – 7 Mar punya 114.825 baris, sama dengan `dataset_PLTB1.csv` (data TA). Kemungkinan file itu adalah dataset TA.
- Duplikat `... 30-03-26 to 25-04-26(1).xlsx` dari Drive tidak dipakai karena md5-nya identik dengan file tanpa "(1)".
- Waktu ditulis sebagai teks `"D/M/YYYY, HH.MM.SS"` dalam WIB. Ubah ke UTC saat preprocessing (aturan di `ml/README.md`). Interval sampel tidak seragam (1–4 detik pada baris yang sudah dicek), jadi perlu di-resample.
- Format lama (6 kolom): `Timestamp, voltage, current, power, energy, Windspeed`.
- Format baru (12+ kolom): `Waktu, Tegangan (V), Arus (A), Daya (W), Energi (Wh), Angin Arduino (m/s), Angin Stasiun (m/s), Arah Angin (°), Kelembapan (%), Suhu (°C), Kebisingan (dB), Curah Hujan (mm)`, ditambah `ML_Status` (keluaran SVM TA) dan `Validasi` pada file tertentu.
- Ketika turbin mati, nilai listrik tertulis `OFF`, bukan angka.

## Energi harian turbin (`ml/common/energi_harian.py`)

"Total Energy" di dashboard adalah register energi PZEM (kolom `Energi (Wh)`) yang dihitung sejak reset terakhir,
bukan energi per hari. Energi harian dihitung dari kenaikan register yang dibersihkan:

- baris `OFF` = PZEM tidak menjawab (turbin diam) → daya 0 W, register kosong;
- register dihaluskan median 5 baris (flicker naik-turun), penurunan = reset PZEM → dibuang;
- kenaikan diterima bila ≤ 1 kW × jarak antarbaris + 2 Wh, termasuk lompatan setelah celah (Raspi reboot, PZEM tetap menghitung).

Validasi 22 Okt: pada 74 jam data tanpa celah, kenaikan register = integrasi kolom Daya (rasio 1,011). Integrasi daya
saja kehilangan energi saat Raspi reboot, sehingga ±1,6× lebih kecil per hari. Hasil (31 Mar–20 Okt, 140 hari):
median 270 Wh/hari, separuh hari 187–377 Wh. Keluaran `ml/results/energi_harian.{csv,json}`.

## Log reboot Raspi (`data/raw/raspi/log_reboot.txt`)

Disalin dari Raspi turbin 20 Okt 2026. Tiap baris = satu reboot otomatis karena internet mati (`cek_internet.sh`, tiap 10 menit). Selama internet mati, data tidak terekam, karena Raspi tidak menyimpan data lokal.

| Bulan (2026) | Apr | Mei | Jun | Jul | Agu | Sep | Okt (s.d. 20) | Total |
|---|---|---|---|---|---|---|---|---|
| Reboot | 283 | 143 | 159 | 77 | 76 | 1.766 | 283 | **2.787** |

Ditambah reboot terjadwal tiap 00.00 dan 12.00 (crontab).

Data lain:
- `dataset_PLTB1.csv`: data TA, 114.825 baris, sekitar 1 bulan.

Laporan TA ada di `docs/ta-genis/`. Program akuisisi dan training dari TA ada di `edge/ta/` dan `ml/ta/`.
