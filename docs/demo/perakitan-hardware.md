# Perakitan dan uji meja — 21 Oktober 2026

Target pertama: laptop mengirim fitur INT8 ke FPGA fisik, hasil dan CRC benar,
prediksi sama dengan golden model, dan siklus 309. Baru lanjut ke ESP32 dan sensor.

Gambar jalur ESP32-S3 ↔ FPGA dan kabel USB: [PNG](kabel-esp32s3-fpga.png) / [SVG](kabel-esp32s3-fpga.svg).
Gambar menunjukkan hubungan sinyal, bukan posisi lubang header; blok penerjemah level
diperlukan bila level bank FPGA berbeda dari level ESP32.

## Temuan sebelum merakit

- Laptop mendeteksi FT2232 (0403:6010) berlabel SIPEED JTAG Debugger FactoryAIOT Pro:
  `/dev/ttyUSB0` (if00) dan `/dev/ttyUSB1` (if01). Ini identitas antarmuka USB,
  belum membuktikan UART core pada pin 44/46 tersambung ke salah satunya.
- ESP32 dan adaptor UART terpisah belum teridentifikasi pada pemeriksaan USB.
- CST pada branch `feature/fpga`: RX FPGA = pin chip 44, TX FPGA = pin chip 46,
  reset aktif rendah = pin chip 14. Nomor pin chip bukan urutan ke-44 pada header.
- **Tegangan sudah diukur di papan (21 Okt 2026): bank 1 = 3,3 V.** Pin 44 dan 46 sama-sama di bank 1 (chipdb apycula). Pin 46 (TX FPGA) diukur ke GND saat UART diam ≈3,3 V setelah bitstream dimuat, jadi TX/RX ESP32-S3 boleh disambung langsung. Angka "LVCMOS18" di laporan Alif adalah standar I/O bawaan, bukan tegangan bank. Untuk papan atau revisi lain, ukur dulu; bila 1,8 V, pakai penerjemah level.
- Hasil uji HIL dengan kabel langsung: `docs/demo/hil-2026-10-21.txt` (5.373/5.373 inferensi identik, 309 siklus, 482 µs pulang-pergi).
- Acuan resmi: [pinmap dan tautan skematik Sipeed](https://wiki.sipeed.com/hardware/en/tang/Tang-Nano-4K/Nano-4K.html),
  [datasheet Sipeed, perhatian tegangan GPIO halaman 7](https://akizukidenshi.com/goodsaffix/Tang%20nano%204K.pdf).

## Langkah kerja Genis dan Izma

1. Catat papan, revisi, adaptor UART, multimeter, kabel jumper, dan header yang tersedia.
   Pastikan siapa yang menyediakan solder bila header belum terpasang.
2. Identifikasi label pin pada papan dan bank I/O. Cocokkan dengan CST, skematik,
   serta konfigurasi bitstream. Pastikan tegangan idle TX adaptor dengan multimeter
   terhadap ground sebelum dipasangkan; level VCC adaptor belum tentu level TX.
3. Putuskan daya sebelum menyolder atau mengubah sambungan. Solder hanya header
   yang diperlukan; cek kontinuitas tiap sambungan dan hubungan pendek ke pin tetangga.
4. Setelah level sesuai, sambungkan hanya TX adaptor → RX FPGA, RX adaptor ← TX FPGA,
   dan GND bersama. Gunakan kabel pendek. Daya papan lewat USB; kabel VCC adaptor
   tidak diperlukan untuk uji ini. Jangan sambungkan dua sumber TX ke RX yang sama.
5. Pastikan bitstream yang aktif adalah model prediksi daya terbaru: UART 921600 8N1,
   frame masuk 19 byte dan keluar 7 byte dengan CRC-8. Jika bitstream hanya dimuat
   ke SRAM, mencabut daya menghilangkannya; muat ulang lewat toolchain yang sudah
   dipakai tim dan pastikan file build sesuai bobot model saat ini.
6. Jalankan uji kecil 5 sampel, kemudian 20, lalu seluruh 597. Pilih port adaptor yang
   sudah diidentifikasi; `/dev/ttyUSB2` di bawah hanya contoh, bukan hasil deteksi.

   ```bash
   ml/.venv/bin/python -m serial.tools.list_ports -v
   ml/.venv/bin/python edge/bridge/test_fpga_uart.py --check-vectors
   ml/.venv/bin/python edge/bridge/test_fpga_uart.py --port /dev/ttyUSB2 --samples 5
   ml/.venv/bin/python edge/bridge/test_fpga_uart.py --port /dev/ttyUSB2 --samples 20
   ml/.venv/bin/python edge/bridge/test_fpga_uart.py --port /dev/ttyUSB2 --samples 597 --report /tmp/wec-hil.json
   ```

   Mode `--check-vectors` hanya cek acuan offline. Uji fisik lulus bila semua balasan
   valid, status nol, prediksi cocok, dan siklus 309. `roundtrip_us` meliputi USB/UART/host;
   bukan latensi core FPGA. Skrip keluar nonzero bila ada sampel gagal.
7. Jika timeout: periksa port, ground, label TX/RX, level sinyal, bitstream yang aktif,
   baud, serta versinya. Jangan menganggap port JTAG sebagai port core tanpa bukti.
8. Setelah uji laptop lulus, ganti sumber UART ke ESP32 sesuai jenis papan di
   `edge/esp32/include/config.h`. Untuk S3: TX GPIO6 → RX FPGA, RX GPIO5 ← TX FPGA,
   tetap melalui penerjemah level bila dibutuhkan. Reset GPIO7 bersifat opsional dan
   juga harus cocok levelnya. Lepas adaptor UART sebelum memasang TX ESP32.
9. Sambungkan sensor RS-485 setelah jalur FPGA stabil. Periksa tipe modul dan level
   sisi TTL sebelum menyambungkan ke ESP32. Mulai dengan satu sensor, baru sensor kedua.

## Catatan Shania

Catat waktu, komponen/revisi, alat ukur, tegangan yang diukur, diagram final,
versi bitstream dan bobot, port, jumlah sampel lulus/gagal, log JSON, dan foto.
Jika ada bagian belum diuji, tulis belum diuji. Uji UART ini tidak mengukur daya.

## Pengukur daya (2× INA219)

Diagram: [`pemasangan-ina219.png`](pemasangan-ina219.png) (sumber [`pemasangan-ina219.svg`](pemasangan-ina219.svg)). ESP32 klasik dengan firmware `esp32_daya` (`edge/esp32/README.md`): INA1 = Raspberry Pi (I2C 21/22), INA2 = Tang Nano 4K + ESP32-S3 (I2C 18/19). Arus diukur seri di kabel +5 V (Vin+ → Vin−), semua GND disatukan, dan perangkat yang diukur hanya diberi daya lewat INA (kabel USB laptop dicabut).

Pinout papan Tang Nano 4K (foto produk Sipeed): [`tang-nano-4k-pinout.avif`](tang-nano-4k-pinout.avif). Label header `1-xx`, `2-xx`, `3-xx` = nomor bank-pin; papan juga punya pin **5V** dan GND di header (bisa dipakai untuk catu lewat INA2).
