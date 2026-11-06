# Audit Turbine Database dan riwayat 3 jam — 22 Oktober 2026

Pengguna memilih riwayat **3 jam terakhir** untuk grafik dashboard Hackathon
dan pemulihan riwayat fitur ML setelah reboot. Angka live tetap dari MQTT.
Google Sheets hanya dibaca; metode dan kredensial penulis tidak diubah.

## Progres yang dikonfirmasi

- Model FPGA tersimpan permanen; uji setelah putus daya sebelumnya lulus.
- Video dashboard sudah ada dalam deck Demo Day. Video fisik papan chip masih
  menunggu pengguna (`docs/presentasi/hackathon-2026/demo-day/video-chip.mp4`).
- Pencatat energi menyimpan status tiap menit dan melanjutkan setelah restart;
  waktu pencatat mati dikecualikan. Skrip reboot Raspi tidak diubah.
- Data energi perangkat saat ini adalah estimasi INA219 dengan syarat cakupan
  software 95% dan jembatan celah maksimal 15 detik, bukan kalibrasi independen.
- MQTT saat pemeriksaan riwayat masih menghasilkan prediksi dan ringkasan
  perbandingan (10 pasangan cocok, 0 mismatch pada snapshot pemeriksaan).

## CSV yang diberikan

`Turbine Database - Sheet1.csv` berukuran 27.158.595 byte, **326.585 baris data**,
rentang 1 Oktober 13.58.56 sampai 22 Oktober 17.11.07 WIB. Baris pertama kosong,
bukan header. Susunan 13 kolom dicocokkan dengan function penulis Node-RED.
CSV tidak diubah, diimpor ke database, atau dimasukkan git.

| Tanggal | Baris CSV mentah | Timestamp unik | Baris OFF unik | Titik Influx |
|---|---:|---:|---:|---:|
| 21 Oktober | 11.779 | 11.732 | 4.411 | 7.208 |
| 22 Oktober | 4.480 | 4.313 | 796 | 3.003 |

Ada **214 timestamp duplikat** pada dua tanggal tersebut dan **1.072 langkah
waktu mundur** pada urutan baris CSV terpilih. Pengolahan memakai urutan waktu
dan satu baris terakhir per timestamp, bukan urutan baris append.

Periode Influx berbeda: 21 Oktober 06.22–19.41 WIB; 22 Oktober 12.03–17.20 WIB.
CSV 22 Oktober mulai 11.00 dan berakhir 17.11. Jumlah baris/rata-rata seluruh
periode tidak boleh dibandingkan sebagai dua rekaman yang identik.

## Temuan OFF dan energi

Function `a9da8f077ca7adc5` mengirim baris ketika tujuh topik cuaca terkumpul.
Field PZEM yang belum ada di buffer ditulis `OFF`. Karena itu **OFF tidak
membuktikan turbin berhenti**. Pengguna menyetujui: OFF menjadi data tidak
tersedia, dan nol hanya untuk bacaan numerik 0 W. Model training historis
dan flow penulis TA tidak diubah dalam pekerjaan ini.

Influx tidak mempunyai titik `turbin_on=0` pada rentang yang diperiksa. Ini
tidak langsung berarti data nol terukur hilang: beberapa OFF Sheet berasal
dari pemisahan batch cuaca/PZEM. Dengan hanya memakai daya numerik pada menit
yang sama, selisih absolut rata-rata antar-rerata menit adalah:

- 21 Oktober: **0,617 W**, pada 599 menit yang beririsan.
- 22 Oktober: **0,656 W**, pada 280 menit yang beririsan.

Ini pemeriksaan konsistensi dua pencatat, bukan galat prediksi ML. Waktu
Influx memakai kedatangan MQTT, sedangkan Sheet memakai waktu pembuatan baris.

Register energi Sheet berawal/berakhir 433→1.273 Wh pada 21 Oktober dan
1.521→1.740 Wh pada 22 Oktober. Namun setelah pengurutan/deduplikasi masih
ada 23 dan 42 langkah register negatif; Influx juga memiliki langkah negatif.
Tidak dihitung energi harian dengan rumus akhir−awal atau menjumlahkan seluruh
kenaikan positif. Perlu audit register, reset dan waktu batch tersendiri.

Bukti numerik: [audit JSON](audit-sheet-influx-2026-10-22.json).

## Penerapan Node-RED

Pembaca baru menggunakan Google Sheets node metode `get` dengan range dinamis
maksimal 15.000 baris, kemudian memilih timestamp 3 jam terakhir. Cursor baris
terbaru berasal dari hasil append yang sudah ada dan disimpan retained melalui
`WEC/history/cursor`; seed awal 326.586 berasal dari jumlah baris ekspor CSV.
Pembacaan dibatasi, bukan mengambil seluruh `Sheet1!A:M` tiap refresh browser.

Cache diperbarui saat boot, setiap 5 menit, setelah jeda akuisisi >2 menit, atau
permintaan browser bila cache >1 menit. Permintaan bersamaan digabung dan
dibatasi minimal 30 detik antar-baca. Kegagalan Sheet tidak menghentikan MQTT.

- Grafik: ringkasan per menit, sumbu 3 jam; menit tanpa nilai memakai null.
  Riwayat tidak mengubah gauge live. Data live pada menit yang sama diprioritaskan.
- ML: hanya menambah menit tertutup yang belum ada; snapshot retained dan data
  live lebih tinggi prioritasnya. Tidak mengubah SoC/evaluasi atau menerbitkan
  prediksi untuk waktu lampau. Jika riwayat memang kurang, mode celah/cadangan
  tetap mengikuti syarat mesin ML yang sudah ada.
- Data mentah turbin yang tidak pernah direkam selama Raspi mati tetap tidak
  tersedia. Riwayat dari Sheet tidak dapat menciptakan kembali data tersebut.
- Halaman TA, Turbin 2, model/bobot, firmware dan layanan Raspi tidak diubah.

Backup awal: `/tmp/wec-history-backups/history_before_20261022_104240.json`.
Pemeriksaan MQTT live: range `Sheet1!A311895:M326894`, **2.128 baris** dalam
rentang waktu, **172 menit**, **40 duplikat** dibuang. Angka berubah mengikuti
waktu. Status pembacaan tersedia di `WEC/history/status`.

Uji lokal parser WIB, OFF/missing, sort/dedup, cache, prioritas snapshot/live,
dan impor tanpa efek ke SoC/evaluasi lulus. Uji mesin Node-RED biasa, celah
data, dan PZEM diam juga lulus. Browser memuat sekitar 171 menit riwayat pada
181 posisi sumbu waktu (termasuk menit berjalan), tanpa error JavaScript.
Sesudah menunggu pesan MQTT baru, gauge menunjukkan 15,29 V / 0,46 A / 7 W;
histori tidak mengganti angka tersebut. Posisi grup editor kemudian dirapikan
agar tidak bertumpuk; backup metadata terakhir:
`/tmp/wec-history-backups/history_before_20261022_105036.json`.

Acuan: [kode Google Sheets node](https://github.com/sammachin/node-red-contrib-google-sheets/blob/master/gsheet.js),
[batas penggunaan Google Sheets API](https://developers.google.com/workspace/sheets/api/limits).
