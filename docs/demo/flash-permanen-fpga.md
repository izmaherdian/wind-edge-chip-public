# Bitstream dan bobot di flash internal FPGA

Pada 21 Oktober 2026 sekitar 20.31 WIB, bitstream model prediksi ditulis ke
**flash konfigurasi internal Tang Nano 4K (GW1NSR-4C)** menggunakan
openFPGALoader v1.2.0. Programmer menyelesaikan erase/write dan melaporkan
`CRC check: Success`. Ini menggantikan pemuatan SRAM sementara sebelumnya.

Bobot bukan dikirim per prediksi oleh ESP32-S3: 1.040 bobot INT8 (260 word
32-bit) dan 49 bias ditanam saat sintesis. Konfigurasi dari flash menginisialisasi
memori bobot FPGA saat boot. Audit membandingkan seluruh bobot/bias RTL dengan
export model forecast saat ini dan semuanya identik.

Bitstream lokal yang sudah diuji disalin ke
`hw/build/tang_nano_4k/wind_edge_chip_20261021.fs` (hasil build, tidak masuk git).
MD5: `c5a970a367d2830ca3079774815057ce`.
Manifest SHA256 dan status pengujian:
`measurements/results/2026-10-21-fpga-flash-manifest.json`.

## Penerapan dan bukti

```bash
/home/izmaherdian/tools/oss-cad-suite/bin/openFPGALoader \
  -b tangnano4k -f hw/build/tang_nano_4k/wind_edge_chip_20261021.fs
```

Pada sesi ini debugger dipilih secara khusus dengan `--busdev-num 1:7`.
Alamat USB berubah setelah cabut-pasang; periksa ulang dengan `lsusb`.
Seleksi serial awal gagal membuka perangkat sebelum penulisan; percobaan
dengan alamat USB di atas berhasil.

- Log penulisan: `measurements/results/2026-10-21-fpga-internal-flash-retry.log`.
- Reset JTAG dijalankan sesudah penulisan tanpa mengunggah ulang SRAM.
- Tiga vektor data nyata dikirim melalui MQTT ke firmware bridge ESP32-S3;
  seluruh keluaran cocok dengan acuan, masing-masing 309 siklus. Waktu UART
  pulang-pergi 560, 561, dan 572 µs. Bukti:
  `measurements/results/2026-10-21-fpga-post-flash-check.json`.
- ESP32-S3 teridentifikasi lewat serial FT232R `A5069RR4` dari pesan boot
  `ESP-ROM:esp32s3-20210327`; tidak perlu mengganti firmware S3 pada sesi ini.

## Uji putus daya: lulus

Pengguna mengonfirmasi telah mencabut dan memasang kembali daya kedua papan.
Sesudah itu, tanpa menjalankan programmer atau menulis SRAM/flash, tiga vektor
nyata dikirim melalui MQTT dan menghasilkan keluaran **0, 87, 10**, identik
dengan acuan. Masing-masing 309 siklus; UART pulang-pergi 560/561/570 µs.
Dengan demikian, pemuatan konfigurasi beserta bobot dari flash setelah putus
daya sudah terbukti melalui jalur ESP32-S3 → FPGA. Bukti lengkap:
`measurements/results/2026-10-21-fpga-cold-boot-check.json`; manifest sudah
ditandai `physical_power_cycle_verified: true`.

Acuan pemrograman: [Sipeed: flashing Linux](https://en.wiki.sipeed.com/hardware/en/tang/common-doc/flash-in-linux),
[openFPGALoader: Gowin](https://trabucayre.github.io/openFPGALoader/vendors/gowin.html).
