"""Data rujukan dari Python untuk dashboard/wec/test/test_engine.js (tidak masuk git; dibuat ulang kapan saja)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "forecast")); sys.path.insert(0, str(ROOT / "ml" / "status"))
from features import FEATURES, build, split
from train_mlp import quantize_inputs
import train_powercurve_mlp as tpc
OUT = Path(__file__).with_name("ref"); OUT.mkdir(exist_ok=True)
b = json.load(open(ROOT / "dashboard" / "wec" / "model_bundle.json"))
_, _, te = split(build())
pcf = tpc.build(); pte = pcf[pcf.index >= tpc.VAL_END]
common = te.index.intersection(pte.index)
sel = common[np.random.default_rng(0).choice(len(common), 400, replace=False)]
xq_fc = quantize_inputs(te.loc[sel], b["forecast"]["skala_fitur"])
xq_pc = tpc.quantize(pte.loc[sel], b["powercurve"]["skala_fitur"])
rows = [{"t": int(t.value // 10**6), "fc": te.loc[t, FEATURES].astype(float).to_dict(), "pc": pte.loc[t, tpc.FEATURES_PC].astype(float).to_dict(),
         "xq_fc": xq_fc[k].tolist(), "xq_pc": xq_pc[k].tolist(), "p_mean10": float(pte.loc[t, "p_mean10"])} for k, t in enumerate(sel)]
json.dump(rows, open(OUT / "features.json", "w"))
t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
t = t[t.index >= pd.Timestamp("2026-09-29", tz="UTC")]
mins = [{"m": int(i.value // 60_000_000_000), "p": r.power_w, "on": r.turbin_on, "ws": r.wind_ms, "wsMax": r.wind_max_ms, "ds": r.dir_sin, "dc": r.dir_cos,
         "rh": r.humidity_pct, "tc": r.temp_c} for i, r in t[t.n_sampel > 0].iterrows()]
json.dump(mins, open(OUT / "minutes.json", "w"), allow_nan=True)
om = pd.read_parquet(ROOT / "data" / "external" / "openmeteo_forecast.parquet")
json.dump({"time": [int(x.value // 10**6) for x in om.index], "wind": om["om_wind_speed_10m"].tolist(), "pressure": om["om_surface_pressure"].tolist()}, open(OUT / "om.json", "w"))
print(len(rows), "sampel fitur,", len(mins), "menit")
