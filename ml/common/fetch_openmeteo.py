"""Unduh cuaca per jam dari Open-Meteo untuk lokasi turbin (atap PAU ITB).

- Historical Forecast API: arsip keluaran model prakiraan (yang juga tersedia saat
  operasi nyata), dipakai sebagai fitur "prakiraan 1 jam ke depan".
- Archive API (ERA5): reanalisis, hanya untuk pembanding.

Gratis, tanpa API key. Lisensi data CC BY 4.0 (sebutkan Open-Meteo sebagai sumber);
pemakaian komersial butuh paket berbayar.
Keluaran: data/external/openmeteo_{forecast,era5}.parquet (tidak masuk git).
"""

import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external"
LAT, LON = -6.891, 107.610
START, END = "2026-03-30", "2026-10-20"
HOURLY = [
    "wind_speed_10m", "wind_speed_80m", "wind_speed_120m", "wind_gusts_10m",
    "wind_direction_10m", "temperature_2m", "relative_humidity_2m",
    "surface_pressure", "cloud_cover",
]
SOURCES = {
    "forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "era5": "https://archive-api.open-meteo.com/v1/archive",
}


def fetch(name, url):
    params = {
        "latitude": LAT, "longitude": LON, "start_date": START, "end_date": END,
        "hourly": ",".join(HOURLY), "wind_speed_unit": "ms", "timezone": "GMT",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").rename(columns=lambda c: f"om_{c}")
    df.index.name = "time_utc"
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        try:
            df = fetch(name, url)
        except requests.RequestException as e:
            print(f"[{name}] gagal: {e}", file=sys.stderr)
            continue
        df.to_parquet(OUT / f"openmeteo_{name}.parquet")
        print(f"[{name}] {len(df)} jam, {df.index[0]} → {df.index[-1]}, NaN: {int(df.isna().sum().sum())}")


if __name__ == "__main__":
    main()
