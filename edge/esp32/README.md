# edge/esp32: firmware edge node (ESP32 + FPGA)

ESP32-S3 menggantikan Raspi + Arduino di turbin. Tugasnya membaca sensor, menyusun 16 fitur INT8, lalu meminta prediksi ke FPGA Tang Nano 4K. Kalau FPGA tidak menjawab, ESP32 menghitung sendiri dengan MLP yang sama. Status turbin dan relai baterai/PLN ditentukan di ESP32, lalu semuanya dikirim lewat MQTT. Satu-satunya yang butuh internet adalah prakiraan Open-Meteo; satu kali ambil berlaku untuk 3 hari ke depan.

Status: **UART ESP32-S3 ↔ FPGA sudah diuji di papan** (5.373/5.373 inferensi identik, 309 siklus). Firmware `esp32s3_bridge` juga sudah menjalankan data live dari Raspi melalui MQTT dan Node-RED. Firmware lengkap pembaca sensor (`esp32s3`) sudah dikompilasi dan intinya lulus uji laptop; jalur Modbus/anemometer langsung ke ESP32 belum diuji di plant.

```
PZEM-017 ─┐ RS-485 (satu bus)            UART1 921600
Stasiun  ─┴─ MAX485 ── UART2 ── ESP32 ──────────────── Tang Nano 4K (MLP INT8, 309 siklus)
Anemometer optik ── GPIO15 ─┘   │  └── GPIO11/12 ── relai PLN / dump load
                                └── WiFi ── MQTT citaitb.com:1883 ── Node-RED / InfluxDB
```

## Isi
| File | Isi |
|---|---|
| `lib/wec_core/wec_core.{h,cpp}` | Inti, C++ murni tanpa Arduino: pembersihan sampel, agregat 1 menit, riwayat 256 menit, 16+16 fitur, kuantisasi, MLP INT8, status, baterai, keputusan relai, paket UART. Padanan baris per baris dengan `dashboard/wec/engine_core.js` |
| `lib/wec_core/wec_bundle.h` | Skala fitur presisi penuh, ambang status, interval P10–P90, parameter baterai + inverter. Dibuat oleh `tools/gen_bundle.py` dari `dashboard/wec/model_bundle.json` |
| `src/sensors.cpp` | PZEM-017 (input register 0–5, 9600 8N2), stasiun cuaca (holding register 0x01F4–0x01FA + 0x0201, 4800 8N1), anemometer optik (interupsi, 18 celah). Register dan rumus sama dengan `edge/ta/akuisisi_raspi.py` |
| `src/fpga_link.cpp` | Paket 19 byte `[AA 55, 16 fitur, CRC-8]`, balasan 7 byte `[55 AA, status, prediksi, siklus, CRC-8]` (`hw/rtl/top_soc.v` 21 Okt), 921600 bps, batas waktu 20 ms, coba ulang sekali |
| `src/net.cpp` | WiFi, MQTT, NTP, Open-Meteo, antrean offline di LittleFS |
| `src/main.cpp` | Jadwal: baca sensor tiap 3 detik, hitung fitur 1–3 tiap menit |
| `include/config.h` | Pin, topik, broker, URL Open-Meteo |
| `include/secrets.h` | SSID/sandi WiFi (tidak masuk git; salin dari `secrets.example.h`) |
| `test/run_native.py` + `test/wec_cli.cpp` | Uji inti di laptop terhadap Python dan JS |
| `src/hil_main.cpp`, `src/bridge_main.cpp`, `src/daya_main.cpp` | Firmware khusus: uji HIL (`esp32s3_hil`), jembatan live ke FPGA (`esp32s3_bridge`), pengukur daya INA219 (`esp32_daya`) |

Bobot MLP tidak disalin ke sini. `platformio.ini` langsung memakai `ml/forecast/model/export/mlp_int8.h` dan `ml/status/model/export/mlp_powercurve_int8.h`, jadi FPGA, Node-RED, dan ESP32 berbagi satu sumber bobot.

## Pemakaian
```bash
# uji inti di laptop (g++ + node), tanpa papan
python3 edge/esp32/test/run_native.py

# build + upload (PlatformIO; di laptop Izma: ~/tools/pio-venv/bin/pio)
cp edge/esp32/include/secrets.example.h edge/esp32/include/secrets.h   # isi WiFi
pio run -d edge/esp32 -t upload
pio device monitor -d edge/esp32          # log per menit: P1j, status, SoC, fpga ok/cpu

# setelah model dilatih ulang (bundle baru)
python3 edge/esp32/tools/gen_bundle.py
```

Hasil uji inti (21 Okt 2026):
- MLP prediksi daya dan MLP kurva daya identik dengan test vector golden model (597 + 600 vektor, h1/h2/keluaran 0 beda).
- Kuantisasi 16+16 fitur identik dengan Python (400 sampel).
- Fitur yang dihitung dari riwayat per menit sama dengan Python (400 sampel, 0 nilai beda); input INT8-nya identik 400/400.
- Baterai (langkah + prakiraan SoC) sama dengan `engine_core.js` (2.000 kasus acak).
- Mode PZEM diam (fitur dengan daya wajar) sama dengan `engine_core.js` (120 menit, separuh menit dayanya dikosongkan).
- Mode celah (syarat menit longgar saat data berlubang) sama dengan `engine_core.js` (120 menit, 30% menit hilang total). Di mesin Node-RED, mode ini menaikkan cakupan prediksi dari 12,5% ke 97,7% saat 20% menit hilang, dengan MAE 5,07 W vs 5,00 W data utuh (`dashboard/wec/test/test_celah.js`).

Build: `esp32s3` RAM 32% (106 KB), flash 13% dari 16 MB; `esp32dev` RAM 31%, flash 68%.

## Alur per menit
1. Sampel 3 detik dibersihkan dengan aturan yang sama dengan preprocessing (spike di atas batas fisik dibuang, sentinel arah −115 dibuang, angin > 8 m/s dibuang), lalu diagregasi per menit.
2. **Fitur 2:** 16 fitur dikuantisasi, lalu dikirim ke FPGA. Kalau PZEM diam, daya menit yang kosong diganti daya wajar dari MLP kurva daya (`mode` = `cadangan`/`campuran`), sama dengan mesin Node-RED; uji 1–20 Okt MAE 4,72 W vs 4,76 W normal. ESP32 juga menghitung sendiri untuk membandingkan. Kalau hasilnya beda, `n_beda` naik; seharusnya selalu 0.
3. **Fitur 1:** fitur kurva daya dihitung di CPU, karena RTL sekarang baru memuat satu model. Setelah RTL dua model diterapkan, set `FPGA_DUAL_MODEL 1`. Status diambil dari rasio rata-rata 30 menit aktual/wajar, dengan ambang 0,42 dan 1,463.
4. **Fitur 3:** SoC baterai disimulasikan, lalu prakiraan SoC 1 jam ditentukan dari prediksi daya. Aturan relai:
   - **PLN:** pindah ke PLN kalau SoC ≤ 12% atau diprakirakan menyentuh batas bawah dalam 1 jam. Kembali ke baterai kalau SoC ≥ 25%.
   - **Dump load:** nyala kalau baterai penuh dan masih surplus. Mati lagi setelah SoC turun 5 poin.
5. Kirim `WEC/esp32/menit|prediksi|status|baterai`. Skemanya sama dengan mesin Node-RED, ditambah `sumber`, `fpga` (ok, siklus, µs, jumlah ok/timeout/beda), dan status relai. Kalau MQTT putus, pesan ditulis ke `/antre.txt` (maks 600 KB, ±2 hari) dan dikirim ulang setelah tersambung. Raspi tidak punya penyangga seperti ini: datanya hilang setiap internet mati (tercatat 2.787 reboot).

Data mentah 3 detik dikirim ke `TurbinAnginESP/<besaran>` dengan format yang sama dengan Raspi (`ML_Status` di akhir batch). Kalau ESP32 sudah menggantikan Raspi, ubah `TOPIC_DATA` menjadi `TurbinAngin`, supaya flow Node-RED dan Google Sheets milik Genis tetap berjalan tanpa diubah. Subscriber Influx (`dashboard/db/mqtt_to_influx.py`) sudah menerima `TurbinAnginESP/#` (tag `turbin=esp32`) dan `WEC/esp32/#` (tag `sumber=esp32`).

## Sambungan
**Papan yang diuji 21 Oktober:** bank 1 dan TX FPGA saat idle sudah diukur 3,3 V; UART pin 44/46 tersambung langsung ke ESP32-S3 dan lulus HIL. Untuk papan/revisi lain, verifikasi ulang level bank dan gunakan penerjemah level bila berbeda. Jalur sensor dan relai pada tabel masih perlu diuji terpisah. Panduan uji meja:
[`docs/demo/perakitan-hardware.md`](../../docs/demo/perakitan-hardware.md).

Papan tim: **ESP32-S3-DevKitC-1 N16R8** (RAB), env `esp32s3` (bawaan). Pin ESP32 klasik ada di kolom kanan (env `esp32dev`). Di N16R8, GPIO26–37 dipakai flash/PSRAM dan GPIO19/20 dipakai USB, jadi tidak dipakai di sini.

| Fungsi | ESP32-S3 | ESP32 klasik | Ke | Catatan |
|---|---|---|---|---|
| RS-485 RX / TX / DE+RE | 16 / 17 / 4 | 16 / 17 / 4 | Modul RS-485 terisolasi → A/B ke PZEM-017 dan stasiun | Satu bus, alamat 1 dan 2. Baud diganti per transaksi (9600 8N2 / 4800 8N1). Kalau mengganggu, ubah baud stasiun ke 9600 atau pakai dua modul |
| UART FPGA RX | 5 | 26 | Tang Nano 4K pin 46 (`tx_pin`) | Papan uji: bank 1 = 3,3 V, HIL lulus |
| UART FPGA TX | 6 | 27 | Tang Nano 4K pin 44 (`rx_pin`) | |
| Reset FPGA | 7 | 25 | Tang Nano 4K pin 14 (`rst_n`) | Opsional; ditarik setelah dua kali gagal (FPGA juga punya watchdog sendiri) |
| Anemometer optik | 15 | 33 | Keluaran optocoupler | Pull-up internal, sisi turun |
| Relai PLN / dump load | 11 / 12 | 18 / 19 | Modul relai | Aktif tinggi (`RELAY_ACTIVE_HIGH`) |
| GND | GND | GND | FPGA, RS-485, relai | Ground bersama |

## Pengukur daya komputasi (env `esp32_daya`)
ESP32 **klasik terpisah** (DevKit V1) dengan dua INA219. Pin dan kalibrasi mengikuti kode tim:

| INA219 | Mengukur | ESP32 | Alamat |
|---|---|---|---|
| INA1 | Raspberry Pi (catu 5 V, lewat Vin+/Vin−) | I2C 0: SDA 21, SCL 22 | 0x40 |
| INA2 | Tang Nano 4K + ESP32-S3 (catu bersama) | I2C 1: SDA 18, SCL 19 | 0x40 |

Diagram pemasangan: `docs/demo/pemasangan-ina219.png`. INA219: VCC ke 3,3 V ESP32, GND bersama. Catu perangkat yang diukur dilewatkan seri: sumber → Vin+ → Vin− → perangkat. Kalibrasi `32V_2A`: arus di atas ±3,2 A tidak terbaca (Raspi 4 saat beban puncak bisa mendekati 3 A).

Tiap 1 detik firmware mengirim `WEC/daya`:
```json
{"t": 1792559303208, "raspberry_pi": {"voltage_v": 5.08, "current_a": 0.612, "power_w": 3.11, "energy_wh": 0.02, "sensor_ok": true},
 "fpga": {"voltage_v": 4.97, "current_a": 0.149, "power_w": 0.74, "energy_wh": 0.005, "sensor_ok": true}}
```
**Pemasangan 21 Okt tertukar:** INA di I2C 18/19 terpasang ke Raspberry Pi dan INA di I2C 21/22 ke FPGA + ESP32-S3. Firmware tidak diubah; label ditukar di Node-RED (`TUKAR = true` di `dashboard/wec/daya_node.js`) dan di subscriber Influx (`TUKAR_DAYA` di `dashboard/db/mqtt_to_influx.py`). Kalau kabel atau firmware nanti disesuaikan, kembalikan keduanya ke `false`.

Node-RED (`dashboard/wec/daya_node.js`) mengubahnya ke panel "Konsumsi Daya · Raspberry Pi vs FPGA + ESP32-S3" di `/dashboard/hackathon`, dan InfluxDB mencatatnya sebagai `wec_daya`. Sensor yang belum terpasang dicoba ulang tiap 10 detik, dan panelnya tetap "MENUNGGU SENSOR". Keluaran Serial tetap CSV `Time_ms,V1,I1,P1,V2,I2,P2` seperti kode asli. Wh dihitung sejak ESP32 menyala.

WiFi: kalau `WIFI_EAP_USER` diisi di `include/secrets.h`, firmware mencoba **eduroam** (WPA2-Enterprise PEAP/MSCHAPv2) dan bergantian dengan WiFi biasa (`WIFI_SSID`) tiap 30 detik sampai tersambung (`include/wifi_mulai.h`). Akun eduroam memakai akun kampus sendiri dan hanya ditulis di `secrets.h` (tidak masuk git). Diuji 21 Okt: tersambung lewat eduroam, 1 pesan/detik sampai ke panel.

```bash
pio run -d edge/esp32 -e esp32_daya -t upload      # ESP32 klasik; WiFi dari include/secrets.h
pio device monitor -d edge/esp32 -e esp32_daya
```

## Batasan yang diketahui
- Jam diambil dari NTP. Setelah sekali tersinkron, ESP32 tetap jalan saat offline. Kalau menyala tanpa internet sama sekali, perhitungan per menit menunggu jam valid; untuk itu perlu RTC DS3231 (belum ada).
- Firmware lengkap memiliki model offline di CPU bila fitur Open-Meteo tidak tersedia; bobot FPGA masih model utama. Pada mode bridge, penyusunan fitur masih bergantung pada Node-RED dan jaringan MQTT.
- Protokol UART mengikuti RTL `feature/fpga` 21 Okt (paket + CRC-8, 921600 bps). Bitstream lama (16 byte mentah, 115200) tidak cocok lagi; flash ulang versi terbaru.
- Belum diuji di plant: Modbus langsung ke ESP32, interupsi anemometer, dan relai. UART ke FPGA sudah lulus HIL (`docs/demo/hil-2026-10-21.txt`).
