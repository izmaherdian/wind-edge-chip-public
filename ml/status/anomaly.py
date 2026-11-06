"""Pendekatan baru: deteksi kinerja turbin dari kurva daya yang dipelajari.

Model kuantil (LightGBM P10/P50/P90) memperkirakan daya yang *wajar* untuk kondisi
angin saat ini (angin, rata-rata 10 menit, ρ, arah, jam). Status ditentukan dari rasio
daya aktual terhadap daya harapan P50, keduanya dirata-rata 30 menit:
  rasio < ambang bawah → "Di bawah normal", rasio > ambang atas → "Di atas normal (cek sensor)",
  selain itu "Normal". Ambang dikalibrasi pada data validasi (Agu–Sep) untuk alarm palsu ±1%.
Tidak bergantung ambang Cp dan tetap berarti saat angin lemah.

Evaluasi: kerusakan buatan disisipkan ke data uji (Okt): jendela 30 menit saat turbin
menghasilkan (rata-rata > 5 W), daya dikalikan 0,6 (degradasi 40%). Diukur deteksi (recall) dan alarm palsu.
"""

import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forecast"))
from features import air_density  # noqa: E402

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ml" / "results"
AREA = np.pi * 1.25**2
PRESSURE_HPA = 1013.25 * (1 - 2.25577e-5 * 768) ** 5.25588
FEATS = ["wind_ms", "w_mean10", "rho", "dir_sin", "dir_cos", "hour_sin", "hour_cos"]
N_FAULT, FAULT_LEN, FAULT_GAIN, MIN_EXPECTED_W = 40, 30, 0.6, 5.0


def load():
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    t = t[t["n_sampel"] > 0].copy()
    t["w_mean10"] = t["wind_ms"].rolling(10, min_periods=5).mean()
    t["rho"] = air_density(t["temp_c"].fillna(t["temp_c"].median()), t["humidity_pct"], PRESSURE_HPA)
    hour = t.index.tz_convert("Asia/Jakarta").hour + t.index.minute / 60
    t["hour_sin"], t["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    t[["dir_sin", "dir_cos"]] = t[["dir_sin", "dir_cos"]].fillna(0)
    return t.dropna(subset=FEATS + ["power_w"])


def inject(te, rng, length=None, gain=None):
    length, gain = length or FAULT_LEN, gain or FAULT_GAIN
    te = te.copy()
    te["fault"] = False
    on = np.flatnonzero((te["power_w"].rolling(length).mean().shift(-length + 1) > 5).to_numpy())
    starts = []
    for s in rng.permutation(on):
        if all(abs(s - x) > 2 * length for x in starts):
            starts.append(s)
        if len(starts) == N_FAULT:
            break
    for s in starts:
        idx = te.index[s:s + length]
        te.loc[idx, "power_w"] *= gain
        te.loc[idx, "fault"] = True
    return te, starts


def window_scores(flag, te, starts, length=FAULT_LEN):
    """Deteksi per jendela: jendela rusak terdeteksi bila ≥ 30% menitnya ditandai."""
    f = flag.to_numpy()
    hit = [f[s:s + length].mean() >= 0.3 for s in starts]
    clean = ~te["fault"].to_numpy()
    onmask = te["power_w"].to_numpy() > 5
    return {"recall_jendela_rusak": round(float(np.mean(hit)), 3),
            "alarm_palsu_menit_normal_turbin_on": round(float(f[clean & onmask].mean()), 4)}


def ratio(power, expected, index, win=30):
    a = pd.Series(power, index=index).rolling(win, min_periods=win // 3).mean()
    e = pd.Series(expected, index=index).rolling(win, min_periods=win // 3).mean()
    return (a / e).where(e > MIN_EXPECTED_W)


def main():
    rng = np.random.default_rng(0)
    t = load()
    tr = t[t.index < pd.Timestamp("2026-08-01", tz="UTC")]
    va = t[(t.index >= pd.Timestamp("2026-08-01", tz="UTC")) & (t.index < pd.Timestamp("2026-10-01", tz="UTC"))]
    te = t[t.index >= pd.Timestamp("2026-10-01", tz="UTC")]
    te, starts = inject(te, rng)

    q = {}
    for a in (0.1, 0.5, 0.9):
        m = lgb.LGBMRegressor(objective="quantile", alpha=a, n_estimators=400, learning_rate=0.05,
                              num_leaves=31, verbose=-1, random_state=0)
        m.fit(tr[FEATS], tr["power_w"])
        q[a] = m
    # kalibrasi ambang pada validasi bersih: alarm palsu ±1% di bawah dan di atas
    r_va = ratio(va["power_w"], q[0.5].predict(va[FEATS]), va.index).dropna()
    lo, hi = float(r_va.quantile(0.01)), float(r_va.quantile(0.99))
    p = te["power_w"].to_numpy()
    e50 = q[0.5].predict(te[FEATS])
    r = ratio(p, e50, te.index)
    below, above = (r < lo).fillna(False), (r > hi).fillna(False)
    status = np.where(below, "Di bawah normal", np.where(above, "Di atas normal (cek sensor)", "Normal"))
    clean = ~te["fault"].to_numpy()
    p10, p90 = q[0.1].predict(te[FEATS]), q[0.9].predict(te[FEATS])
    cover = float(np.mean((p[clean] >= p10[clean]) & (p[clean] <= p90[clean])))

    # pembanding 1: aturan Cp < 0,10 (Inefisien), rata-rata 30 menit, hanya saat angin >= 1,5 m/s
    cp = te["power_w"] / (0.5 * te["rho"] * AREA * te["wind_ms"].clip(lower=0.5) ** 3)
    cp_flag = (pd.Series((cp < 0.10) & (te["wind_ms"] >= 1.5), index=te.index).rolling(30, min_periods=10).mean() > 0.5)
    # pembanding 2: Isolation Forest pada (angin, daya)
    iso = IsolationForest(n_estimators=200, contamination=0.01, random_state=0)
    iso.fit(tr[["wind_ms", "w_mean10", "power_w"]])
    iso_flag = pd.Series(iso.predict(te[["wind_ms", "w_mean10", "power_w"]]) == -1, index=te.index).rolling(30, min_periods=10).mean() > 0.5

    res = {
        "kerusakan_buatan": {"jendela": len(starts), "panjang_menit": FAULT_LEN, "faktor_daya": FAULT_GAIN},
        "ambang_rasio": [round(lo, 3), round(hi, 3)],
        "cakupan_P10_P90_data_normal": round(cover, 3),
        "MAE_P50_W_data_normal": round(float(np.mean(np.abs(p[clean] - e50[clean]))), 2),
        "distribusi_status_test": pd.Series(status).value_counts(normalize=True).round(3).to_dict(),
        "metode": {
            "Kurva daya kuantil (baru)": window_scores(below, te, starts),
            "Aturan Cp < 0,10 (gaya TA)": window_scores(cp_flag, te, starts),
            "Isolation Forest": window_scores(iso_flag, te, starts),
        },
    }
    # sapuan: kerusakan seberapa besar & selama apa yang bisa dideteksi (alarm palsu ±1%)
    te0 = t[t.index >= pd.Timestamp("2026-10-01", tz="UTC")]
    sweep = []
    for win in (30, 120, 360):
        r_va = ratio(va["power_w"], q[0.5].predict(va[FEATS]), va.index, win).dropna()
        lo_w = float(r_va.quantile(0.01))
        for gain in (0.2, 0.4, 0.6, 0.8):
            tf, st = inject(te0, np.random.default_rng(1), win, gain)
            fl = (ratio(tf["power_w"], q[0.5].predict(tf[FEATS]), tf.index, win) < lo_w).fillna(False)
            sc = window_scores(fl, tf, st, win)
            sweep.append({"jendela_menit": win, "daya_tersisa": gain, "n_jendela": len(st), "ambang": round(lo_w, 3), **sc})
    res["sapuan_deteksi"] = sweep
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "status_anomali.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
