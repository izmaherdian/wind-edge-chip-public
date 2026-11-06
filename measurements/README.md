# measurements/ — Pengukuran daya dan latensi

Pemilik: Shania (rekomendasi).

Yang diukur, dengan model yang sama:
- Raspberry Pi 4 (sistem TA)
- ESP32 saja
- ESP32 + FPGA

Yang dicatat: daya saat diam, energi per prediksi (V × I × t), waktu per prediksi, dan jumlah siklus per prediksi sebelum dan sesudah instruksi khusus.

Aturan: catat angka apa adanya, sertakan tanggal, alat ukur, dan cara ukur. Tidak ada angka perkiraan.

## Status implementasi 21 Oktober 2026

- Raspi menjalankan model INT8 native C++17 `-O2` dengan header bobot yang sama
  dengan firmware FPGA. 597/597 vektor uji identik pada Raspi.
- Kedua perangkat menerima fitur INT8 yang sama dari MQTT. Akuisisi RS-485 tetap
  di Raspi; tidak ada dua master pada bus sensor.
- Uji terkendali: 150 balasan baseline dan 150 inferensi per perangkat lengkap;
  semua inferensi cocok dengan golden model. Lihat
  [hasil](results/2026-10-21-comparison.json).
- Pencatat live dan pembanding model adalah layanan pengguna Raspi terpisah;
  `Linger=yes` agar hidup saat boot dan tidak berhenti setelah SSH ditutup.
- Dashboard hackathon memiliki panel perbandingan, dengan energi kosong sampai
  pengukuran siap. Kanal INA219 FPGA ditandai **BELUM DIPASANG** sesuai konfirmasi
  pengguna, bukan dianggap konsumsi nol.

**Belum tersedia:** hasil Wh/hari dan J/prediksi kedua perangkat. Pengguna baru
memasang INA219 pada catu Raspi; kanal FPGA belum dipasang. Pembacaan daya INA219
Raspi masih belum valid. Firmware diagnosis sudah diunggah ke ESP32 klasik dan
MQTT pulih. Pengukuran VIN− terhadap GND INA219 juga menunjukkan sekitar 0,5 V;
referensi ground ke negatif adaptor ternyata belum sama. Sambungan sudah
dibahas dengan pengguna, tetapi rekaman terakhir tetap invalid. Lihat
[diagnosis](../docs/demo/diagnosis-ina219.md) dan
[rekaman terakhir](results/2026-10-21-meter-ground-fixed.json).

Bitstream beserta bobot FPGA sudah disimpan ke flash internal dan lulus uji
setelah kedua papan dicabut-pasang dayanya, tanpa pemrograman ulang:
[bukti boot](results/2026-10-21-fpga-cold-boot-check.json).

## Dua jenis hasil energi

1. **Pemakaian normal:** catat paling sedikit 30 menit sebelum menampilkan
   proyeksi `Wh/hari = P_rata-rata × 24`. Ini proyeksi pada beban yang teramati,
   bukan pengukuran penuh 24 jam. Pencatat menyimpan jendela maksimum 24 jam dan
   merotasi bukti mentah per tanggal UTC.
2. **Energi per prediksi:** `J_total/N` membagi seluruh energi papan pada jumlah
   prediksi yang selesai; termasuk idle, WiFi dan pekerjaan latar. Uji terpisah
   menghitung tambahan energi di atas kondisi dasar:
   `(E_aktif − P_dasar × durasi_aktif)/N`. Selisih negatif/kecil tidak dijepit ke
   nol; perlu kajian ketidakpastian pengukuran.

Jangan memakai `P rata-rata papan × latensi mikrodetik` sebagai hasil ukur
energi tambahan satu inferensi. INA219 sekitar 1 sampel/detik tidak memisahkan
pulsa inferensi mikrodetik. Gunakan jendela baseline/aktif yang cukup panjang
dan laporkan resolusi serta ketidakpastian alat ukur.

Raspi tetap menjalankan akuisisi sensor dan program TA. Karena tugas papan belum
identik seluruhnya, perbandingan energi seluruh papan harus menyebutkan peran
tersebut; jangan menganggap Raspi dapat dilepas hanya dari hasil uji bridge ini.

## Menjalankan ulang

Deploy/validasi model native dan pencatat ke alias SSH Raspi:

```bash
ml/.venv/bin/python measurements/deploy_rpi.py         # daftar kandidat
ml/.venv/bin/python measurements/deploy_rpi.py --apply
```

Deploy menguji 597 vektor sebelum layanan berjalan. Kredensial MQTT dikirim lewat
stdin dan disimpan di file privat Raspi, tidak disalin ke laporan atau command
line. Layanan sensor `nodered_duadata` tidak diubah.

```bash
ssh RASPI-TURBIN 'systemctl --user status wec-inference wec-comparison-record'
ssh RASPI-TURBIN 'cat ~/wec-comparison/records/latest.json'
```

Uji kondisi dasar dan aktif, masing-masing 30 detik, 10 permintaan/detik:

```bash
ml/.venv/bin/python measurements/compare.py \
  --phase-seconds 30 --hz 10 \
  --meter-config measurements/meter.example.json \
  --report measurements/results/perbandingan-baru.json
```

Fitur diambil dari data plant terbaru lalu dibekukan untuk seluruh sesi.
Baseline menerima pesan pada laju yang sama tetapi tidak menjalankan model;
aktif menjalankan satu inferensi per permintaan pada kedua perangkat. Semua
pesan uji memakai `WEC/benchmark/*`, tidak mengganti prediksi turbin. Inferensi
normal dijeda otomatis selama uji, lalu pulih paling lambat lima detik setelah
pesan uji terakhir. Raspi tetap mengakuisisi sensor sepanjang sesi.

Pencatat normal mengenali uji benchmark, lalu memulai jendela normal baru setelah
uji selesai agar lonjakan 10 Hz tidak tercampur dengan beban produksi 1/menit.

## Batas pengukuran waktu

- `rpi_core_us`: fungsi model C++ saja, diukur dengan jam monotonic native.
- `dispatch_us`: Python → worker C++ → Python, termasuk IPC.
- `fpga_uart_us`: ESP32-S3 → UART → FPGA → UART → ESP32-S3.
- `mqtt_roundtrip_ms`: pengamat yang sama mengirim permintaan dan menerima
  balasan; termasuk jaringan, broker, antrean dan pemrosesan perangkat.

Jangan membagi `rpi_core_us` dengan `fpga_uart_us` untuk membuat klaim speedup.

## Menyelesaikan pengukuran daya

1. Firmware `esp32_daya` diagnosis sudah diunggah. Verifikasi ulang pembacaan
   setelah sambungan GND INA219–ESP32–negatif adaptor diperbaiki; VIN− terhadap
   GND modul harus sesuai tegangan input Raspi yang diukur multimeter.
2. Pasang kanal INA219 kedua untuk **gabungan** ESP32-S3 + FPGA, mengikuti
   [diagram pemasangan](../docs/demo/pemasangan-ina219.png). Seluruh arus kedua
   papan harus melewati kanal itu; suplai USB lain tidak boleh melewati sensor.
   Sebelum memutus catu FPGA, pastikan prosedur pemuatan bitstream/boot sudah
   tersedia: log HIL mencatat pemuatan SRAM dan cold boot belum dibuktikan.
3. Verifikasi resistor `R100` (0,1 ohm), ground/isolasi, tegangan **dan arus**
   terhadap alat ukur pembanding pada masing-masing kanal. Kalibrasi firmware
   saat ini mengasumsikan shunt 0,1 ohm.
4. Setelah kanal FPGA dipasang, ubah `TERPASANG.fpga` di
   `dashboard/wec/daya_node.js` ke `true`, lalu deploy panel. Label fisik tetap
   ditukar: firmware `fpga` mengukur Raspi, `raspberry_pi` mengukur FPGA+S3.
5. Salin `meter.example.json` menjadi konfigurasi lokal yang diisi dengan bukti
   alat ukur, hasil referensi, waktu UTC, shunt, `installed` dan `verified`.
   Jangan mengaktifkan `verified` sebelum verifikasi fisik selesai. Pasang
   konfigurasi yang sama pada `~/wec-comparison/meter.json` di Raspi dan restart
   **pencatat** setelah konfigurasi berubah.
6. Catat kondisi normal minimal 30 menit dan ulangi uji baseline/aktif. Simpan
   suhu, catu, konfigurasi WiFi, laju inferensi dan program latar yang berjalan.

Pencatat menyimpan status (energi per menit, pasangan prediksi, awal jendela) ke `records/state.json` tiap menit dan melanjutkannya setelah Raspi reboot (maks 6 jam); waktu pencatat mati dikecualikan dari jendela dan dilaporkan sebagai `downtime_excluded_s`, bukan diisi. Backup versi sebelumnya di Raspi: `~/wec-comparison/backup-resume-20261022/`.

Energi hanya dihitung dari transaksi sensor yang valid, timestamp baru, dan
segmen daya berurutan dengan celah maksimal 2,5 detik. Pencatat live memakai
cakupan minimal 95%, waktu sampel ESP32 (`t`), celah sampai 15 detik dijembatani linier, dan jendela yang dimulai dari sampel daya valid pertama
kedua kanal (22 Okt: Raspi sering reboot, jadi syarat 99% sejak boot hampir
tidak pernah tercapai); cakupan sebenarnya tetap dilaporkan. `meter.json` di Raspi
diisi 22 Okt atas keputusan tim dengan acuan INA219 sendiri (tanpa multimeter
pembanding), jadi energi adalah estimasi INA219.
Tidak ada pengisian tegangan dengan konstanta 5,1 V. Bukti mentah ada di Raspi
`~/wec-comparison/records/YYYYMMDD.jsonl`; `latest.json` berisi ringkasan terakhir.

Uji lokal perhitungan dan tampilan:

```bash
python3 measurements/test_energy.py
python3 dashboard/wec/test_comparison_panel.py
```
