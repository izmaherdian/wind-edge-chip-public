# edge/ta/ — Program akuisisi dari TA

Program dari TA Genis, apa adanya. Hanya untuk acuan. Jangan dikembangkan di sini; program baru ditulis di `edge/`.

| File | Isi |
|---|---|
| `anemometer.ino` | Anemometer optik celah di Arduino: 18 celah, r = 0,08 m, faktor kalibrasi 2,3, kirim kecepatan angin lewat serial |
| `akuisisi_raspi.py` | Program utama di Raspi 4: baca PZEM-017 (Modbus, `/dev/ttyUSB0`), stasiun cuaca (Modbus, `/dev/ttyUSB1`), dan Arduino (`/dev/ttyACM0`); klasifikasi SVM (`model_pltb_svm_rbf.pkl`); kirim tiap 3 detik ke MQTT `citaitb.com`, topik `TurbinAngin/...` |
| `*.docx` | Berkas asli dari Genis |

File `.ino` dan `.py` disalin dari teks di dalam `.docx`. Di dalam `program-utama-akuisisi-data.docx`, kode tertempel dua kali dengan isi yang sama, jadi salinannya cukup satu.

Laporan TA: `docs/ta-genis/`.
