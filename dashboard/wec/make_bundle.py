"""Buat paket model untuk mesin WEC di Node-RED: dashboard/wec/model_bundle.json.

Isi:
- forecast: MLP INT8 prediksi rata-rata daya 60 menit ke depan (ml/forecast/model/mlp_int8.json)
- forecast_offline: MLP INT8 yang sama tanpa Open-Meteo (masukan ke-16 = 0; ml/forecast/model/mlp_int8_offline.json)
- powercurve: MLP INT8 kurva daya wajar untuk status (ml/status/model/powercurve_int8.json)
- interval: P10/P90 empiris daya aktual per bin prediksi, dari data VALIDASI (Agu-Sep),
  cakupannya dicek di data uji (Okt)
- battery: asumsi + kurva inverter (DC yang dibutuhkan untuk AC tertentu) dari ml/battery/sim_battery.py
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "forecast"))
sys.path.insert(0, str(ROOT / "ml" / "battery"))
from features import TARGET, build, split  # noqa: E402
from train_mlp import integer_forward, quantize_inputs  # noqa: E402
import sim_battery  # noqa: E402

sys.path.insert(0, str(ROOT / "ml" / "status"))
import train_powercurve_mlp as tpc  # noqa: E402

BINS = [0, 1, 2, 4, 7, 12, 20, 35, 60, 1e9]


def model(path):
    m = json.loads(Path(path).read_text())
    keep = ("topologi", "fitur", "skala_fitur", "skala_keluaran_W_per_lsb", "requantize", "weights", "bias", "ambang_status")
    return {k: m[k] for k in keep if k in m}


def interval_table(fc):
    _, va, te = split(build())
    params = [(np.array(w), np.array(b)) for w, b in zip(fc["weights"], fc["bias"])]
    rows, cover = [], {}
    for name, d in (("va", va), ("te", te)):
        out, _ = integer_forward(quantize_inputs(d, fc["skala_fitur"]), params)
        cover[name] = (out * fc["skala_keluaran_W_per_lsb"], d[TARGET].to_numpy())
    p, y = cover["va"]
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p >= lo) & (p < hi)
        q10, q90 = (np.quantile(y[m], [0.1, 0.9]) if m.sum() >= 30 else (np.nan, np.nan))
        rows.append({"dari": lo, "sampai": hi, "p10": round(float(q10), 2), "p90": round(float(q90), 2), "n": int(m.sum())})
    # isi bin kosong dengan tetangga terdekat
    for i, r in enumerate(rows):
        if np.isnan(r["p10"]):
            j = min((k for k in range(len(rows)) if not np.isnan(rows[k]["p10"])), key=lambda k: abs(k - i))
            r["p10"], r["p90"] = rows[j]["p10"], rows[j]["p90"]
    pt, yt = cover["te"]
    idx = np.clip(np.searchsorted(BINS, pt, side="right") - 1, 0, len(rows) - 1)
    lo = np.array([rows[i]["p10"] for i in idx]); hi = np.array([rows[i]["p90"] for i in idx])
    return rows, float(np.mean((yt >= lo) & (yt <= hi)))


def typical():
    """Nilai cadangan (median data latih) bila sensor suhu/kelembapan atau Open-Meteo kosong."""
    f = tpc.build()
    tr = f[f.index < tpc.TRAIN_END]
    return {k: float(tr[k].median()) for k in ("rho", "temp_c", "humidity_pct")}


def power_curve():
    """Rata-rata daya terukur per bin angin stasiun 0,5 m/s (untuk mode demo digital twin)."""
    import pandas as pd
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet").dropna(subset=["wind_ms", "power_w"])
    edges = np.arange(0, 8.5, 0.5)
    g = t.groupby(pd.cut(t["wind_ms"], edges), observed=False)["power_w"].mean()
    return {"angin_ms": [round(float(e + 0.25), 2) for e in edges[:-1]], "daya_W": [round(float(x), 2) if x == x else None for x in g]}


def main():
    fc = model(ROOT / "ml" / "forecast" / "model" / "mlp_int8.json")
    pc = model(ROOT / "ml" / "status" / "model" / "powercurve_int8.json")
    rows, coverage = interval_table(fc)
    dc_for_ac, inv = sim_battery.inverter_model()
    ac = np.linspace(0, 60, 61)
    bundle = {
        "dibuat": "dashboard/wec/make_bundle.py",
        "forecast": fc,
        "forecast_offline": model(ROOT / "ml" / "forecast" / "model" / "mlp_int8_offline.json"),   # tanpa Open-Meteo
        "powercurve": pc,
        "interval": {"bins": rows, "cakupan_uji_okt": round(coverage, 3), "sumber": "kuantil empiris data validasi Agu-Sep"},
        "typical": typical(),
        "kurva_daya": power_curve(),
        "battery": {**sim_battery.ASUMSI, "inverter_ac_W": ac.round(3).tolist(), "inverter_dc_W": np.round(dc_for_ac(ac), 3).tolist()},
    }
    out = Path(__file__).with_name("model_bundle.json")
    out.write_text(json.dumps(bundle))
    print(f"{out} {out.stat().st_size / 1024:.1f} KB; cakupan P10-P90 di uji: {coverage:.3f}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
