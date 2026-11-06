# ml/ — Model AI

> Branch `feature/ml` berisi jalur ML lengkap. Yang dibawa ke `main` hanya hasil ekspor (`*/model/export/`, `*.json`), `golden_model.py`, dan `requirements.txt`; setelah melatih ulang, bawa file itu ke `main`.

Pemilik: Izma. Branch kerja: `feature/ml`.

| Folder | Fitur | Isi |
|---|---|---|
| `common/` | bersama | `preprocess.py` (CSV mentah → 1 menit), `fetch_openmeteo.py`, `fetch_bmkg.py` (logger, jalankan tiap 3 jam) |
| `forecast/` | **2. Prediksi rata-rata daya 60 menit ke depan** | `features.py` (16 fitur), `baselines.py`, `train_mlp.py` (float + INT8 QAT identik RTL), `export.py`, `benchmark.py` (36 metode) |
| `status/` | 1. Status turbin | `reproduce_ta.py` (SVM TA), `improved.py`, `anomaly.py` (kurva daya kuantil) |
| `battery/` | 3. Setelah inverter/baterai | `sim_battery.py` (simulasi; lihat `docs/kajian-inverter-baterai.md`) |
| `results/` | | hasil JSON/CSV + `plot_data.py` (data grafik laporan dan deck) |
| `golden_model.py` | | golden model integer (interface sama dengan versi Alif); otomatis memuat `forecast/model/mlp_int8.json` |
| `ta/` | | program TA asli dan model SVM dari Raspi (tidak diubah) |

Keluaran untuk tim: `forecast/model/export/` (`weights.hex`, `weights32.hex`, `bias.hex`, `test_vectors.csv`, `mlp_int8.h`, `mlp_float_int8.tflite`). Skala fitur: `docs/kontrak-kuantisasi.md`.

## Menjalankan
```
uv venv --python 3.12 ml/.venv
uv pip install --python ml/.venv -r ml/requirements.txt --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cpu
ml/.venv/bin/python ml/common/preprocess.py
ml/.venv/bin/python ml/common/fetch_openmeteo.py
cd ml/forecast
../.venv/bin/python baselines.py
../.venv/bin/python train_mlp.py && ../.venv/bin/python export.py
../.venv/bin/python benchmark.py          # ±25 menit (CPU 6 inti); --cepat melewati model sekuensial
cd ../.. && ml/.venv/bin/python ml/status/reproduce_ta.py && ml/.venv/bin/python ml/status/improved.py && ml/.venv/bin/python ml/status/anomaly.py
ml/.venv/bin/python ml/battery/sim_battery.py && ml/.venv/bin/python ml/results/plot_data.py
```

## Aturan
- Pembagian data latih/validasi/uji berdasarkan waktu (latih ≤ Jul, validasi Agu–Sep, uji 1–20 Okt), bukan acak.
- Setiap model dibandingkan dengan baseline persistence.
- Waktu dalam UTC; satuan ditulis di nama kolom (`power_w`, `wind_ms`).
- Perubahan format bobot atau skala → perbarui `docs/kontrak-kuantisasi.md`.
