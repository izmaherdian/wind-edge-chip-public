# Kajian: prediksi setelah inverter dan ke baterai

Masukan PLN di coaching clinic (16 Okt 2026): forecasting daya turbin sudah ada di PLN. Yang belum ada adalah prediksi **setelah inverter** atau **yang masuk ke baterai**. Dokumen ini menjelaskan data apa yang dibutuhkan, dari mana datanya, dan apa yang sudah bisa dikerjakan sekarang.

## Sistem sekarang vs usulan
```
Sekarang : generator 3 fasa → rectifier → DC → PZEM-017 → resistor 35 Ω (dump load)
Usulan   : generator → rectifier → charge controller (MPPT angin) ─┬→ baterai ──→ inverter → beban AC
                                                                    └→ dump load (saat baterai penuh)
                                                       PLN ←→ (cadangan saat SoC rendah)
```

## Data yang dibutuhkan
| Besaran | Alat / sumber | Bisa dari API? | Status |
|---|---|---|---|
| Daya DC turbin (V, I) | PZEM-017 yang sudah ada | – | **Ada** (data 30 Mar–20 Okt) |
| Angin, arah, suhu, kelembapan lokal | Stasiun cuaca yang sudah ada | – | **Ada** |
| Prakiraan angin/tekanan/suhu | Open-Meteo (arsip + real-time), BMKG | **Ya** | **Ada** (Open-Meteo); BMKG perlu logger |
| Tegangan, arus, daya baterai (masuk/keluar) | PZEM-017 kedua di terminal baterai, atau INA226 + shunt | Tidak (spesifik lokasi) | **Perlu diukur** |
| SoC baterai | BMS dengan port data (UART/RS-485/CAN), atau coulomb counting dari arus baterai | Tidak | **Perlu diukur** |
| Suhu baterai | DS18B20 di badan baterai | Tidak | **Perlu diukur** |
| Daya AC keluaran inverter (V, I, P, PF, f) | PZEM-004T di sisi AC | Tidak | **Perlu diukur** |
| Konsumsi beban AC | PZEM-004T yang sama / per beban | Tidak | **Perlu diukur** |
| Energi yang dibuang ke dump load | PZEM-017 di jalur resistor | Tidak | **Perlu diukur** |
| Status charge controller (mode bulk/float, proteksi) | Port data charge controller (kalau ada) | Tidak | Opsional |
| Kurva efisiensi inverter | Datasheet / database CEC–Sandia (pvlib) | **Ya** (database publik) | **Dipakai** di simulasi |
| Perilaku baterai (SoC, penuaan) untuk pra-latih | NASA PCoE Battery Dataset, CALCE (UMD) | **Ya** (dataset publik) | Untuk estimator SoC/SoH berikutnya |

Semua sensor baru dicatat dengan timestamp yang sama dengan data turbin (ESP32 → MQTT → database), dan disimpan lokal dulu supaya tidak hilang saat internet mati (Raspi saat ini sudah 2.787 kali reboot karena internet mati).

## Yang sudah dikerjakan (simulasi): `ml/battery/sim_battery.py`
- Masukan: daya DC terukur (Okt 2026) dan prediksi 1 jam dari fitur 2 (MLP INT8 FPGA, LightGBM, persistence).
- Model: charge controller η 0,95 → baterai LiFePO4 384 Wh (η 0,97/0,97, SoC 10–100%) → inverter (kurva Hoymiles MI-250 dari database CEC) → beban 6 W + 25 W malam (skenario sengaja defisit supaya impor PLN terjadi).
- Keluaran: prediksi SoC 1 jam ke depan, energi masuk baterai, dan peringatan impor dari PLN. Semuanya dibandingkan dengan hasil simulasi. Angkanya ada di `ml/results/baterai_simulasi.json`.

## Catatan penting
- Dengan baterai, **titik kerja turbin berubah**: tegangan dijepit baterai/MPPT, tidak lagi ditentukan resistor 35 Ω. Model daya yang dilatih di data dump-load **tidak bisa langsung dipindah**. Perlu data baru setelah baterai dipasang, atau penyesuaian lewat kurva daya P(v).
- Semua angka simulasi bergantung pada asumsi. Angka sebenarnya baru ada setelah pengukuran di atas berjalan.

## Langkah berikut (usulan untuk roadmap)
1. Pasang baterai kecil + charge controller + inverter + 3 sensor (baterai, AC, dump load) di panel yang ada.
2. Rekam ≥ 2–4 minggu.
3. Latih ulang: (a) daya DC dalam mode baterai, (b) estimator SoC (bisa pra-latih dengan NASA/CALCE), (c) prediksi energi AC 1 jam.
4. Kontrol: berdasarkan prediksi, putuskan isi baterai / nyalakan beban / ambil dari PLN.
