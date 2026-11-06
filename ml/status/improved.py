"""Klasifikasi status turbin versi perbaikan.

Beda dengan TA: angin stasiun (bukan Arduino yang macet), rotor diameter 2,5 m
(disepakati 20 Okt), ρ dihitung dari suhu/kelembapan/tekanan, data 1 menit
30 Mar–20 Okt, split kronologis (latih s.d. Jul, uji Okt), tanpa sampel seimbang buatan.

Catatan jujur: label Cp adalah rumus dari input (V, I, v), jadi aturan Cp langsung
selalu 100% benar. Model ML di sini hanya menunjukkan seberapa baik ia meniru rumus
tersebut, dan berapa biaya hitungnya bila dijalankan di edge.
"""

import json
import time
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forecast"))
from features import air_density  # noqa: E402

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ml" / "results"
AREA = np.pi * 1.25**2                      # diameter 2,5 m
PRESSURE_HPA = 1013.25 * (1 - 2.25577e-5 * 768) ** 5.25588


def load():
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    t = t.dropna(subset=["voltage_v", "current_a", "wind_ms"])
    t = t[(t["wind_ms"] >= 0.5) & (t["turbin_on"] > 0.5)]
    temp = t["temp_c"].fillna(t["temp_c"].median())
    rho = air_density(temp, t["humidity_pct"], PRESSURE_HPA)
    p = t["voltage_v"] * t["current_a"]
    t = t.assign(rho=rho, cp=p / (0.5 * rho * AREA * t["wind_ms"] ** 3))
    t["status"] = np.where(t["cp"] < 0.10, "Inefisien", np.where(t["cp"] <= 0.59, "Optimal", "Anomaly"))
    return t


def main():
    t = load()
    tr = t[t.index < pd.Timestamp("2026-08-01", tz="UTC")]
    te = t[t.index >= pd.Timestamp("2026-10-01", tz="UTC")]
    X = ["voltage_v", "current_a", "wind_ms"]
    res = {"n_train": len(tr), "n_test": len(te),
           "distribusi_test": te["status"].value_counts(normalize=True).round(3).to_dict(),
           "cp_median_test": round(float(te["cp"].median()), 3)}
    sub = tr.sample(n=min(20_000, len(tr)), random_state=0)       # SVM RBF lambat untuk data besar
    models = {
        "SVM RBF (seperti TA, 20 rb sampel)": (make_pipeline(StandardScaler(), SVC(C=8, gamma=0.42)), sub),
        "SVM linear": (make_pipeline(StandardScaler(), LinearSVC(C=1.0)), tr),
        "Random Forest": (RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=0), tr),
        "LightGBM": (lgb.LGBMClassifier(n_estimators=300, verbose=-1, random_state=0), tr),
    }
    out = {"Aturan Cp langsung (rumus label)": {"akurasi": 1.0, "macro_F1": 1.0, "ms_per_1000": None}}
    for name, (m, d) in models.items():
        m.fit(d[X], d["status"])
        t0 = time.perf_counter()
        pred = m.predict(te[X])
        dt = (time.perf_counter() - t0) / len(te) * 1000 * 1000
        out[name] = {"akurasi": round(float(accuracy_score(te["status"], pred)), 4),
                     "macro_F1": round(float(f1_score(te["status"], pred, average="macro")), 4),
                     "ms_per_1000": round(dt, 3)}
    res["model"] = out
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "status_perbaikan.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
