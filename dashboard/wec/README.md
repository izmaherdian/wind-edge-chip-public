# dashboard/wec/ — Mesin ML (3 fitur) + patch dashboard Genis + digital twin 3D

Berjalan di Node-RED `citaitb.com:1880`, tab **"Turbin angin"**, grup **"Wind Edge Chip · Mesin ML"**. Tampil di dashboard Genis `http://citaitb.com:1880/dashboard`.

```
MQTT TurbinAngin/* (Raspi, tiap ±3 dtk) ──► Mesin WEC (function node) ──► template dashboard Genis
Open-Meteo (tiap jam) ─────────────────────┘        │                     prediction_1h, wec_ml, wec_live, wec_model
                                                    └──► MQTT WEC/prediksi, WEC/status, WEC/baterai (retain)
```

| Fitur | Di mesin WEC | Model |
|---|---|---|
| 2. Prediksi rata-rata daya 60 menit | tiap menit, setelah 60 menit pemanasan | MLP INT8 16-32-16-1, **identik dengan FPGA** (bit-exact) + rentang 80% empiris |
| 1. Status turbin | rasio daya aktual / daya wajar (30 menit) | MLP INT8 kurva daya (set bobot kedua FPGA) |
| 3. Baterai | simulasi SoC tiap menit + SoC 1 jam ke depan | rantai charge controller → aki 12 V 50 Ah (600 Wh, DoD 50%) → inverter; kelebihan ke dump load 35 Ω (asumsi, `ml/battery/sim_battery.py`) |

Tambahan di dashboard: panel prediksi yang dirapikan (rata-rata 1 jam, rentang 80%, akurasi live vs persistence), panel status dan baterai, serta **digital twin 3D** (three.js dari jsDelivr). Mode **Live** mengikuti angin/daya nyata; mode **Demo** memakai slider angin, kurva daya empiris, dan MLP INT8 yang sama di browser. Responsif untuk HP, tablet, dan laptop. Semua fitur Genis (gauge, CCTV, peta, grafik, log, PDF) tetap ada.

## File
| File | Isi |
|---|---|
| `engine_core.js` | Logika inti (pembersihan, agregasi 1 menit, fitur, MLP INT8, status, baterai), sama dengan Python |
| `engine_node.js` | Pembungkus Node-RED (context, keluaran ke dashboard dan MQTT) |
| `model_bundle.json` | Bobot kedua model + interval + kurva daya + asumsi baterai (`make_bundle.py`) |
| `patch_template.py` | Patch template Genis; berhenti kalau template di server sudah berubah |
| `deploy.py` | Backup → patch → tambah node `wec_*` → deploy mode "nodes"; ada `--dry-run` dan `--rollback` |
| `test/` | `test_engine.js` (kesetaraan JS = Python), `test_node.js` (simulasi node), `build_preview.py` (pratinjau Vue lokal) |

## Menjalankan ulang
```
ml/.venv/bin/python dashboard/wec/make_bundle.py              # setelah model dilatih ulang
ml/.venv/bin/python dashboard/wec/test/make_reference.py && node dashboard/wec/test/test_engine.js
NR_PASS=... ml/.venv/bin/python dashboard/wec/deploy.py --backup-dir ~/nodered-backups --dry-run
NR_PASS=... ml/.venv/bin/python dashboard/wec/deploy.py --backup-dir ~/nodered-backups
NR_PASS=... ml/.venv/bin/python dashboard/wec/deploy.py --rollback ~/nodered-backups/backup_flows_<waktu>.json   # darurat
```

Catatan:
- Riwayat disimpan di memori Node-RED. Setelah Node-RED restart, perlu 60 menit pemanasan lagi.
- Hasil uji 20 Okt: kesetaraan JS = Python 0 beda (MLP, kuantisasi, 16+16 fitur). Simulasi replay Okt: MAE live 3,3 W vs persistence 5,0 W.
- Setelah ESP32/FPGA jalan, ESP32 mengirim topik `WEC/*` sendiri dan mesin ini menjadi cadangan.

## Riwayat Google Sheets 3 jam

Halaman Hackathon membaca riwayat terukur dari Sheet untuk grafik dan menambah
menit yang belum tersedia pada mesin ML. Nilai/gauge live tetap dari MQTT;
impor riwayat tidak mengubah SoC, evaluasi atau menerbitkan prediksi historis.
Snapshot retained `WEC/state` dan data live diprioritaskan atas impor Sheet.

`deploy_history.py` mencadangkan flow dan membatasi perubahan ke template
Hackathon, handler riwayat mesin ML, serta output acknowledgement penulis Sheet.
Metode, range dan kredensial penulis tidak berubah; pembaca baru hanya `get`.
Dashboard TA dan Turbin 2 tetap menggunakan flow sebelumnya.

Pembaca memakai range maksimal 15.000 baris, mengurutkan tanggal WIB secara
eksplisit, membuang duplikat dan data di luar 3 jam terakhir. Cache disegarkan
saat boot, setiap 5 menit, setelah akuisisi kembali setelah jeda >2 menit, atau
permintaan browser bila cache lebih dari 1 menit (maksimal satu baca tiap 30
detik). Cursor baris diambil dari acknowledgement append yang sudah ada dan
disimpan retained pada `WEC/history/cursor`. `--seed-row` diperlukan pada
pemasangan pertama; nilainya baris terakhir ekspor CSV, bukan jumlah sel.

**OFF bukan nol:** flow penulis lama memakai OFF saat data PZEM belum masuk
buffer. Riwayat baru mempertahankannya sebagai data tidak tersedia. Nilai
numerik 0 tetap nol. Grafik memakai titik per menit dan null pada celah; field
energi menampilkan register terakhir yang tersedia, bukan penjumlahan register.
Status rentang aktual dan jumlah sampel tersedia di `WEC/history/status`.

```bash
NR_PASS=... python dashboard/wec/deploy_history.py \
  --seed-row 326586 --backup-dir /tmp/wec-history-backups --apply
node dashboard/wec/test_history.js
python3 dashboard/wec/test_history_panel.py
```

Deploy utama mempertahankan mekanisme ini; gunakan `--history-seed-row` pada
pemasangan pertama atau biarkan nilainya dibaca dari node yang sudah terpasang.
CSV hanya dipakai untuk audit dan seed awal; pembacaan selanjutnya langsung ke
Google Sheets. Raw CSV tidak dimasukkan git.

## Susunan editor Node-RED

Panel perangkat pada `/dashboard/hackathon` kini menampilkan **V, A, W**
sesuai permintaan terbaru setelah perbaikan ground. `power_panel.py` juga
diterapkan oleh skin utama agar tampilan tetap konsisten saat deploy ulang.
Angka hanya muncul untuk sampel valid, perangkat terpasang, dan data tidak
lebih dari 30 detik; FPGA+S3 tetap `BELUM DIPASANG` sampai kanal dayanya dipasang.
Pemetaan fisik firmware `fpga` → Raspi tetap dipertahankan. Arus/daya belum
diverifikasi alat pembanding. Deploy terbatas dengan `deploy_power.py`.

Tab **Turbin angin** dirapikan pada 21 Oktober: 68 node dalam delapan grup
(sensor Turbin 1, sensor Turbin 2, pengolahan/replay, dashboard, mesin WEC,
INA219, database/ekspor Turbin 1 dan Turbin 2). Kode, topik MQTT, wiring dan
konfigurasi runtime dipertahankan identik; tab lain tidak berubah.

`layout_flow.py` mencadangkan flow, memeriksa revisi, dan membatasi perubahan
pada metadata editor. Tanpa `--apply`, hanya menyimpan kandidat:

```bash
NR_PASS=... python dashboard/wec/layout_flow.py --backup-dir ~/nodered-backups
NR_PASS=... python dashboard/wec/layout_flow.py --backup-dir ~/nodered-backups --apply
```

Deploy utama juga menerapkan susunan ini agar posisi tidak kembali berantakan.
Backup sebelum perapian live: `~/nodered-backups/layout_before_20261021_081920.json`
(nama waktu UTC).

## Urutan mode prediksi (mesin WEC)

1. **Normal**: ≥50 dari 60 menit terakhir berisi data.
2. **Data berlubang (celah)**: syarat diturunkan ke separuh jendela (Raspi reboot singkat).
3. **Offline**: tanpa Open-Meteo, model INT8 offline.
4. **Pemulihan** (22 Okt): Raspi baru kembali setelah mati lama; cukup 3 menit data, menit kosong diisi nilai
   tertua yang ada (tanpa data masa depan). Uji Raspi mati 75 menit pada 1–20 Okt: MAE 6,04 W vs data utuh
   5,99 W dan persistence 8,73 W; prediksi muncul menit ke-3 (`node dashboard/wec/test/test_pemulihan.js`).
   Kandidat "mode cuaca" (kurva daya pada prakiraan Open-Meteo) diuji dan tidak dipakai: MAE 10,10 W, lebih buruk dari persistence.
