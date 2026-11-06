# Database InfluxDB (demo di laptop)

InfluxDB 2.7 lokal untuk menyimpan data turbin dan hasil ML. Berjalan paralel dengan Google Sheets milik Genis (Sheets tidak diubah). Batas Sheets 10 juta sel; Influx tidak punya batas itu dan bisa di-query per waktu.

```
Raspi --MQTT--> citaitb.com:1883 --+--> Node-RED (Sheets, dashboard, mesin ML -> WEC/*)
                                   +--> mqtt_to_influx.py (laptop) --> InfluxDB 127.0.0.1:8086
data/processed + ml/results --import_history.py--> InfluxDB
```

## Isi

| Bucket | Measurement | Sumber | Isi |
|---|---|---|---|
| `turbin` | `turbin_1min` | `data/processed/turbine_1min.parquet` | 181.228 menit (30 Mar–20 Okt), tag `turbin=1`, `sumber=historis` |
| `turbin` | `turbin_live` | MQTT `TurbinAngin/#`, `TurbinAngin2/#` | satu titik per batch Raspi (±5 detik), tag `turbin=1|2` |
| `wec` | `prediksi_uji` | `ml/results/prediksi_test.parquet` + `ml/forecast/model/test_set_int8.npz` | 1–20 Okt: aktual, MLP INT8 (= FPGA), persistence, Transformer, P10/P50/P90 |
| `wec` | `baterai_sim` | `ml/results/baterai_simulasi.parquet` | SoC dan aliran energi simulasi aki 12 V 50 Ah (600 Wh; sebelum 22 Okt: 384 Wh) |
| `wec` | `wec_prediksi`, `wec_status`, `wec_baterai` | MQTT `WEC/*` (mesin ML Node-RED) | hasil live tiap menit |

Aturan `turbin_live` sama dengan preprocessing: `OFF` → `turbin_on=0`, daya 0 W; arah `-115` → kosong. Nama field: `power_w`, `voltage_v`, `current_a`, `energy_wh`, `wind_ms` (stasiun), `wind_arduino_ms`, `dir_deg`, `humidity_pct`, `temp_c`, `noise_db`, `rain_mm`, `ml_status`.

## Pemakaian

Kredensial ada di `~/.config/wind-edge-chip/influx.env` (`INFLUX_URL`, `INFLUX_ORG`, `INFLUX_TOKEN`, `INFLUX_USER`, `INFLUX_PASSWORD`; chmod 600, tidak masuk repo; minta ke Izma). InfluxDB terpasang di `~/tools/influxdb`.

```bash
dashboard/db/start.sh                                  # nyalakan influxd + subscriber MQTT (aman diulang)
ml/.venv/bin/python dashboard/db/import_history.py     # impor historis + hasil ML (aman diulang, titik sama ditimpa)
dashboard/db/apply_dashboard.sh                        # pasang/perbarui dashboard dari dashboard.yml
dashboard/db/start.sh stop                             # matikan keduanya
```

Buka `http://127.0.0.1:8086` → login → **Dashboards → Wind Edge Chip · Turbin 1**. Log: `~/tools/influxdb/data/influxd.log` dan `mqtt_to_influx.log`.

Subscriber hanya merekam saat laptop menyala; data saat laptop mati tetap ada di Google Sheets.

**Peran database (keputusan tim 22 Okt 2026):** Google Sheets milik Genis tetap menjadi database dashboard (riwayat
`/dashboard` dibaca node "Baca Database GSheet"); InfluxDB laptop dipakai untuk analisis dan pengecekan. Untuk produk,
InfluxDB atau PostgreSQL dipindah ke server `citaitb.com` (node `influxdb` dan `postgresql` sudah terpasang di Node-RED),
perlu izin pengelola server. Seri `baterai_sim` lama bertag `kapasitas=384Wh`; impor ulang menulis seri baru `600Wh` (aki 12 V 50 Ah).

## Cek cepat

MAE uji 1–20 Okt dihitung langsung di Flux (panel tabel) dan sama dengan `ml/results/mlp.json`: MLP INT8 5,48 W, Transformer 5,70 W, persistence 8,67 W (16.255 menit).
