"""Energi harian turbin dari register energi PZEM (kolom "Energi (Wh)"), dibersihkan.

Kenapa register, bukan integrasi daya: saat Raspi reboot/internet putus tidak ada baris tercatat, tetapi PZEM tetap
menghitung energi. Integrasi kolom Daya kehilangan energi di celah itu; register menangkapnya sebagai lompatan.
Pada segmen tanpa celah keduanya sama (validasi di bawah, rasio ~1,01).

"Total Energy" di dashboard = register kumulatif sejak reset PZEM terakhir (bisa berhari-hari), bukan energi per hari.

Aturan (data mentah sudah melalui preprocess.clean: OFF -> 0 W, sel nomor seri Excel -> NaN, spike daya -> NaN):
- Register dihaluskan median 5 baris (flicker naik-turun 1 Wh).
- Kenaikan diterima bila > 0 dan <= P_MAX x dt + 2 Wh (batas fisik; dt = jarak antarbaris, termasuk celah).
- Penurunan = reset PZEM -> dibuang (energi sebelum reset sudah terhitung).
- Hari dipakai untuk statistik bila >= 3.000 baris (~4 jam data, sampel tiap ~5 dtk).

Keluaran: ml/results/energi_harian.csv, ml/results/energi_harian.json, docs/presentasi/data/energi_harian.csv
Jalankan: ml/.venv/bin/python ml/common/energi_harian.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess import P_MAX, ROOT, START, clean, load_raw  # noqa: E402

OUT_CSV = ROOT / "ml" / "results" / "energi_harian.csv"
OUT_JSON = ROOT / "ml" / "results" / "energi_harian.json"
OUT_DECK = ROOT / "docs" / "presentasi" / "data" / "energi_harian.csv"
MIN_BARIS = 3000
RASPI_W, CHIP_W = 2.96, 0.17      # INA219 22 Okt (rata-rata seluruh papan, estimasi tanpa multimeter)


def validasi_segmen(df):
    """Bandingkan kenaikan register vs integrasi daya pada segmen rapat (dt <= 10 dtk, tanpa reset)."""
    x = df.dropna(subset=["energy_wh", "power_w"])
    dt = x["time"].diff().dt.total_seconds()
    seg = ((dt > 10) | (x["energy_wh"].diff() < -2)).cumsum()
    reg = integ = jam = 0.0
    for _, s in x.groupby(seg):
        if len(s) < 300:
            continue
        r = s["energy_wh"].rolling(5, center=True, min_periods=1).median()
        d = np.diff(s["time"].values).astype("timedelta64[ms]").astype(float) / 1000
        e = float((s["power_w"].values[:-1] * d).sum() / 3600)
        if e <= 5:
            continue
        reg += float(r.iloc[-1] - r.iloc[0]); integ += e; jam += float(d.sum() / 3600)
    return {"jam": round(jam, 1), "register_wh": round(reg), "integrasi_wh": round(integ), "rasio": round(reg / integ, 3)}


def main():
    rep = {}
    df = clean(load_raw(), rep)
    df = df[df["time"] >= START].reset_index(drop=True)
    x = df.dropna(subset=["energy_wh"]).copy()
    dt = x["time"].diff().dt.total_seconds().fillna(0)
    halus = x["energy_wh"].rolling(5, center=True, min_periods=1).median()
    naik = halus.diff().fillna(0)
    sah = (naik > 0) & (naik <= P_MAX * dt / 3600 + 2)
    x["inc_wh"] = naik.where(sah, 0.0)
    x["setelah_celah"] = sah & (dt > 60)
    x["tgl"] = x["time"].dt.date

    # integrasi daya (pembanding), dt dibatasi 60 dtk agar celah tidak diisi
    df["dt"] = df["time"].diff().dt.total_seconds().clip(upper=60).fillna(0)
    df["e_int"] = df["power_w"].fillna(0) * df["dt"] / 3600
    df["tgl"] = df["time"].dt.date

    hari = pd.DataFrame({
        "baris": df.groupby("tgl").size(),
        "baris_off": df.groupby("tgl")["turbin_on"].apply(lambda s: int((s == 0).sum())),
        "energi_register_wh": x.groupby("tgl")["inc_wh"].sum(),
        "energi_integrasi_wh": df.groupby("tgl")["e_int"].sum(),
        "wh_dari_celah": x[x["setelah_celah"]].groupby("tgl")["inc_wh"].sum(),
    }).fillna({"wh_dari_celah": 0})
    hari["lengkap"] = hari["baris"] >= MIN_BARIS
    hari = hari.round(1)
    hari.index.name = "tanggal"
    hari.to_csv(OUT_CSV)

    h = hari[hari["lengkap"]]
    e = h["energi_register_wh"]
    med = float(e.median())
    hasil = {
        "metode": "register PZEM dibersihkan (lihat docstring ml/common/energi_harian.py)",
        "periode": f"{h.index.min()} s.d. {h.index.max()}",
        "hari_lengkap": int(len(h)), "hari_ada_data": int(len(hari)),
        "median_wh_per_hari": round(med, 1),
        "kuartil_wh_per_hari": [round(float(e.quantile(0.25)), 1), round(float(e.quantile(0.75)), 1)],
        "median_integrasi_daya_wh_per_hari": round(float(h["energi_integrasi_wh"].median()), 1),
        "rasio_register_per_integrasi_median": round(float((h["energi_register_wh"] / h["energi_integrasi_wh"]).median()), 2),
        "validasi_segmen_tanpa_celah": validasi_segmen(df),
        "baris_off_persen": round(100 * float((df["turbin_on"] == 0).mean()), 1),
        "reset_register": int(((halus.diff() < -2)).sum()),
        "kenaikan_setelah_celah": int(x["setelah_celah"].sum()),
        "per_bulan": {k: {"hari": int(v.size), "median_wh": round(float(v.median()), 1)}
                      for k, v in e.groupby(pd.to_datetime(e.index).strftime("%Y-%m"))},
        "konsumsi_komputer": {
            "raspi_wh_per_hari": round(RASPI_W * 24, 1), "chip_wh_per_hari": round(CHIP_W * 24, 1),
            "raspi_persen_median": round(100 * RASPI_W * 24 / med, 1), "chip_persen_median": round(100 * CHIP_W * 24 / med, 1),
            "raspi_persen_rentang_kuartil": [round(100 * RASPI_W * 24 / float(e.quantile(0.75)), 1),
                                             round(100 * RASPI_W * 24 / float(e.quantile(0.25)), 1)],
            "hemat_kwh_per_tahun_per_turbin": round((RASPI_W - CHIP_W) * 24 * 365 / 1000, 1),
            "sumber_daya": "INA219 22 Okt 2026, rata-rata seluruh papan (estimasi tanpa multimeter)",
        },
    }
    OUT_JSON.write_text(json.dumps(hasil, indent=2, ensure_ascii=False) + "\n")
    bulan = pd.DataFrame([{"bulan": k, "hari": v["hari"], "median_wh": v["median_wh"]} for k, v in hasil["per_bulan"].items()])
    bulan[bulan["hari"] >= 5].to_csv(OUT_DECK, index=False)       # bulan dengan < 5 hari lengkap tidak ditampilkan
    print(json.dumps(hasil, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
