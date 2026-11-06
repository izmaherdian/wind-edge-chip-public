"""SVM status turbin gaya TA, dengan angin Arduino diganti angin stasiun (permintaan Genis, 21 Okt 2026).

Sama dengan model di Raspi (ml/status/reproduce_ta.py): label dari Cp = V·I / (0,5·ρ·A·v³), ρ = 1,156 kg/m³,
diameter 2,5 m (keputusan tim 21 Okt; TA memakai 3 m), Infisien < 0,10 ≤ Optimal ≤ 0,59 < Anomaly; SVC RBF tanpa scaler, masukan [voltage, current, wind],
5.000 sampel per kelas. Yang berubah hanya sumber angin: windspeedstation (Modbus 0x01F4), bukan anemometer Arduino
yang macet di 1,25 m/s.

Latih: data 1 menit 30 Mar-31 Jul; uji: 1-20 Okt (kronologis).
Keluaran: ml/status/model/svm_angin_stasiun.pkl (scikit-learn 1.8.0, sama dengan venv Raspi), ml/results/status_svm_angin_stasiun.json
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import accuracy_score
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[2]
DIAMETER_M = 2.5                    # keputusan tim 21 Okt 2026 (TA: 3 m, A = 7,065 m²)
K_TA = 0.5 * 1.156 * (3.141592653589793 * (DIAMETER_M / 2) ** 2)   # rumus TA (persamaan IV.12), ρ = 1,156
OUT = ROOT / "ml" / "status" / "model" / "svm_angin_stasiun.pkl"


def label_cp(cp):
    return np.where(cp < 0.10, "Infisien", np.where(cp <= 0.59, "Optimal", "Anomaly"))


def main():
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    t = t[(t["turbin_on"] > 0.5)].dropna(subset=["voltage_v", "current_a", "wind_ms"])
    t = t[t["wind_ms"] > 0]
    t = t.assign(cp=t["voltage_v"] * t["current_a"] / (K_TA * t["wind_ms"] ** 3))
    t["status"] = label_cp(t["cp"])
    X = ["voltage_v", "current_a", "wind_ms"]
    tr = t[t.index < pd.Timestamp("2026-08-01", tz="UTC")]
    te = t[t.index >= pd.Timestamp("2026-10-01", tz="UTC")]
    bal = pd.concat([g.sample(n=min(5000, len(g)), random_state=42) for _, g in tr.groupby("status")])
    m = SVC(C=8, gamma=0.4, random_state=42).fit(bal[X].to_numpy(), bal["status"].to_numpy())
    pred = m.predict(te[X].to_numpy())
    res = {
        "sklearn": sklearn.__version__,
        "n_latih_seimbang": len(bal), "n_uji_okt": len(te),
        "akurasi_vs_label_cp_okt": round(float(accuracy_score(te["status"], pred)), 4),
        "distribusi_label_okt": te["status"].value_counts(normalize=True).round(3).to_dict(),
        "distribusi_prediksi_okt": pd.Series(pred).value_counts(normalize=True).round(3).to_dict(),
        "diameter_m": DIAMETER_M,
        "cp_median_okt": round(float(te["cp"].median()), 3),
        "catatan": "label tetap rumus Cp; angin stasiun berbeda tempat dengan rotor, jadi sebagian 'Anomaly' (Cp > 0,59) masih asumsi angin/diameter",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, OUT)
    (ROOT / "ml" / "results" / "status_svm_angin_stasiun.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
