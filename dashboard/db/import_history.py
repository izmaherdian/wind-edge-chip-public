"""Impor data historis + hasil ML ke InfluxDB lokal (sekali jalan; aman diulang karena titik yang sama ditimpa).

  bucket turbin : turbin_1min   (data/processed/turbine_1min.parquet, menit tanpa sampel dilewati)
  bucket wec    : prediksi_uji  (periode uji 1-20 Okt: aktual, MLP INT8 = FPGA, persistence, Transformer, P10/P50/P90)
                  baterai_sim   (ml/results/baterai_simulasi.parquet)

Pemakaian: ml/.venv/bin/python dashboard/db/import_history.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from influx_io import Writer, line  # noqa: E402


def ts(index):
    return (index.astype("int64") // 10**9).to_numpy()


def turbin():
    d = pd.read_parquet(ROOT / "data/processed/turbine_1min.parquet")
    d = d[d["n_sampel"] > 0]
    cols = ["power_w", "power_max_w", "voltage_v", "current_a", "turbin_on", "wind_ms", "wind_max_ms",
            "dir_sin", "dir_cos", "humidity_pct", "temp_c"]
    out = []
    for t, row, n, seg in zip(ts(d.index), d[cols].to_numpy(), d["n_sampel"].to_numpy(), d["segmen"].to_numpy()):
        f = {c: float(v) for c, v in zip(cols, row)}
        f["n_sampel"] = int(n)
        if np.isfinite(seg):
            f["segmen"] = int(seg)
        out.append(line("turbin_1min", {"turbin": "1", "sumber": "historis"}, f, t))
    return out


def prediksi():
    p = pd.read_parquet(ROOT / "ml/results/prediksi_test.parquet")
    z = np.load(ROOT / "ml/forecast/model/test_set_int8.npz")
    s_y = json.loads((ROOT / "ml/forecast/model/mlp_int8.json").read_text())["skala_keluaran_W_per_lsb"]
    int8 = pd.Series(z["out_q"] * s_y, index=pd.to_datetime(z["time"], utc=True))
    p = p.join(int8.rename("int8"), how="left")
    pick = {"aktual_w": "y", "p_sekarang_w": "p_now", "mlp_int8_w": "int8", "persistence_w": "persistence (P sekarang)",
            "transformer_w": "Transformer", "p10_w": "P10", "p50_w": "P50", "p90_w": "P90"}
    out = []
    for t, row in zip(ts(p.index), p[list(pick.values())].astype(float).to_numpy()):
        out.append(line("prediksi_uji", {"horizon": "60m"}, dict(zip(pick, map(float, row))), t))
    return out


def baterai():
    b = pd.read_parquet(ROOT / "ml/results/baterai_simulasi.parquet")
    kap = json.loads((ROOT / "ml/results/baterai_simulasi.json").read_text())["asumsi"]["kapasitas_Wh"]
    out = []
    for t, (soc, tb, dmp, grid, load) in zip(ts(b.index), b[["soc", "to_batt_Wh", "dumped_Wh", "grid_Wh", "load_W"]].to_numpy()):
        out.append(line("baterai_sim", {"kapasitas": f"{kap:.0f}Wh"},
                        {"soc_pct": float(soc) * 100, "ke_baterai_wh": float(tb), "dibuang_wh": float(dmp),
                         "pln_wh": float(grid), "beban_w": float(load)}, t))
    return out


if __name__ == "__main__":
    n = Writer("turbin").write(turbin())
    print(f"turbin_1min : {n} titik")
    w = Writer("wec")
    print(f"prediksi_uji: {w.write(prediksi())} titik")
    print(f"baterai_sim : {w.write(baterai())} titik")
