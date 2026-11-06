"""Baseline wajib: model yang tidak mengalahkan baseline ini tidak layak diklaim."""

import json
from pathlib import Path

import numpy as np

from features import TARGET, build, split
from metrics import scores

RESULTS = Path(__file__).resolve().parents[2] / "ml" / "results"


def climatology(train):
    """Rata-rata target per jam (WIB) dari data latih."""
    hour = train.index.tz_convert("Asia/Jakarta").hour
    return train.groupby(hour)[TARGET].mean()


def predict_all(train, df):
    clim = climatology(train)
    hour = df.index.tz_convert("Asia/Jakarta").hour
    c = clim.reindex(hour).to_numpy()
    # campuran rata-rata 60 menit terakhir + klimatologi, bobot dipilih di data latih
    th = train.index.tz_convert("Asia/Jakarta").hour
    ct = clim.reindex(th).to_numpy()
    a = np.linspace(0, 1, 101)
    best = a[np.argmin([np.mean((x * train["p_mean60"] + (1 - x) * ct - train[TARGET]) ** 2) for x in a])]
    return {
        "persistence (P sekarang)": df["p_now"].to_numpy(),
        "smart persistence (rata-rata 60 menit terakhir)": df["p_mean60"].to_numpy(),
        "moving average 10 menit": df[["p_now", "p_lag5"]].mean(axis=1).to_numpy(),
        "klimatologi per jam": c,
        f"campuran mean60 + klimatologi (a={best:.2f})": best * df["p_mean60"].to_numpy() + (1 - best) * c,
    }


def main():
    tr, va, te = split(build())
    out = {}
    for name, df in (("val", va), ("test", te)):
        preds = predict_all(tr, df)
        out[name] = {k: scores(df[TARGET], v, df["p_now"]) for k, v in preds.items()}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "baselines.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    for k, v in out["test"].items():
        print(f"{k:55s} MAE {v['MAE_W']:6.2f} W  RMSE {v['RMSE_W']:6.2f} W  skill {v['skill_vs_persistence']:+.3f}")


if __name__ == "__main__":
    main()
