# Runbook demo Wind Edge Chip (Hackathon 21–23 Okt 2026)

Tujuan: demo yang menunjukkan ketiga lapis berjalan (L1 digitalisasi, L2 edge AI, L3 chip), dengan angka nyata. Setiap bagian yang masih simulasi disebut terang-terangan.

**Format Demo Day (briefing panitia 22 Okt): 7 menit pitch + live demo, lalu 5 menit QnA.** Deck dan naskah final ada di `docs/presentasi/hackathon-2026/demo-day/` (`demoday.pdf`/`demoday.pptx`, `naskah.md`); demo live 2 menit di slide 5. Alur 5 menit di bagian 3 di bawah adalah versi lama yang lebih panjang (untuk mentoring/booth).

## 1. Apa yang benar-benar jalan

| Bagian | Status 21 Okt | Bukti yang bisa ditunjukkan |
|---|---|---|
| Sensor di atap CRIMSE → Raspi → MQTT | **live** (kadang reboot saat internet mati; PZEM sempat diam) | `/dashboard/hackathon`: angka live, CCTV/digital twin |
| Mesin ML 3 fitur di Node-RED (MLP INT8 = FPGA) | **live** tiap menit | hero "Prediksi 1 jam", status, SoC; mode cadangan bila PZEM diam |
| Riwayat + hasil uji di InfluxDB | **live** di laptop | `http://127.0.0.1:8086` → dashboard "Wind Edge Chip · Turbin 1" |
| Akselerator MAC4 di Tang Nano 4K | **jalan di papan** (HIL 21 Okt: ESP32-S3 ↔ FPGA, 5.373/5.373 identik, 309 siklus, `docs/demo/hil-2026-10-21.txt`) | slide "Chip jalan di papan"; `pio run -d edge/esp32 -e esp32s3_hil -t upload` lalu monitor |
| Jembatan data live → chip → dashboard | **live di papan** sejak 21 Okt 11.56: ESP32-S3 (env `esp32s3_bridge`, hotspot HP) ↔ Tang Nano 4K | baris "Chip: Tang Nano 4K via ESP32-S3 UART1" di dashboard; cadangan `fpga_bridge.py --sim` (ditandai "simulasi") |
| Firmware ESP32-S3 pembaca sensor langsung | dikompilasi + inti diuji 0 beda; **Modbus/anemometer belum diuji di plant**. Firmware bridge UART sudah berjalan di papan. | `python3 edge/esp32/test/run_native.py` |
| Baterai/inverter | **simulasi** (belum terpasang) | panel Baterai, slide "Lebih maju" |

## 2. Persiapan (30 menit sebelum)

1. Laptop di Wi-Fi yang sama dengan Raspi kalau ingin SSH (opsional); dashboard cukup internet biasa.
2. Cek data mengalir:
   - `ssh RASPI-TURBIN 'tail -2 ~/log_reboot.txt; journalctl -u nodered_duadata --since "-1 min" --no-pager | tail -5'` (hanya baca).
   - Dashboard menampilkan angin dan daya yang bergerak. Kalau tertulis "tidak ada data turbin masuk sejak …", Raspi sedang reboot; tunggu ±5 menit.
3. Nyalakan chip: colok ESP32-S3 dan Tang Nano 4K ke USB; pastikan bitstream 21 Okt aktif. Bitstream beserta bobot sudah ditulis ke flash internal pada 21 Okt malam (CRC sukses dan 3 vektor setelah reset cocok); lihat `docs/demo/flash-permanen-fpga.md`. Uji putus daya kedua papan juga lulus: 3/3 prediksi cocok tanpa pemrograman ulang; bukti di manifest. ESP32-S3 menjalankan `esp32s3_bridge`: tersambung ke WiFi yang diisi di `edge/esp32/include/secrets.h`, lalu tiap menit meneruskan fitur ke FPGA. Cek: `pio device monitor -d edge/esp32 -e esp32s3_bridge` harus menampilkan `chip … SAMA | 309 siklus`. Upload ulang bila perlu: `pio run -d edge/esp32 -e esp32s3_bridge -t upload`. **Jangan** jalankan `fpga_bridge.py` bersamaan (keduanya menulis `WEC/fpga`).
4. Nyalakan database (dan jembatan laptop hanya bila ESP32 tidak dipakai):
   ```bash
   dashboard/db/start.sh
   ml/.venv/bin/python edge/bridge/fpga_bridge.py --port /dev/ttyUSB0   # papan tersambung (TXD→44, RXD←46, GND), 921600 bps
   ml/.venv/bin/python edge/bridge/fpga_bridge.py --sim                 # tanpa papan (dashboard menandai "simulasi")
   ```
   Cek papan lewat ESP32-S3 (kabel di `docs/demo/kabel-esp32s3-fpga.png`): muat bitstream ke SRAM `openFPGALoader -b tangnano4k wind_edge_chip.fs`, upload `esp32s3_hil`, tekan RESET, baca serial 115200 (harus "597/597 identik"). Atau dari laptop: `hw/scripts/test_uart_hil.py --port /dev/ttyUSB0` (branch `feature/fpga`/`feature/integrasi`; bitstream harus versi 21 Okt dengan paket + CRC-8, 921600 bps).
5. Buka tab:
   - `http://citaitb.com:1880/dashboard/hackathon` (utama)
   - `http://citaitb.com:1880/dashboard/dashboard` (dashboard asli TA, pembanding "sebelum")
   - `http://127.0.0.1:8086` (InfluxDB)
   - deck `docs/presentasi/hackathon-2026/main.pdf` di pdfpc/Okular (video tertanam)
6. Mesin ML butuh ±50 menit data angin setelah Raspi reboot lama. Jangan deploy ulang Node-RED tepat sebelum demo; riwayat memang dipulihkan dari `WEC/state`, tapi tetap lebih aman.

## 3. Alur demo 5 menit

Uji ulang jalur Raspi sampai FPGA tanpa mengubah layanan:

```bash
ml/.venv/bin/python edge/bridge/check_live_path.py --seconds 150 --pairs 2 --report /tmp/wec-live-raspi.json
```

Hasil 21 Oktober: dua siklus baru lulus, timestamp identik, 309 siklus,
keluaran FPGA/CPU/golden identik. Lihat [laporan uji](uji-live-raspi-2026-10-21.md).

| Menit | Tunjukkan | Kalimat kunci |
|---|---|---|
| 0:00 | Hero dashboard: "Prediksi 1 jam" + daya + angin live | "Ini turbin di atap CRIMSE, sekarang. Angka ini rata-rata daya 60 menit ke depan, dihitung tiap menit." |
| 0:45 | Pita gelap: prediksi + rentang 80%, status kurva daya, baterai | "Satu jaringan saraf INT8 yang sama persis dengan chip kami. Kami juga melaporkan ketidakpastian, bukan satu angka." |
| 1:30 | Baris "Chip" + slide Chip L3 / Model dilatih dengan aritmetika chip | "Paket 19 byte dengan CRC-8 masuk, 7 byte keluar, 309 siklus (11 µs). Bobotnya dilatih langsung dengan aritmetika RTL, 0 beda di 2.597 vektor." |
| 2:30 | Mode cadangan / "PZEM tidak merespons" | "Sensor daya kami sempat mati tadi malam. Sistem tetap memprediksi dari angin, dengan MAE 5,14 W vs 5,07 W normal." |
| 2:50 | Keterangan "data berlubang" (kalau muncul) | "Internet di atap putus dan Raspi reboot tiga kali pagi ini. Dengan 20% data hilang, prediksi tetap ada 97,7% waktu." |
| 3:15 | Digital twin → Demo, geser angin 2 → 5 m/s | "Model yang sama berjalan di browser; daya naik mengikuti kurva empiris turbin ini." |
| 4:00 | Slide bisnis + roadmap | "Edge node ±Rp624 rb vs gateway SBC Rp3,3 jt; IP core milik sendiri, jalur ke ASIC." |
| 4:40 | Penutup | "Prediksi di turbin, tahan internet putus, chip rancangan sendiri." |

## 4. Kalau ada yang gagal

| Gejala | Tindakan |
|---|---|
| Dashboard "tidak ada data turbin masuk sejak …" | Raspi reboot karena internet; tunjukkan slide + InfluxDB historis, lalu kembali ke live |
| "PZEM tidak merespons" | Justru tunjukkan mode cadangan (poin 2:30) |
| Prediksi kosong "data belum lengkap: …" | Baru pulih dari gangguan panjang (butuh ≥30 menit data dalam 60 menit terakhir); pakai digital twin mode Demo + slide hasil uji |
| Keterangan "data berlubang" | Normal saat Raspi sering reboot; sebutkan uji: 20% data hilang → prediksi tetap ada 97,7% waktu, MAE 5,07 vs 5,00 W |
| FPGA tidak menjawab | Jembatan mencoba sinkron ulang; kalau tetap gagal, jalankan `--sim` dan katakan terus terang |
| Internet tempat acara mati | Deck PDF (video tertanam), InfluxDB lokal, `run_native.py` di terminal |

## 5. Jawaban singkat untuk juri

- **Kenapa FPGA, bukan langsung ESP32?** ESP32 memang bisa menjalankan model ini (dan menjadi cadangan bit-exact). FPGA adalah langkah menuju IP core/ASIC milik sendiri yang bisa dipakai lintas produk, dan memberi latensi deterministik 309 siklus.
- **Akurasinya cukup?** MAE 5,48 W pada data uji 1–20 Okt, 37% lebih baik dari persistence (8,67 W); skill +0,40. Ini dari 181 rb menit data nyata, bukan data sintetis.
- **Data yang hilang?** Raspi tercatat 2.787 kali reboot karena internet; edge node menyangga data di flash (±2 hari) dan tetap memprediksi offline 3 hari dengan prakiraan terakhir.
- **Bedanya dengan forecasting PLN?** Di turbin (tanpa internet), dengan interval ketidakpastian, dan diteruskan sampai energi baterai dan keputusan PLN (masukan coaching clinic).
- **TKDN?** RTL, firmware, model, dan dashboard milik sendiri; PCB dirakit lokal; angka TKDN dihitung setelah BOM produk final.
- **Kenapa badge "SVM TA" sering Anomaly?** Itu SVM lama di Raspi; masukannya anemometer Arduino yang macet di 1,25 m/s. Status kami memakai angin stasiun dan kurva daya wajar. SVM versi angin stasiun sudah disiapkan untuk Raspi (`edge/ta/raspi/usulan-angin-stasiun/`): akurasi 96,5% terhadap label Cp, porsi Anomaly 10% (diameter 3 m).
