"""Reproduksi klasifikasi status turbin dari TA Genis (ml/ta/training_svm.py), tanpa Colab.

Persis seperti TA (laporan TA Bab IV.5.2):
- label dari Cp = V·I / (0,5·ρ·A·v³), ρ = 1,156 kg/m³, A = 7,065 m² (diameter 3 m),
  v = angin Arduino; Inefisien < 0,10 ≤ Optimal ≤ 0,59 < Anomaly
- fitur [voltage, current, Windspeed]; 5.000 sampel acak per kelas; split acak 70/30
- SVC RBF + RandomizedSearchCV (C 2..8, gamma 0,10..0,99, 30 iterasi, CV 3)

Tambahan:
- model asli dari Raspi (ml/ta/models/model_pltb_svm_rbf.pkl) diuji pada data yang sama;
- uji kronologis: latih s.d. 15 Jun, uji 16 Jun–20 Okt (periode yang tidak pernah dilihat).
"""

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.svm import SVC

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "turbine-database"
RESULTS = ROOT / "ml" / "results"
TA_MODEL = ROOT / "ml" / "ta" / "models" / "model_pltb_svm_rbf.pkl"
K_TA = 0.5 * 1.156 * 7.065          # = 4,086 (laporan TA, persamaan IV.12)
CLASSES = ["Anomaly", "Infisien", "Optimal"]


def label_cp(cp):
    return np.where(cp < 0.10, "Infisien", np.where(cp <= 0.59, "Optimal", "Anomaly"))


def load_arduino():
    """V, I, angin Arduino dari semua file (format lama dan baru), baris OFF dibuang seperti TA."""
    frames = []
    for p in sorted(RAW.glob("2026-*.csv")):
        df = pd.read_csv(p, dtype=str, usecols=range(6 if "02-2" in p.name or "01-1" in p.name else 12))
        cols = list(df.columns)
        if "voltage" in cols:
            df = df.rename(columns={"Timestamp": "time", "Windspeed": "wind"})
        else:
            df = df.rename(columns={"Waktu": "time", "Tegangan (V)": "voltage", "Arus (A)": "current",
                                    "Angin Arduino (m/s)": "wind"})
        df = df[["time", "voltage", "current", "wind"]]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], format="%d/%m/%Y, %H.%M.%S")
    for c in ("voltage", "current", "wind"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df[c] = df[c].where(df[c] < 45_000)               # nomor seri tanggal Excel
    df = df.dropna().drop_duplicates("time").sort_values("time")
    df = df[df["wind"] > 0]
    df["cp"] = df["voltage"] * df["current"] / (K_TA * df["wind"] ** 3)
    df["Status"] = label_cp(df["cp"])
    return df


def main():
    df = load_arduino()
    X_cols = ["voltage", "current", "wind"]
    res = {"jumlah_baris": len(df), "distribusi_label": df["Status"].value_counts().to_dict(),
           "persen_angin_arduino_1_25": round(100 * float((df["wind"] == 1.25).mean()), 1)}

    # --- reproduksi TA: sampel seimbang + split acak ---
    period = df[df["time"] <= "2026-06-15 23:59:59"]
    bal = pd.concat([g.sample(n=min(5000, len(g)), random_state=42) for _, g in period.groupby("Status")])
    bal = bal.sample(frac=1, random_state=42)
    Xtr, Xte, ytr, yte = train_test_split(bal[X_cols].to_numpy(), bal["Status"], test_size=0.3, random_state=42)
    search = RandomizedSearchCV(SVC(random_state=42), {"C": np.arange(2, 10, 2), "gamma": np.arange(0.1, 1, 0.01),
                                                       "kernel": ["rbf"]},
                                random_state=42, n_iter=30, cv=3, n_jobs=-1, scoring="accuracy")
    search.fit(Xtr, ytr)
    best = search.best_estimator_
    res["reproduksi_split_acak"] = {
        "parameter_terbaik": {k: float(v) if not isinstance(v, str) else v for k, v in search.best_params_.items()},
        "akurasi_test": round(float(accuracy_score(yte, best.predict(Xte))), 4),
        "laporan": classification_report(yte, best.predict(Xte), output_dict=True, zero_division=0)["macro avg"],
        "klaim_TA": "98,22% (dataset), 96,35% (21.225 data lapangan)",
    }

    # --- model asli dari Raspi pada split test yang sama ---
    ta = joblib.load(TA_MODEL)
    Xte_df = pd.DataFrame(Xte, columns=["voltage", "current", "Windspeed"])
    res["model_raspi_pada_test_sama"] = round(float(accuracy_score(yte, ta.predict(Xte_df))), 4)

    # --- uji kronologis: data setelah 15 Jun (belum pernah dilihat) ---
    later = df[df["time"] > "2026-06-15 23:59:59"]
    pred_new = best.predict(later[X_cols].to_numpy())
    pred_ta = ta.predict(later[X_cols].set_axis(["voltage", "current", "Windspeed"], axis=1))
    res["uji_kronologis_16jun_20okt"] = {
        "n": len(later),
        "akurasi_model_reproduksi": round(float(accuracy_score(later["Status"], pred_new)), 4),
        "akurasi_model_raspi": round(float(accuracy_score(later["Status"], pred_ta)), 4),
        "akurasi_selalu_tebak_kelas_terbanyak": round(float(later["Status"].value_counts(normalize=True).iloc[0]), 4),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "status_reproduksi_ta.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
