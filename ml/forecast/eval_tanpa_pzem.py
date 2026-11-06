"""Uji mode cadangan saat PZEM tidak merespons (data daya kosong, angin stasiun tetap ada).

Fitur daya (p_now, p_lag*, p_mean60) diganti dengan daya wajar dari MLP kurva daya (fitur 1, INT8),
lalu MLP prediksi INT8 yang sama dijalankan. Dibandingkan dengan:
  - MLP normal (fitur daya asli)
  - persistence (butuh daya asli; tidak tersedia saat PZEM diam, hanya pembanding)
  - persistence daya wajar (daya wajar sekarang sebagai prediksi 1 jam)
Data uji 1-20 Okt. Hasil: ml/results/tanpa_pzem.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "ml" / "forecast"))
sys.path.insert(0, str(ROOT / "ml" / "status"))
import features as F  # noqa: E402
import train_powercurve_mlp as PC  # noqa: E402
from golden_model import GoldenModelINT8  # noqa: E402


def run(gm, df, names):
    x = np.stack([df[n].to_numpy() for n in names], 1)
    sc = [gm.feature_scales[n] for n in names]
    xq = np.clip(np.round((x - [s["center"] for s in sc]) / [s["scale"] for s in sc]), -128, 127).astype(int)
    h = xq.astype(np.int64)
    for w, b in ((gm.w1, gm.b1), (gm.w2, gm.b2), (gm.w3, gm.b3)):   # integer, sama dengan golden_model.forward
        h = np.clip(((h @ np.array(w, dtype=np.int64) + np.array(b, dtype=np.int64)) * 32) >> 8, 0, 127)
    return h[:, 0] * gm.output_scale


def main():
    gm_fc = GoldenModelINT8(model_path=str(ROOT / "ml/forecast/model/mlp_int8.json"))
    gm_pc = GoldenModelINT8(model_path=str(ROOT / "ml/status/model/powercurve_int8.json"))
    pcf = PC.build()
    pcf = pcf[pcf.index >= F.VAL_END - pd.Timedelta(hours=3)]
    p_est = pd.Series(run(gm_pc, pcf, gm_pc.features), index=pcf.index).asfreq("1min")

    f = F.build()
    _, _, te = F.split(f)
    alt = te.copy()
    alt["p_now"] = p_est.reindex(te.index)
    for k in (5, 15, 30, 60):
        alt[f"p_lag{k}"] = p_est.shift(k).reindex(te.index)
    alt["p_mean60"] = p_est.rolling(60, min_periods=50).mean().reindex(te.index)
    ok = alt[F.FEATURES].notna().all(axis=1)
    te, alt = te[ok], alt[ok]
    y = te[F.TARGET].to_numpy()
    res = {}
    for name, pred in (("mlp_normal", run(gm_fc, te, gm_fc.features)),
                       ("mlp_cadangan_tanpa_pzem", run(gm_fc, alt, gm_fc.features)),
                       ("persistence_asli", te["p_now"].to_numpy()),
                       ("persistence_daya_wajar", alt["p_now"].to_numpy())):
        e = pred - y
        res[name] = {"MAE_W": round(float(np.mean(np.abs(e))), 3), "RMSE_W": round(float(np.sqrt(np.mean(e ** 2))), 3)}
    res["n_menit"] = int(len(y))
    print(json.dumps(res, indent=1))
    (ROOT / "ml/results/tanpa_pzem.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
