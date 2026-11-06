# edge/ — Program ESP32

Pemilik: Genis (rekomendasi).

Isi yang direncanakan:
- baca sensor (Modbus/serial) dan susun fitur
- kirim fitur ke FPGA dan terima hasil lewat UART (`docs/kontrak-uart.md`)
- kirim data dan prediksi lewat MQTT
- model cadangan di ESP32 (dipakai kalau FPGA tidak menjawab; juga sebagai pembanding daya)

Firmware ada di `esp32/` (PlatformIO, sudah dikompilasi dan intinya lulus uji di laptop; belum diuji di papan). Lihat `esp32/README.md`.

Catatan: jenis papan ESP32 dan modul RS-485 masih perlu dikonfirmasi (Bagian 10 di `wind-edge-chip.md`).
