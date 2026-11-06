"""Bersihkan data turbin mentah lalu resample ke 1 menit.

Masukan : data/raw/turbine-database/2026-*.csv (format 12+ kolom, mulai 30 Mar 2026)
Keluaran: data/processed/turbine_1min.parquet + ml/results/kualitas_data.json

Aturan (disepakati 20 Okt 2026, lihat data/README.md):
- Waktu WIB "D/M/YYYY, HH.MM.SS" → disimpan UTC; urutkan, buang duplikat.
- Sel > 45.000 = nomor seri tanggal Excel → NaN.
- "OFF" = turbin tidak menghasilkan (angin lemah) → daya 0 W.
- Daya rusak dihitung ulang dari V × I bila V dan I utuh.
- Spike daya di atas batas fisik beban 35 Ω → NaN.
- Angin Arduino (macet di 1,25 m/s) dan curah hujan (penghitung kumulatif) tidak dipakai.
- Angin stasiun > 8 m/s → NaN; arah -115, kelembapan < 0, suhu < 5 °C → NaN.
  Arah negatif lain (-114…-1) sah: sensor punya offset sudut, sin/cos tetap benar.
- Menit tanpa sampel tetap NaN (tidak diinterpolasi); celah > 10 menit memutus segmen.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "turbine-database"
OUT = ROOT / "data" / "processed" / "turbine_1min.parquet"
REPORT = ROOT / "ml" / "results" / "kualitas_data.json"

START = pd.Timestamp("2026-03-30", tz="Asia/Jakarta")
EXCEL_SERIAL_MIN = 45_000
R_LOAD = 35.0          # resistor dump load (laporan TA)
P_MAX = 1_000.0        # W, jauh di atas p99 (±150–360 W)
WIND_MAX = 8.0         # m/s; di atas ini daya median 0 W → sensor salah (disepakati 20 Okt)
GAP_MIN = 10           # menit

COLS = {
    "Waktu": "time",
    "Tegangan (V)": "voltage_v",
    "Arus (A)": "current_a",
    "Daya (W)": "power_w",
    "Energi (Wh)": "energy_wh",
    "Angin Stasiun (m/s)": "wind_ms",
    "Arah Angin (°)": "wind_dir_deg",
    "Kelembapan (%)": "humidity_pct",
    "Suhu (°C)": "temp_c",
}


def load_raw():
    frames = []
    for p in sorted(RAW.glob("2026-*.csv")):
        with open(p, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        header = rows[0][:12]
        if "Daya (W)" not in header:      # format lama (Jan–Mar), tanpa angin stasiun
            continue
        # beberapa baris punya kolom tambahan (catatan validasi manual); ambil 12 kolom pertama
        df = pd.DataFrame([r[:12] for r in rows[1:]], columns=header)
        df = df[list(COLS)].rename(columns=COLS)
        df["file"] = p.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def clean(df, rep):
    rep["baris_mentah"] = len(df)
    t = pd.to_datetime(df["time"], format="%d/%m/%Y, %H.%M.%S").dt.tz_localize("Asia/Jakarta")
    df = df.assign(time=t)
    df = df[df["time"] >= START]
    df = df.sort_values("time", kind="stable")
    dup = df["time"].duplicated()
    rep["duplikat_dibuang"] = int(dup.sum())
    df = df[~dup].copy()

    off = df["power_w"].eq("OFF")
    rep["baris_off"] = int(off.sum())
    num = {c: pd.to_numeric(df[c], errors="coerce") for c in COLS.values() if c != "time"}
    serial = {c: int((v > EXCEL_SERIAL_MIN).sum()) for c, v in num.items()}
    rep["sel_nomor_seri_excel"] = {c: n for c, n in serial.items() if n}
    for c, v in num.items():
        df[c] = v.where(v <= EXCEL_SERIAL_MIN)

    v, i, p = df["voltage_v"], df["current_a"], df["power_w"]
    rebuild = p.isna() & ~off & v.notna() & i.notna()
    rep["daya_dihitung_ulang_vxi"] = int(rebuild.sum())
    p = p.where(~rebuild, v * i)
    spike = (p > P_MAX) | (v.notna() & (p > 1.5 * v**2 / R_LOAD + 20))
    rep["spike_daya_dibuang"] = int(spike.sum())
    p = p.where(~spike)
    df["power_w"] = p.where(~off, 0.0)
    df["turbin_on"] = (~off).astype(float)

    w = df["wind_ms"]
    rep["angin_lebih_batas"] = int((w > WIND_MAX).sum())
    df["wind_ms"] = w.where(w <= WIND_MAX)
    # Rentang sensor -114…244 (= 360°, ada offset); hanya -115 yang sentinel (muncul saat angin 0).
    d = df["wind_dir_deg"]
    rep["arah_sentinel"] = int((d == -115).sum())
    df["wind_dir_deg"] = d.where(d != -115)
    df["humidity_pct"] = df["humidity_pct"].where(df["humidity_pct"].between(0, 100))
    df["temp_c"] = df["temp_c"].where(df["temp_c"] >= 5)
    return df


def resample(df):
    df = df.set_index(df["time"].dt.tz_convert("UTC")).drop(columns=["time", "file"])
    rad = np.deg2rad(df["wind_dir_deg"])
    df["dir_sin"], df["dir_cos"] = np.sin(rad), np.cos(rad)
    g = df.resample("1min")
    out = pd.DataFrame({
        "n_sampel": g["power_w"].size(),
        "power_w": g["power_w"].mean(),
        "power_max_w": g["power_w"].max(),
        "voltage_v": g["voltage_v"].mean(),
        "current_a": g["current_a"].mean(),
        "turbin_on": g["turbin_on"].mean(),
        "wind_ms": g["wind_ms"].median(),
        "wind_max_ms": g["wind_ms"].max(),
        "dir_sin": g["dir_sin"].mean(),
        "dir_cos": g["dir_cos"].mean(),
        "humidity_pct": g["humidity_pct"].mean(),
        "temp_c": g["temp_c"].mean(),
    })
    empty = out["n_sampel"] == 0
    out.loc[empty, out.columns.drop("n_sampel")] = np.nan
    # Segmen kontinu: celah > GAP_MIN menit memutus segmen
    have = ~empty
    run = (have != have.shift()).cumsum()
    gap_len = have.groupby(run).transform("size").where(~have, 0)
    breaks = (~have) & (gap_len > GAP_MIN)
    out["segmen"] = breaks.cumsum().where(have)
    out.index.name = "time_utc"
    return out


def main():
    rep = {}
    df = clean(load_raw(), rep)
    out = resample(df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT)
    have = out["n_sampel"] > 0
    rep.update({
        "baris_bersih": len(df),
        "menit_total": len(out),
        "menit_ada_data": int(have.sum()),
        "persen_menit_ada_data": round(100 * have.mean(), 1),
        "jumlah_segmen": int(out["segmen"].nunique()),
        "rentang_utc": [str(out.index[have][0]), str(out.index[have][-1])],
        "nan_per_kolom_pada_menit_ada_data": {c: int(out.loc[have, c].isna().sum()) for c in out.columns},
        "persen_menit_turbin_on": round(100 * (out.loc[have, "turbin_on"] > 0.5).mean(), 1),
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
