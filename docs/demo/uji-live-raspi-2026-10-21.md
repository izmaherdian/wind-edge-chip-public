# Uji jalur live melalui Raspberry Pi — 21 Oktober 2026

**Hasil: lulus dua siklus baru setelah perbaikan timestamp bridge.**

```text
Sensor plant → Raspi → MQTT TurbinAngin/*
                         ↓
                 Node-RED menyusun 16 fitur INT8
                         ↓ WEC/prediksi
                     ESP32-S3
                         ↓ UART
                    Tang Nano 4K
                         ↓ UART → ESP32-S3 → WEC/fpga
                     Dashboard
```

## Hasil yang dicatat

| Timestamp fitur (WIB) | Hasil FPGA / CPU / golden | Prediksi rata-rata daya 1 jam | Siklus | UART pulang-pergi menurut firmware |
|---|---|---|---|---|
| 16.09 | 54 / 54 / 54 | 52,49 W | 309 | 561 µs |
| 16.10 | 60 / 60 / 60 | 58,32 W | 309 | 562 µs |

Timestamp request dan reply identik. Kedua hasil dihitung ulang dengan golden
model lokal dari 16 fitur yang benar-benar diterima melalui MQTT, tidak hanya
mengandalkan flag `cocok` dari bridge. Pesan retained tidak dihitung sebagai
siklus baru; tidak ada request live tertinggal tanpa pasangan dalam laporan
akhir. Bukti lengkap: [JSON](uji-live-raspi-2026-10-21.json).

Raspi diperiksa melalui SSH: layanan `nodered_duadata` aktif,
`get_throttled=0x0`; log akuisisi mengirim PZEM dan stasiun cuaca. Browser
dashboard menampilkan `Tang Nano 4K via ESP32-S3 UART1 · 309 siklus · hasil
identik dengan CPU`, dan prediksi 58,3 W. Daya turbin aktual saat itu 50,2 W;
angka ini bukan target evaluasi prediksi satu jam yang sudah matang.

## Masalah yang diperbaiki selama uji

Uji awal mendapat tiga request baru; dua cocok, satu balasan memiliki timestamp
yang dibulatkan (`1792573440000` menjadi `1792573000000`). Timestamp bridge
sebelumnya diserialkan sebagai floating-point. Uji dengan header ArduinoJson
yang sama mereproduksi pembulatan pada 30 dari 1.440 timestamp per menit;
integer 64-bit mempertahankan 1.440/1.440 timestamp.

`bridge_main.cpp` kini mempertahankan timestamp sebagai integer 64-bit.
Build dan upload env `esp32s3_bridge` ke ESP32-S3 berhasil; uji dua siklus di
atas dilakukan sesudah upload. Raspi, firmware sensor plant, dan bitstream
FPGA tidak diubah dalam uji ini.

## Mengulang uji

Jalankan dari akar repo saat Raspi, Node-RED, ESP32-S3 bridge dan FPGA aktif:

```bash
ml/.venv/bin/python edge/bridge/check_live_path.py \
  --seconds 150 --pairs 2 --report /tmp/wec-live-raspi.json
```

Skrip hanya berlangganan MQTT dan keluar dengan kode 0 bila uji lulus. Ia
memeriksa data sensor baru, timestamp, keluaran golden/CPU/FPGA dan siklus.
Tidak perlu menjalankan bridge laptop kedua atau menyuntikkan fitur buatan.
Prediksi biasanya terbit setiap menit; bila mesin belum punya cukup riwayat,
laporan belum lulus sampai fitur tersedia.

## Batas bukti

- Ini uji integrasi singkat, bukan uji ketahanan lapangan berjam-jam.
- Penyusunan fitur masih di Node-RED; Raspi masih membaca sensor. Ini belum
  membuktikan ESP32 menggantikan Raspi atau berjalan mandiri tanpa jaringan.
- Akurasi terhadap daya aktual **60 menit berikutnya** harus dinilai sesudah
  target tersedia; kesamaan FPGA/CPU membuktikan kesetaraan perhitungan.
- Jalur sensor langsung RS-485/anemometer, restart penuh catu FPGA, enclosure,
  dan pengukuran daya INA219 masih perlu diuji tersendiri.
