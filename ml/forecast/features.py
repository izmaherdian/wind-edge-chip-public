"""16 fitur + target untuk prediksi rata-rata daya 60 menit ke depan.

Urutan FEATURES dikunci di docs/kontrak-kuantisasi.md: urutan ini juga urutan byte
dalam paket ESP32 → FPGA. Semua fitur hanya memakai data ≤ t (tanpa kebocoran);
target = rata-rata daya menit t+1 … t+60.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TURBINE = ROOT / "data" / "processed" / "turbine_1min.parquet"
OPENMETEO = ROOT / "data" / "external" / "openmeteo_forecast.parquet"

FEATURES = [
    "p_now", "p_lag5", "p_lag15", "p_lag30", "p_lag60", "p_mean60",
    "w_now", "w_mean10", "w_mean60", "w3_mean10",
    "dir_sin", "dir_cos", "hour_sin", "hour_cos",
    "rho", "om_wind_next",
]
OFFLINE_FEATURES = [f for f in FEATURES if f != "om_wind_next"]   # mode tanpa internet
TARGET = "y_p_next60"
HORIZON = 60

# Split kronologis (UTC)
TRAIN_END = pd.Timestamp("2026-08-01", tz="UTC")
VAL_END = pd.Timestamp("2026-10-01", tz="UTC")

ELEVATION_M = 768        # Bandung (ITB Ganesha), untuk tekanan cadangan
R_DRY, R_VAP = 287.05, 461.5


def air_density(temp_c, rh_pct, pressure_hpa):
    """Kerapatan udara lembap (kg/m³)."""
    t_k = temp_c + 273.15
    p_sat = 6.1078 * 10 ** (7.5 * temp_c / (temp_c + 237.3))      # hPa (Tetens)
    p_v = rh_pct / 100 * p_sat
    p_d = pressure_hpa - p_v
    return (p_d * 100) / (R_DRY * t_k) + (p_v * 100) / (R_VAP * t_k)


def build(with_openmeteo=True):
    t = pd.read_parquet(TURBINE)
    p, w = t["power_w"], t["wind_ms"]
    f = pd.DataFrame(index=t.index)
    f["p_now"] = p
    for k in (5, 15, 30, 60):
        f[f"p_lag{k}"] = p.shift(k)
    f["p_mean60"] = p.rolling(60, min_periods=50).mean()
    f["w_now"] = w
    f["w_mean10"] = w.rolling(10, min_periods=8).mean()
    f["w_mean60"] = w.rolling(60, min_periods=50).mean()
    f["w3_mean10"] = (w**3).rolling(10, min_periods=8).mean()
    s = t["dir_sin"].rolling(10, min_periods=5).mean()
    c = t["dir_cos"].rolling(10, min_periods=5).mean()
    norm = np.hypot(s, c).replace(0, np.nan)
    f["dir_sin"], f["dir_cos"] = (s / norm).fillna(0.0), (c / norm).fillna(0.0)   # angin tenang → 0
    hour = (t.index.tz_convert("Asia/Jakarta").hour + t.index.minute / 60).to_numpy()
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)

    om = pd.read_parquet(OPENMETEO) if with_openmeteo and OPENMETEO.exists() else None
    if om is not None:
        om_min = om.resample("1min").interpolate("time").reindex(t.index)
        pressure = om_min["om_surface_pressure"]
        # prakiraan: rata-rata angin model untuk t … t+60 (tersedia saat operasi dari prakiraan per jam)
        f["om_wind_next"] = om_min["om_wind_speed_10m"].rolling(HORIZON + 1).mean().shift(-HORIZON)
    else:
        pressure = pd.Series(1013.25 * (1 - 2.25577e-5 * ELEVATION_M) ** 5.25588, index=t.index)
        f["om_wind_next"] = np.nan
    temp = t["temp_c"].rolling(30, min_periods=1).mean().ffill(limit=180)
    rh = t["humidity_pct"].rolling(30, min_periods=1).mean().ffill(limit=180)
    rho = air_density(temp, rh, pressure)
    f["rho"] = rho.fillna(rho.median())        # suhu rusak (Jul–Agu) → median, bukan sampel dibuang

    # Target: rata-rata daya t+1 … t+60, minimal 50 menit ada data
    fut = p[::-1].rolling(HORIZON, min_periods=50).mean()[::-1].shift(-1)
    f[TARGET] = fut

    # Jendela t-60 … t+60 harus dalam satu segmen (tidak melewati celah > 10 menit)
    seg = t["segmen"]
    lo = seg.rolling(121, center=True, min_periods=1).min()
    hi = seg.rolling(121, center=True, min_periods=1).max()
    f["segmen"] = seg
    cols = FEATURES if om is not None else OFFLINE_FEATURES
    ok = (lo == hi) & seg.notna() & f[cols + [TARGET]].notna().all(axis=1)
    return f[ok]


def split(f):
    tr = f[f.index < TRAIN_END]
    va = f[(f.index >= TRAIN_END) & (f.index < VAL_END)]
    te = f[f.index >= VAL_END]
    return tr, va, te


if __name__ == "__main__":
    f = build()
    tr, va, te = split(f)
    print(f"sampel: total {len(f)} | train {len(tr)} | val {len(va)} | test {len(te)}")
    print(f[FEATURES + [TARGET]].describe().T.round(3))
