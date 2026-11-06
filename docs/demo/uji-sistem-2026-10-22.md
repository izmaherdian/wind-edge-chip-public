# Uji sistem end-to-end — 22 Oktober 2026

Pemeriksaan menyeluruh sebelum Demo Day (kode, build, simulasi, dan jalur live). Ditulis setelah simulasi baterai
diganti ke aki 12 V 50 Ah dan deck Demo Day dirombak.

## 1. Tes kode (laptop)
| Tes | Perintah | Hasil |
|---|---|---|
| Paritas inti ESP32 C++ = Python = JS (model, fitur, kuantisasi, UART+CRC, mode PZEM diam, mode celah, aki) | `ml/.venv/bin/python edge/esp32/test/run_native.py` | LULUS, 0 beda (aki: 2.000 kasus) |
| Mesin Node-RED (JS) | `node dashboard/wec/test/{test_engine,test_node,test_tanpa_pzem,test_celah}.js` | LULUS |
| Panel daya INA219 | `node dashboard/wec/test_daya_node.js`, `python dashboard/wec/test_power_panel.py`, `test_comparison_panel.py` | LULUS |
| Energi per prediksi (pencatat Raspi) | `python measurements/test_energy.py` | LULUS |
| RTL: regresi 500 vektor + SoC UART (CRC-8) | `python hw/sim/run_regression.py` | LULUS (500/500, 8/8) |
| RTL: uji pre-silicon satu vektor | `python hw/sim/test_runner.py` | LULUS setelah diperbaiki (lihat catatan) |
| Firmware: 5 env PlatformIO | `pio run -d edge/esp32 -e <env>` (esp32s3, esp32dev, esp32s3_hil, esp32s3_bridge, esp32_daya) | semua SUCCESS |
| Deck | `latexmk -xelatex demoday.tex`; `buat_pptx.py` | 21 halaman / 20 slide, tanpa error |

Catatan perbaikan `hw/sim/test_runner.py` (milik bidang FPGA, diperbaiki di `feature/integrasi`, perlu diteruskan ke Alif):
daftar file belum memuat `weights_rom.v` (modul BSRAM bobot yang ditambahkan belakangan) dan folder `waveforms/` untuk
VCD tidak dibuat. Pesan lama "Simulator iverilog belum siap / sedang mengunduh" menyesatkan: penyebab aslinya modul hilang.

Tes yang butuh perangkat tidak dijalankan: `hw/scripts/test_uart_hil.py` (papan ke laptop) dan
`edge/bridge/test_fpga_uart.py` (file untracked milik anggota lain).

## 2. Jalur live (16.10 WIB)
| Tahap | Status | Bukti |
|---|---|---|
| Raspi → MQTT `TurbinAngin/*` | ✓ | 252 pesan / 95 dtk; `nodered_duadata` active |
| Mesin ML Node-RED → `WEC/prediksi`, `WEC/status`, `WEC/baterai` | ✓ | tiap menit; panel "Aki 12 V 50 Ah" tampil setelah deploy |
| Inferensi native Raspi `WEC/rpi` | ✓ | out_q identik dengan mesin Node-RED (40=40, 39=39) |
| Pencatat perbandingan `WEC/comparison/summary` | ✓ | `wec-comparison-record` active; energi valid sejak 13.45 |
| InfluxDB laptop + subscriber | ✓ | 19.207 titik, 0 galat |
| ESP32-S3 → FPGA `WEC/fpga` | ✗ | tidak ada pesan sejak ±15.35 (papan mati/dipindah ke PSU); dashboard jujur menulis "FPGA belum tersambung" |
| ESP32 INA219 `WEC/daya` | ✗ | tidak ada pesan; panel daya "MENUNGGU SENSOR" |
| Google Sheets (database dashboard) vs InfluxDB | belum | Sheet privat (ekspor CSV 401); perlu `/mcp` → claude.ai Google Drive atau CSV dari Genis |

## 3. Temuan yang perlu ditindaklanjuti
- **Raspi reboot karena catu daya**: 13.24, 13.28, dan ±16.00 Raspi menyala ulang tanpa catatan di `log_reboot.txt`
  (bukan skrip cek internet) dan `vcgencmd get_throttled = 0x50000` (undervoltage pernah terjadi). Pakai adaptor 5,1 V 3 A
  resmi Raspi 4 dan kabel 5 V/GND yang pendek-tebal (INA219 + jumper menambah rugi tegangan).
- **IP Raspi berubah** 10.18.117.195 → .197 (DHCP); `~/.ssh/config` sudah diperbarui (HostKeyAlias ke IP lama).
- **Akurasi live 24 jam** di dashboard (22 Okt sore) MAE 27,1 W vs persistence 38,7 W: hari berangin, galat absolut naik,
  model tetap ±30% lebih baik dari persistence. Uji resmi 1–20 Okt: 5,48 W vs 8,67 W.
- **Simulasi aki** diganti 384 Wh LiFePO4 → 12 V 50 Ah timbal-asam (600 Wh, DoD 50%, η 0,90/0,95); paritas Python/JS/C++ tetap 0 beda.
