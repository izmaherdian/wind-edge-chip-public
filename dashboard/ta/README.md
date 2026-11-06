# dashboard/ta/ — Flow Node-RED dari TA

`node-red-flow.json`: tab **"Turbin angin"** beserta node config yang dipakainya (77 node). Diekspor ulang 21 Okt 2026 dengan `NR_PASS=... ml/.venv/bin/python dashboard/ta/export_flow.py` (Admin API, token baca-saja; credentials tidak ikut). Sudah memuat node `wec_*` (mesin ML, halaman `/dashboard/hackathon`); node itu dikelola `dashboard/wec/deploy.py`, jangan diedit manual. Template Genis (`ECharts Neon Component`) identik dengan aslinya. Catatan: sandi cetak PDF di template diperiksa di browser, jadi bisa dibaca siapa pun yang membuka halaman.

## Server
- Node-RED 4.0.5 di `citaitb.com` (port 1880 editor, 1883 MQTT). Login editor: minta ke tim.
- **Server ini dipakai bersama** proyek lain (9 tab: ServerSITH24, Weather Station 0–2, BE4001, Smart Screenhouse, PostgreSQL, …). Hati-hati saat Deploy: pakai "Modified Flows", jangan "Full".
- Modul terpasang yang relevan: `@flowfuse/node-red-dashboard` 1.29.0, `node-red-contrib-google-sheets`, `node-red-contrib-influxdb`, `node-red-contrib-postgresql`.

## Isi tab "Turbin angin"
```
Raspi (NodeRED_DuaData.py) ──MQTT TurbinAngin/*  (12 topik)──┐
Raspi (turbine2.py)        ──MQTT TurbinAngin2/* (6 topik) ──┤
                                                             ▼
                        mqtt in ×18 ──► "Gabung data" (buffer flow context)
                                          │  baris lengkap
                                          ▼
                                   GSheet append  ──► Google Sheets
                        mqtt in ──► "Penyatu Data" ──► "Storage & Replay Manager" ──► Dashboard 2.0
                 Dashboard minta riwayat ──► "Baca Database GSheet" ──► "Filter Data" ──┘
```

| Bagian | Detail |
|---|---|
| Topik Turbin 1 | `TurbinAngin/` + `voltage`, `current`, `power`, `energy`, `Windspeed`, `windspeedstation`, `winddirdeg`, `temperature`, `humidity`, `noise`, `rainfall`, `ML_Status` |
| Topik Turbin 2 | `TurbinAngin2/` + `voltage`, `current`, `power`, `energy`, `Windspeed`, `ML_Status` |
| Sheet Turbin 1 | `<SHEET_ID>`, `Sheet1!A:M` (kolom A waktu … M ML_Status) |
| Sheet Turbin 2 | `<SHEET_ID>`, `Sheet1!A:G` |
| Timestamp | Dibuat oleh server Node-RED saat baris ditulis, format `D/M/YYYY, HH.MM.SS` (WIB) |
| Dashboard | `http://citaitb.com:1880/dashboard` (MONITORING CITA ITB), `/kontrol` (Analys), `/about` |

Ekspor ini tidak membawa kredensial: akun layanan Google (`gauth`) dan login MQTT harus diisi ulang setelah impor.

## Mengunduh data tanpa merusaknya
Unduh langsung dari Google Sheets sebagai CSV (File → Download → Comma-separated values). **Jangan buka atau simpan lewat Excel**, karena angka desimal seperti `17.9` bisa berubah jadi tanggal (lihat `data/README.md`).

Cara impor: Node-RED → menu → Import → pilih file ini.
