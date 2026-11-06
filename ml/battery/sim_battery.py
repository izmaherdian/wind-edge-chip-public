"""Fitur 3 (masukan PLN di coaching clinic): prediksi setelah charge controller, baterai, dan inverter.

Sistem sekarang belum punya baterai/inverter (generator → rectifier → dump load resistor 35 Ω / 1.200 W), jadi ini
SIMULASI dengan daya DC terukur (data Okt) sebagai masukan. Asumsi (ubah di ASUMSI):
- charge controller η = 0,95; aki timbal-asam 12 V 50 Ah (600 Wh) yang akan dipasang (keputusan tim 22 Okt 2026),
  η_isi 0,90, η_buang 0,95, SoC 50–100 % (DoD 50 % agar aki awet), awal 75 %; kelebihan saat penuh dibuang ke
  dump load 35 Ω; kekurangan saat SoC 50 % diambil dari PLN
- inverter: kurva efisiensi Sandia/CEC Hoymiles MI-250 (pvlib) sebagai pendekatan inverter kecil
- beban AC: 6 W terus-menerus + 25 W pukul 18–23 WIB (lampu/monitoring); skenario sengaja defisit
  (±269 Wh/hari vs produksi ±239 Wh/hari) supaya peringatan impor PLN bisa diuji

Rantai prediksi 1 jam ke depan: prediksi daya DC (model fitur 2) → energi masuk baterai,
SoC 1 jam lagi, impor dari PLN. Dibandingkan dengan nilai "aktual" hasil simulasi.
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ml" / "results"
sys.path.insert(0, str(ROOT / "ml" / "forecast"))

ASUMSI = {
    "eta_charge_controller": 0.95,
    "kapasitas_Wh": 12.0 * 50,        # aki timbal-asam 12 V 50 Ah
    "eta_isi": 0.90,
    "eta_buang": 0.95,
    "soc_min": 0.50,                  # DoD 50 % untuk aki timbal-asam
    "soc_max": 1.00,
    "soc_awal": 0.75,
    "inverter": "Hoymiles_Converter_Technology__MI_250__240V_",
    "beban_dasar_W": 6.0,
    "beban_malam_W": 25.0,
    "jam_malam_WIB": [18, 23],
}


def inverter_model():
    inv = pvlib.pvsystem.retrieve_sam("cecinverter")[ASUMSI["inverter"]]
    v = float(inv["Vdco"])
    grid = np.linspace(0, float(inv["Pdco"]), 2000)
    ac = np.clip(pvlib.inverter.sandia(v, grid, inv), 0, None)
    # kebalikan: daya DC yang dibutuhkan untuk menghasilkan daya AC tertentu
    dc_for_ac = lambda p_ac: np.interp(p_ac, ac, grid)
    return dc_for_ac, inv


def load_profile(index):
    h = index.tz_convert("Asia/Jakarta").hour
    a, b = ASUMSI["jam_malam_WIB"]
    return ASUMSI["beban_dasar_W"] + np.where((h >= a) & (h < b), ASUMSI["beban_malam_W"], 0.0)


def simulate(p_dc, load_ac, dc_for_ac):
    """Simulasi per menit. Mengembalikan SoC, energi ke baterai, dibuang, impor PLN (Wh per menit)."""
    A = ASUMSI
    cap = A["kapasitas_Wh"]
    need_dc = dc_for_ac(load_ac)                       # DC yang diminta inverter
    soc = np.empty(len(p_dc))
    to_batt, dumped, grid = (np.zeros(len(p_dc)) for _ in range(3))
    s = A["soc_awal"]
    for k in range(len(p_dc)):
        net = p_dc[k] * A["eta_charge_controller"] - need_dc[k]      # W di bus baterai
        e = net / 60                                                 # Wh per menit
        if e >= 0:
            room = (A["soc_max"] - s) * cap
            stored = min(e * A["eta_isi"], room)
            to_batt[k] = stored
            dumped[k] = e - stored / A["eta_isi"]
            s += stored / cap
        else:
            avail = (s - A["soc_min"]) * cap
            draw = min(-e / A["eta_buang"], avail)
            s -= draw / cap
            to_batt[k] = -draw
            grid[k] = -e - draw * A["eta_buang"]
        soc[k] = s
    return soc, to_batt, dumped, grid


def forecast_chain(soc_now, p_dc_hat, load_next_mean, dc_for_ac):
    """SoC 1 jam lagi dari prediksi rata-rata daya DC 60 menit ke depan."""
    A = ASUMSI
    net = p_dc_hat * A["eta_charge_controller"] - dc_for_ac(load_next_mean)
    e = np.where(net >= 0, net * A["eta_isi"], net / A["eta_buang"])   # Wh dalam 1 jam
    soc = np.clip(soc_now + e / A["kapasitas_Wh"], A["soc_min"], A["soc_max"])
    return soc, e


def main():
    dc_for_ac, inv = inverter_model()
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    t = t[t.index >= pd.Timestamp("2026-10-01", tz="UTC")]
    p_dc = t["power_w"].fillna(0).to_numpy()
    load = load_profile(t.index)
    soc, to_batt, dumped, grid = simulate(p_dc, load, dc_for_ac)
    sim = pd.DataFrame({"soc": soc, "to_batt_Wh": to_batt, "dumped_Wh": dumped, "grid_Wh": grid, "load_W": load}, index=t.index)

    pred = pd.read_parquet(RESULTS / "prediksi_test.parquet")
    d = np.load(ROOT / "ml" / "forecast" / "model" / "test_set_int8.npz")
    s_y = json.loads((ROOT / "ml" / "forecast" / "model" / "mlp_int8.json").read_text())["skala_keluaran_W_per_lsb"]
    pred["MLP INT8 (FPGA)"] = pd.Series(d["out_q"] * s_y, index=pd.to_datetime(d["time"], utc=True)).reindex(pred.index).to_numpy()
    cands = {"persistence": pred["p_now"], "smart persistence": pred["smart persistence (rata-rata 60 menit terakhir)"],
             "MLP INT8 (FPGA)": pred["MLP INT8 (FPGA)"], "LightGBM": pred["LightGBM"], "Ideal (daya DC aktual)": pred["y"]}

    # nilai aktual 1 jam ke depan dari simulasi
    idx = sim.index.get_indexer(pred.index)
    ok = (idx >= 0) & (idx + 60 < len(sim))
    idx = idx[ok]
    soc_now, soc_next = sim["soc"].to_numpy()[idx], sim["soc"].to_numpy()[idx + 60]
    load_next = np.array([load[i + 1:i + 61].mean() for i in idx])
    batt_next = np.array([to_batt[i + 1:i + 61].sum() for i in idx])
    grid_next = np.array([grid[i + 1:i + 61].sum() for i in idx])
    out = {}
    for name, ph in cands.items():
        ph = np.asarray(ph)[ok]
        s_hat, e_hat = forecast_chain(soc_now, ph, load_next, dc_for_ac)
        grid_hat = s_hat <= ASUMSI["soc_min"] + 1e-9
        grid_true = grid_next > 0.5
        tp = np.sum(grid_hat & grid_true)
        out[name] = {
            "MAE_SoC_1jam_poin_persen": round(float(100 * np.mean(np.abs(s_hat - soc_next))), 3),
            "MAE_energi_ke_baterai_1jam_Wh": round(float(np.mean(np.abs(e_hat - batt_next))), 2),
            "impor_PLN_terprediksi_presisi": round(float(tp / max(grid_hat.sum(), 1)), 3),
            "impor_PLN_terprediksi_recall": round(float(tp / max(grid_true.sum(), 1)), 3),
        }
    eff = inv["Paco"] / inv["Pdco"]
    res = {
        "asumsi": ASUMSI,
        "inverter_efisiensi_nominal": round(float(eff), 3),
        "ringkasan_simulasi_okt": {
            "energi_turbin_DC_Wh": round(float(p_dc.sum() / 60), 1),
            "energi_beban_AC_Wh": round(float(load.sum() / 60), 1),
            "energi_dibuang_Wh": round(float(dumped.sum()), 1),
            "impor_PLN_Wh": round(float(grid.sum()), 1),
            "persen_waktu_SoC_minimum": round(float(100 * np.mean(soc <= ASUMSI["soc_min"] + 1e-9)), 1),
            "SoC_rata_rata_persen": round(float(100 * soc.mean()), 1),
        },
        "prediksi_1jam": out,
        "catatan": "Simulasi dengan asumsi; angka nyata butuh pengukuran baterai/inverter (docs/kajian-inverter-baterai.md).",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "baterai_simulasi.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    sim.to_parquet(RESULTS / "baterai_simulasi.parquet")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
