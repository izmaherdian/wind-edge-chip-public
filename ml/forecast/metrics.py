"""Metrik bersama: semua model dinilai dengan fungsi yang sama."""

import numpy as np


def scores(y, yhat, y_persist=None):
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    err = yhat - y
    out = {
        "MAE_W": float(np.mean(np.abs(err))),
        "RMSE_W": float(np.sqrt(np.mean(err**2))),
        "nMAE_pct": float(100 * np.mean(np.abs(err)) / np.mean(y)),
        "bias_W": float(np.mean(err)),
    }
    if y_persist is not None:
        rmse_p = np.sqrt(np.mean((np.asarray(y_persist, float) - y) ** 2))
        out["skill_vs_persistence"] = float(1 - out["RMSE_W"] / rmse_p)
    return out
