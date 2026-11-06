# Pemeriksaan INA219 — 21 Oktober 2026

**Status dashboard terbaru:** atas permintaan pengguna, panel perangkat kembali
menampilkan V/A/W. Penerapan dan pemeriksaan browser selesai sekitar 20.01 WIB;
hanya template `wec_v2_tpl` berubah. Data invalid atau lebih dari 30 detik
ditampilkan sebagai tanda —. Data MQTT terbaru masih rendah (contoh Raspi
0,484 V), sehingga panel menampilkan `DATA TIDAK VALID`. Pengguna menerima
kondisi ini sementara. FPGA tetap `BELUM DIPASANG`. Backup sebelum perubahan:
`/tmp/wec-vaw-backup/power_before_20261021_125608.json`; screenshot lokal:
`/tmp/wec-vaw-dashboard.png`. Uji panel V/A/W, panel perbandingan, dan validasi
function INA219 lulus. Riwayat panel ampere saja di bawah merupakan status lama.

Pengguna melaporkan tegangan input Raspberry Pi stabil **5,1 V** pada multimeter.
Ini berbeda dari bacaan MQTT INA219 sebelumnya (sekitar 0–1,5 V). Belum ada
bukti bahwa ESP32 atau INA219 rusak; perlu membandingkan titik ukur yang sama.

## Pemeriksaan fisik berikutnya

1. Ukur `VIN−` INA219 terhadap `GND` **modul INA219 yang sama**. Nilainya
   seharusnya dekat dengan input Raspi jika kabel pengukuran benar.
2. Jika input Raspi 5,1 V tetapi titik tadi berbeda, periksa ground referensi
   INA219–ESP32–catu Raspi dan sambungan VIN− menuju beban.
3. Jika kedua titik sama tetapi MQTT berbeda, uji firmware baru dan catat
   `sensor_ok`, `measurement_valid`, `error`, serta `shunt_mv`.
4. Pastikan resistor shunt modul bertanda `R100` (0,1 ohm). Kalibrasi firmware
   masih mengikuti asumsi ini dari kode sebelumnya; resistor berbeda memerlukan
   kalibrasi arus/daya berbeda. Kalibrasi shunt tidak memperbaiki ground bus yang salah.

Bus INA219 mengukur tegangan `VIN−` terhadap ground, sedangkan ESP32 membaca
register digital lewat I2C. Bacaan ini tidak memakai ADC analog ESP32.
Jangan mengganti hasil ukur dengan konstanta 5,1 V.

## Perbaikan software yang disiapkan

- Firmware: transaksi I2C diperiksa, konversi tunggal shunt+bus dengan averaging
  16 sampel, tunggu conversion-ready maksimal 100 ms, tolak overflow dan bacaan
  di luar pemeriksaan jalur 5 V (4–6 V). Rentang ini hanya filter diagnosis,
  bukan batas spesifikasi tegangan kerja Raspberry Pi.
- Arus/daya diasumsikan memakai shunt 0,1 ohm, calibration register 4096.
- Daya invalid dikirim `null`; tegangan, arus dan shunt tetap tersedia jika
  transaksi berhasil. Energi tidak diintegrasikan melewati sampel invalid
  atau jeda panjang.
- Node-RED memvalidasi firmware lama juga dan menghapus daya yang invalid.
  Sesuai permintaan pengguna, template hackathon sekarang menampilkan **arus
  saja (A)**, dengan status arus terbaca / data lama / tidak valid. Tegangan,
  watt, Wh dan persentase penghematan di panel komputasi dihilangkan.
  Arus tetap ditandai belum diverifikasi alat ukur, meskipun data MQTT tersedia.
- Pemetaan fisik tetap: firmware `fpga` = Raspi, `raspberry_pi` = FPGA+S3;
  dashboard dan pencatat Influx sudah menukarnya.
- Firmware diagnosis kini mengirim `schema_version: 2`, `shunt_ohm`,
  `measurement_valid`, `error`, `shunt_mv`, `energy_valid_time_s`, dan snapshot
  register `bus`, `shunt`, `current`, `power`, `config`, `calibration`.
  Konfigurasi dan kalibrasi dibaca ulang, serta arus dibandingkan dengan
  tegangan shunt/R100. Register shunt/current adalah bit mentah 16-bit bertanda;
  interpretasikan sebagai int16 sebelum mengonversi satuan.
  `energy_wh` hanya mencakup interval valid, bukan seluruh waktu sejak boot
  bila sensor bermasalah; durasi valid dikirim terpisah.

## Validasi dan penerapan

```bash
g++ -std=c++17 -Wall -Wextra -Werror -Iedge/esp32/include \
  edge/esp32/test/ina219_reading_test.cpp -o /tmp/wec-ina219-test
/tmp/wec-ina219-test
node dashboard/wec/test_daya_node.js
python3 dashboard/wec/test_power_panel.py
/home/izmaherdian/tools/pio-venv/bin/pio run -d edge/esp32 -e esp32_daya
```

Uji decoder, validasi Node-RED dan build firmware lulus. Template hackathon
berhasil dibangun; uji transisi arus terbaca, data lama, invalid, pulih,
pesan tidak berurutan dan timestamp masa depan juga lulus.
Firmware belum diunggah: USB yang terdeteksi hanya ESP32-S3 bridge dan debugger
Sipeed, belum ESP32 klasik pengukur daya.

Perubahan dashboard **sudah diterapkan** pada 21 Oktober, diverifikasi 13.58 WIB
di browser dengan data live: Raspi 0,503 A dan FPGA+S3 sekitar 0,000 A pada sampel
itu. Ini adalah bacaan INA219 yang belum diverifikasi, bukan hasil ukur arus
multimeter dan bukan bukti FPGA tanpa konsumsi. Pesan MQTT sebelumnya sendiri
sudah berisi tegangan Raspi 0,050–0,064 V; tidak ditemukan skala tegangan yang
diubah oleh Node-RED.

Deploy melalui `dashboard/wec/deploy_power.py`: hanya `wec_daya_fn` dan
`wec_v2_tpl` berubah; semua node lainnya diverifikasi identik. Backup sebelum
deploy: `/home/izmaherdian/nodered-backups/power_before_20261021_065632.json`
(nama waktu UTC). Tangkapan layar verifikasi:
`/tmp/wec-current-live-verified.png` (lokal, tidak masuk git).

Referensi: [datasheet INA219](https://www.ti.com/lit/ds/symlink/ina219.pdf),
[catu resmi Raspberry Pi 4, 5,1 V / 3 A](https://www.raspberrypi.com/products/type-c-power-supply/).

## Pemeriksaan lanjutan sore hari

Pengguna mengonfirmasi INA219 baru mengukur Raspi; kanal FPGA+S3 belum dipasang.
ESP32 klasik menyala tetapi USB belum tersambung ke laptop. Pada pemantauan
20 detik terbaru tidak ada satu pun pesan baru `WEC/daya`; bukti:
`measurements/results/2026-10-21-meter-check.json`. Ini belum mengidentifikasi
penyebab putusnya pengiriman (WiFi, MQTT, atau firmware); diperlukan serial.
ESP32 klasik juga belum muncul pada daftar perangkat USB laptop.

Firmware diagnosis di atas sudah lolos build dan uji decoder di laptop, tetapi
belum diunggah ke ESP32 klasik. Uji perhitungan energi juga lulus (satuan J/Wh,
integrasi batas interval, penolakan gap/invalid, pemisahan energi total dan
tambahan di atas baseline). Data contoh 5,1 V / 0,5 A / 2,55 W yang disampaikan
pengguna adalah ilustrasi, bukan hasil ukur baru.

Dashboard kini menampilkan **BELUM DIPASANG** untuk kanal FPGA meskipun belum ada
pesan MQTT, dan tidak mengganti data hilang dengan nol. Energi kedua perangkat
tetap kosong sampai dua kanal dipasang dan tervalidasi.

## Hambatan USB laptop saat unggah

Pada 21 Oktober 18.52 WIB, kernel melaporkan `xHCI host controller not
responding, assume dead` untuk PCI `0000:03:00.4` (bus USB 3/4).
Controller `0000:03:00.3` terpisah melayani debugger Sipeed dan SSD T7;
SSD tersebut juga memuat sistem root laptop, sehingga jangan reset controller
itu atau memuat ulang seluruh driver USB.

ESP32 klasik sudah dipindah port dan dipasang ulang oleh pengguna, LED menyala,
tetapi pemeriksaan ulang sekitar 19.03 WIB masih hanya mendeteksi debugger
Sipeed, tanpa perangkat serial ESP32 dan tanpa peristiwa enumerasi USB baru.
LED menyala belum membuktikan koneksi data USB bekerja. Percobaan pemulihan
controller yang macet sebelumnya berhenti karena autentikasi admin diperlukan;
belum ada driver yang diubah. Firmware diagnosis belum diunggah dan bacaan
INA219 belum bisa diverifikasi melalui serial.

## Hasil setelah pemulihan USB dan unggah

**Pembaruan pengukuran fisik:** pengguna kemudian mengukur VIN− terhadap GND
modul yang mengukur Raspi dan mendapat sekitar **0,5 V**. Jadi bacaan bus rendah
juga muncul pada multimeter di titik tersebut. Input Raspi sebelumnya dilaporkan
5,1 V; periksa apakah shunt berada pada jalur positif atau negatif dan apakah
ada jalur suplai lain. Ini belum membuktikan ESP32/INA219 rusak, dan tidak berarti
Raspi bekerja dengan catu 0,5 V. Pemetaan kabel fisik sedang diminta.

Pengguna menyetujui dialog admin. Pemulihan terbatas `0000:03:00.4` berhasil
sekitar 19.04 WIB; CP2102 serial `0001` muncul sebagai `ttyUSB2`, sedangkan
controller SSD/FPGA tidak diubah. Unggah pada 460800 baud gagal sebelum
penulisan flash. Pada 115200 baud firmware berhasil ditulis dan hash flash
terverifikasi. Env `esp32_daya` kini memakai kecepatan unggah tersebut.

Rekaman serial dan MQTT selama 50 detik setelah unggah:

- ESP32 tersambung ke eduroam dan MQTT kembali mengirim `schema_version: 2`.
- Diterima 45 sampel. Kanal fisik Raspi (objek JSON `fpga`) membaca
  **0,172–0,720 V**, **0,4823–0,5798 A**, shunt **48,23–57,98 mV**.
- Seluruh sampel Raspi ditandai `measurement_valid: false` dengan error
  `voltage_outside_5v_rail`. Daya `null`, energi dan durasi valid tetap nol.
  Nol pada akumulator ini berarti belum ada interval valid, bukan konsumsi nol.
- Konfigurasi dibaca kembali 15971 (`0x3e63`), kalibrasi 4096; arus raw sama
  dengan shunt raw, sesuai skala firmware R100. Ini memverifikasi transaksi
  register, belum membuktikan akurasi alat maupun nilai resistor fisik.
- Kanal FPGA+S3 belum dipasang ke beban. Angka pada kanal tersebut tidak
  dipakai sebagai pengukuran konsumsi perangkat.

Bukti: `measurements/results/2026-10-21-meter-after-upload.json`. Baris serial
identik berturut-turut disimpan sebagai `line`/`count`; seluruh pesan MQTT
dipertahankan. Ada rentetan serial berulang pada awal rekaman; analisis angka
di atas memakai 45 pesan MQTT, bukan jumlah baris serial.

Software belum mengatasi perbedaan tegangan terhadap multimeter 5,1 V.
Langkah fisik berikutnya: probe hitam tepat di **GND modul INA219**, probe merah
di **VIN− modul yang sama**; periksa apakah GND modul tersambung ke GND ESP32
dan negatif catu Raspi. Bila tetap 5,1 V pada referensi itu, lanjutkan isolasi
modul/sambungan dan pembandingan dengan sensor pengganti. Arus dashboard tetap
merupakan bacaan yang belum diverifikasi; hasil energi belum dapat dilaporkan.
