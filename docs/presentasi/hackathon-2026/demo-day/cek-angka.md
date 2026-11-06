# Cek angka deck Demo Day (22 Okt 2026, diperbarui 23 Okt 00.40 — susunan 14 slide)

Setiap angka yang muncul di deck/naskah, sumbernya, dan hasil cek ulang. Slide utama hanya memakai 3 angka
(≈¼, 17×, 100%); sisanya ada di lampiran A dan persiapan QnA (`naskah.md`).

| Angka | Di mana | Sumber | Cek ulang 22 Okt |
|---|---|---|---|
| Energi turbin median 270 Wh/hari (separuh hari 187–377 Wh, 140 hari) | slide 2 (gambar), lampiran A/B | `ml/common/energi_harian.py` → `ml/results/energi_harian.json` | ✓ dihitung ulang; **mengganti 173 Wh** (integrasi daya, kehilangan energi saat Raspi reboot) |
| "Total Energy" dashboard ≠ energi harian | lampiran B, QnA | register PZEM kumulatif sejak reset | ✓ |
| Raspi 2,96 W, papan chip 0,17 W | lampiran A, QnA | INA219 22 Okt (dashboard + pencatat Raspi) | ✓ estimasi tanpa multimeter; kanal chip kemungkinan hanya FPGA |
| ≈¼ energi turbin **saat angin ringan / hari tipikal** (26%, separuh hari 19–38%), chip 1,5% | slide 3 | 71 Wh / 270 Wh, 4,1 Wh / 270 Wh | ✓ (sebelumnya "41%" dari 173 Wh, salah) |
| 17× lebih hemat (182 J vs 10,4 J per prediksi) | slide 5, 10, 14 | `WEC/comparison/summary` 22 Okt (screenshot `aset/dash-banding.png`) | ✓ |
| ≈24 kWh per tahun per turbin | lampiran A, QnA | (2,96 − 0,17) W × 24 × 365 | ✓ |
| 100% identik, 5.373/5.373, 309 siklus | slide 9, lampiran A/E | `docs/demo/hil-2026-10-21.txt` (9 ronde × 597) | ✓ |
| MAE 5,48 W vs persistence 8,67 W (−37%) | lampiran A, QnA | `ml/results/mlp.json` (INT8 test), `ml/results/baselines.json` | ✓ 5,481 / 8,674 |
| Sensor daya mati: MAE 5,14 W vs normal 5,07 W | lampiran A, QnA | `node dashboard/wec/test/test_tanpa_pzem.js` (20.997 menit, 22 Okt malam setelah mode pemulihan + aturan cut-in) | ✓ **mengganti 4,72 / 4,76 W** lalu 5,04 / 5,01 W (jumlah menit uji berubah) |
| Data berlubang 20%: cakupan 97,7%, MAE 5,07 vs 5,00 W | lampiran A, QnA, dashboard | `node dashboard/wec/test/test_celah.js` (20.783 menit) | ✓; pembanding lama "tanpa mode ini 12,5%" tidak dicetak tes lagi → dihapus dari deck dan dashboard |
| 2.787 reboot karena internet (Apr–Okt) | slide 3, lampiran A, QnA | `data/raw/raspi/log_reboot.txt` | ✓ 2.787 baris "Internet mati" |
| Komponen inti ±Rp624 rb vs gateway Rp3,3 jt (Rp3.294.795) | slide 3, 5, 11 | RAB di `docs/presentasi/hackathon-2026/main.tex` | ✓ |
| RUPTL 2025–2034 +7,2 GW angin | slide 2 | `main.tex` | sumber kebijakan, tidak dihitung ulang |
| Baterai 12 V 50 Ah, dump load 35 Ω / 1.200 W | slide 2, 6, 8 | spesifikasi dari tim (22 Okt) | ✓ simulasi dashboard diganti ke 600 Wh, DoD 50% |
| Ambang putar 1,4 m/s; PZEM mati < 7 V (≤ 1,4 W pada 35 Ω) | dashboard, QnA | `data/processed/turbine_1min.parquet`: PZEM kosong 51,5% pada 1,3–1,4 m/s, 98% pada 0,8 m/s; 97,8% menit kosong saat angin < 2 m/s; konfirmasi hardware dari tim | ✓ 22 Okt |
| Angin > 4 m/s dengan PZEM kosong (21%) | QnA | konfirmasi tim: sensor angin error saat hujan | catatan, tidak diolah |

## Slide 11 "Lebih murah, lebih banyak energi" (harga jual = asumsi tim, 23 Okt)

| Angka | Hitungan |
|---|---|
| Energi untuk rumah 199 vs 266 Wh/hari (+34%) | 270 − 71 = 199; 270 − 4,1 ≈ 266; 266/199 = 1,34 |
| ≈Rp8,6 rb vs ≈Rp11,5 rb listrik PLN/bulan | 199 × 30 = 5,97 kWh × Rp1.444,70 = Rp8.625; 266 × 30 = 7,98 kWh → Rp11.529 |
| 100 turbin ±2.400 kWh/tahun ≈ Rp3,5 jt | 67 Wh × 365 × 100 = 2.445 kWh × Rp1.444,70 = Rp3,53 jt |
| Paket Rp2,0 jt | Edge Kit Rp1,5 jt + pemasangan Rp0,5 jt (asumsi) |
| Modal Rp1,1 jt → untung ±Rp0,9 jt | kit ±Rp0,9 jt (komponen Rp624 rb + PCB, casing, rakit) + pasang ±Rp0,2 jt |
| Langganan Rp25 rb − server Rp5 rb = Rp20 rb/bulan | asumsi |
| Total 3 tahun: komputer mini ±Rp3,4 jt, sistem kami ±Rp2,9 jt | 3,29 jt + 36 × Rp3.079 = 3,41 jt; 2,0 jt + 36 × 25 rb = 2,9 jt |
| Listrik Raspi ±Rp3 rb/bulan | 2,96 W × 720 jam = 2,13 kWh × Rp1.444,70 (R-1) = Rp3.079 |
| 100 turbin: untung awal ±Rp90 jt + Rp24 jt/tahun; pelanggan hemat ±Rp130 jt di awal | 100 × 0,9 jt; 100 × 20 rb × 12; 100 × (3,29 − 2,0) jt |
