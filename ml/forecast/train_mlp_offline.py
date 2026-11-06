"""MLP INT8 mode offline: dipakai bila prakiraan Open-Meteo tidak tersedia (internet putus > 3 hari).

Topologi, aritmetika RTL, dan 16 masukan sama dengan model utama (train_mlp.py), sehingga kontrak
ESP32 <-> FPGA tidak berubah; masukan ke-16 (om_wind_next) selalu 0. Skala fitur memakai tabel
model utama, jadi ESP32/Node-RED cukup mengganti bobot.

Dibandingkan pada menit uji yang sama (1-20 Okt) dengan:
  - model utama (butuh Open-Meteo)
  - model utama dengan om_wind_next = 0 (salah pakai: tanpa model offline)
  - persistence

Keluaran: ml/forecast/model/mlp_int8_offline.json, ml/results/mlp_offline.json
Pemakaian: ml/.venv/bin/python ml/forecast/train_mlp_offline.py
"""

import json

import numpy as np
import torch

import train_mlp as T
from features import FEATURES, TARGET, build, split
from metrics import scores


def main():
    torch.manual_seed(T.SEED)
    np.random.seed(T.SEED)
    utama = json.loads((T.MODEL_DIR / "mlp_int8.json").read_text())
    table = utama["skala_fitur"]
    s_y = utama["skala_keluaran_W_per_lsb"]
    p_utama = [(np.array(w), np.array(b)) for w, b in zip(utama["weights"], utama["bias"])]

    # data latih offline: tanpa syarat Open-Meteo (lebih banyak menit), om_wind_next = 0
    tr, va, te_off = split(build(with_openmeteo=False))
    for d in (tr, va, te_off):
        d["om_wind_next"] = 0.0
    xq = {k: T.quantize_inputs(d, table) for k, d in (("tr", tr), ("va", va))}
    tq = lambda a: torch.tensor(a, dtype=torch.float32)
    y_q = {k: torch.tensor(np.clip(d[TARGET].to_numpy() / s_y, 0, 127), dtype=torch.float32) for k, d in (("tr", tr), ("va", va))}
    im = T.IntMLP(x_rms=float(np.sqrt(np.mean(xq["tr"].astype(float) ** 2))))
    T.fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=5e-2)
    im.quant = True
    T.fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=1e-2)
    params = im.integer_params()

    # uji pada menit yang sama dengan model utama (yang punya Open-Meteo)
    _, _, te = split(build())
    xq_on = T.quantize_inputs(te, table)
    te0 = te.copy(); te0["om_wind_next"] = 0.0
    xq_off = T.quantize_inputs(te0, table)
    y = te[TARGET].to_numpy()
    out_on, _ = T.integer_forward(xq_on, p_utama)
    out_salah, _ = T.integer_forward(xq_off, p_utama)
    out_off, hid = T.integer_forward(xq_off, params)
    with torch.no_grad():
        mismatch = int(np.sum(np.round(im(tq(xq_off)).numpy()).astype(int) != out_off))
    res = {
        "n_menit_uji": int(len(y)),
        "model_utama_dengan_open_meteo": scores(y, out_on * s_y, te["p_now"]),
        "model_offline_tanpa_open_meteo": scores(y, out_off * s_y, te["p_now"]),
        "model_utama_om_0_tanpa_model_offline": scores(y, out_salah * s_y, te["p_now"]),
        "persistence": scores(y, te["p_now"].to_numpy(), te["p_now"]),
        "beda_pytorch_vs_integer": mismatch,
        "menit_latih": int(len(tr)),
    }
    model = dict(utama)
    model.update({"tugas": "prediksi rata-rata daya 60 menit ke depan, MODE OFFLINE (om_wind_next = 0)",
                  "weights": [w.tolist() for w, _ in params], "bias": [b.tolist() for _, b in params],
                  "info": {"max_abs_bobot_per_lapisan": [int(np.abs(w).max()) for w, _ in params],
                           "fraksi_saturasi_127_test": [float(np.mean(h == 127)) for h in hid],
                           "catatan": "masukan ke-16 (om_wind_next) selalu 0; skala fitur sama dengan mlp_int8.json"}})
    (T.MODEL_DIR / "mlp_int8_offline.json").write_text(json.dumps(model, indent=1))
    (T.RESULTS / "mlp_offline.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    for k, v in res.items():
        if isinstance(v, dict):
            print(f"{k:40s} MAE {v['MAE_W']:6.2f}  RMSE {v['RMSE_W']:6.2f}  skill {v['skill_vs_persistence']:+.3f}")
    print("menit uji", res["n_menit_uji"], "| beda PyTorch vs integer", mismatch)


if __name__ == "__main__":
    main()
