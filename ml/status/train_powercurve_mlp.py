"""Fitur 1 versi FPGA: MLP INT8 "kurva daya wajar" 16-32-16-1, aritmetika sama dengan RTL.

Model menebak daya rata-rata 10 menit terakhir yang *wajar* untuk kondisi angin/udara
saat ini, tanpa memakai daya itu sendiri sebagai input. Status turbin ditentukan dari
rasio daya aktual / daya wajar (rata-rata 30 menit), dengan ambang dari data validasi:
  rasio < ambang bawah → "Di bawah normal", > ambang atas → "Di atas normal (cek sensor)".

Karena topologi dan aritmetikanya sama dengan model prediksi (fitur 2), model ini bisa
dijalankan akselerator MAC4 yang sama sebagai set bobot kedua (lihat docs/usulan-rtl-dua-model.md).
Keluaran: ml/status/model/powercurve_int8.json + export/ (hex, test vector).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "forecast"))
from features import air_density  # noqa: E402
from metrics import scores  # noqa: E402
from train_mlp import IntMLP, fit, integer_forward  # noqa: E402

MODEL_DIR = ROOT / "ml" / "status" / "model"
RESULTS = ROOT / "ml" / "results"
SEED = 11
FEATURES_PC = [
    "w_now", "w_mean10", "w_mean30", "w_mean60", "w3_mean10", "w3_mean30", "w_max10", "w_std10",
    "dir_sin", "dir_cos", "hour_sin", "hour_cos", "rho", "humidity_pct", "temp_c", "om_wind_now",
]
SIGNED = {"dir_sin", "dir_cos", "hour_sin", "hour_cos", "rho", "temp_c", "humidity_pct"}
TARGET = "p_mean10"
TRAIN_END, VAL_END = pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")


def build():
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    w = t["wind_ms"]
    f = pd.DataFrame(index=t.index)
    f["w_now"] = w
    for k in (10, 30, 60):
        f[f"w_mean{k}"] = w.rolling(k, min_periods=int(0.8 * k)).mean()
    f["w3_mean10"] = (w**3).rolling(10, min_periods=8).mean()
    f["w3_mean30"] = (w**3).rolling(30, min_periods=24).mean()
    f["w_max10"] = t["wind_max_ms"].rolling(10, min_periods=8).max()
    f["w_std10"] = w.rolling(10, min_periods=8).std()
    s, c = t["dir_sin"].rolling(10, min_periods=5).mean(), t["dir_cos"].rolling(10, min_periods=5).mean()
    n = np.hypot(s, c).replace(0, np.nan)
    f["dir_sin"], f["dir_cos"] = (s / n).fillna(0.0), (c / n).fillna(0.0)
    hour = (t.index.tz_convert("Asia/Jakarta").hour + t.index.minute / 60).to_numpy()
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    om = pd.read_parquet(ROOT / "data" / "external" / "openmeteo_forecast.parquet").resample("1min").interpolate("time").reindex(t.index)
    temp = t["temp_c"].rolling(30, min_periods=1).mean().ffill(limit=180)
    rh = t["humidity_pct"].rolling(30, min_periods=1).mean().ffill(limit=180)
    f["temp_c"] = temp.fillna(temp.median())
    f["humidity_pct"] = rh.fillna(rh.median())
    rho = air_density(temp, rh, om["om_surface_pressure"])
    f["rho"] = rho.fillna(rho.median())
    f["om_wind_now"] = om["om_wind_speed_10m"]
    f[TARGET] = t["power_w"].rolling(10, min_periods=8).mean()
    seg = t["segmen"]
    same = seg.rolling(61, min_periods=1).min() == seg.rolling(61, min_periods=1).max()
    ok = same & seg.notna() & f[FEATURES_PC + [TARGET]].notna().all(axis=1)
    return f[ok]


def scales(train):
    table = {}
    for name in FEATURES_PC:
        x = train[name].to_numpy()
        if name in ("rho", "temp_c", "humidity_pct"):
            table[name] = {"center": float(np.mean(x)), "scale": float(4 * np.std(x) / 127)}
        elif name in SIGNED:
            table[name] = {"center": 0.0, "scale": 1 / 127}
        else:
            table[name] = {"center": 0.0, "scale": float(np.quantile(x, 0.999) / 127)}
    return table


def quantize(df, table):
    x = np.stack([(df[n].to_numpy() - table[n]["center"]) / table[n]["scale"] for n in FEATURES_PC], 1)
    return np.clip(np.round(x), -128, 127).astype(np.int64)


def ratio(actual, expected, index, win=30):
    a = pd.Series(actual, index=index).rolling(win, min_periods=win // 3).mean()
    e = pd.Series(expected, index=index).rolling(win, min_periods=win // 3).mean()
    return (a / e).where(e > 5.0)


def main():
    torch.manual_seed(SEED)
    f = build()
    tr, va, te = f[f.index < TRAIN_END], f[(f.index >= TRAIN_END) & (f.index < VAL_END)], f[f.index >= VAL_END]
    table = scales(tr)
    s_y = float(np.quantile(tr[TARGET], 0.999) / 127)
    xq = {k: quantize(d, table) for k, d in (("tr", tr), ("va", va), ("te", te))}
    tq = lambda a: torch.tensor(a, dtype=torch.float32)
    yq = {k: torch.tensor(np.clip(d[TARGET].to_numpy() / s_y, 0, 127), dtype=torch.float32) for k, d in (("tr", tr), ("va", va), ("te", te))}
    m = IntMLP(x_rms=float(np.sqrt(np.mean(xq["tr"].astype(float) ** 2))))
    fit(m, tq(xq["tr"]), yq["tr"], tq(xq["va"]), yq["va"], epochs=30, lr=5e-2)
    m.quant = True
    fit(m, tq(xq["tr"]), yq["tr"], tq(xq["va"]), yq["va"], epochs=30, lr=1e-2)
    params = m.integer_params()
    out = {k: integer_forward(xq[k], params)[0] for k in ("va", "te")}
    with torch.no_grad():
        mismatch = int(np.sum(np.round(m(tq(xq["te"])).numpy()).astype(int) != out["te"]))

    # ambang rasio dari validasi (alarm palsu ±1% di tiap sisi)
    r_va = ratio(va[TARGET].to_numpy(), out["va"] * s_y, va.index).dropna()
    lo, hi = float(r_va.quantile(0.01)), float(r_va.quantile(0.99))

    # uji kerusakan buatan di data Okt: daya dikali faktor selama 30 menit
    rng = np.random.default_rng(1)
    p = te[TARGET].to_numpy().copy()
    on = np.flatnonzero(pd.Series(p).rolling(30).mean().shift(-29).to_numpy() > 5)
    sweep = []
    for gain in (0.2, 0.4, 0.6):
        starts = []
        for s in rng.permutation(on):
            if all(abs(s - x) > 60 for x in starts):
                starts.append(s)
            if len(starts) == 40:
                break
        pf = p.copy()
        fault = np.zeros(len(p), bool)
        for s in starts:
            pf[s:s + 30] *= gain
            fault[s:s + 30] = True
        flag = (ratio(pf, out["te"] * s_y, te.index) < lo).fillna(False).to_numpy()
        hit = np.mean([flag[s:s + 30].mean() >= 0.3 for s in starts])
        fa = float(flag[~fault & (p > 5)].mean())
        sweep.append({"daya_tersisa": gain, "recall_jendela": round(float(hit), 3), "alarm_palsu": round(fa, 4)})

    res = {
        "fitur": FEATURES_PC,
        "test_kurva_daya": scores(te[TARGET], out["te"] * s_y),
        "beda_pytorch_vs_integer": mismatch,
        "ambang_rasio": [round(lo, 3), round(hi, 3)],
        "uji_kerusakan_30_menit": sweep,
        "max_abs_bobot": [int(np.abs(w).max()) for w, _ in params],
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model = {
        "topologi": [16, 32, 16, 1], "tugas": "kurva daya wajar (rata-rata daya 10 menit terakhir) untuk status turbin",
        "fitur": FEATURES_PC, "skala_fitur": table, "skala_keluaran_W_per_lsb": s_y,
        "requantize": {"multiplier": 32, "shift": 8, "relu_clamp": [0, 127]},
        "ambang_status": {"bawah": lo, "atas": hi, "jendela_menit": 30, "min_daya_wajar_W": 5.0},
        "weights": [w.tolist() for w, _ in params], "bias": [b.tolist() for _, b in params],
    }
    (MODEL_DIR / "powercurve_int8.json").write_text(json.dumps(model, indent=1))
    np.savez(MODEL_DIR / "test_set_int8.npz", x_q=xq["te"], out_q=out["te"], y_true_w=te[TARGET].to_numpy())
    (RESULTS / "status_mlp_int8.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
