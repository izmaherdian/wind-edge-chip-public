"""Siapkan CSV kecil untuk grafik pgfplots di laporan progress dan deck (docs/presentasi/data/).

Semua angka dihitung dari data/hasil yang ada; tidak ada angka yang diketik manual.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "ml" / "results"
OUT = ROOT / "docs" / "presentasi" / "data"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    have = t[t["n_sampel"] > 0]

    # 1. Persentase menit turbin OFF per jam (WIB)
    h = have.index.tz_convert("Asia/Jakarta").hour
    off = (1 - have["turbin_on"]).groupby(h).mean() * 100
    pd.DataFrame({"jam": off.index, "off_persen": off.round(1)}).to_csv(OUT / "off_per_jam.csv", index=False)

    # 2. Jam data per bulan + reboot per bulan
    m = have.index.tz_convert("Asia/Jakarta").month
    jam = have.groupby(m).size() / 60
    reboot = {}
    log = ROOT / "data" / "raw" / "raspi" / "log_reboot.txt"
    if log.exists():
        for line in log.read_text().splitlines():
            mm = re.match(r"\w{3} (\w{3})\s+\d+ .*Internet mati", line)
            if mm:
                reboot[mm.group(1)] = reboot.get(mm.group(1), 0) + 1
    nama = {3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt"}
    eng = {3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct"}
    rows = [{"bulan": nama[k], "jam_data": round(float(jam.get(k, 0)), 0), "reboot": reboot.get(eng[k], 0)} for k in range(3, 11)]
    pd.DataFrame(rows).to_csv(OUT / "data_per_bulan.csv", index=False)

    # 3. Kurva daya: rata-rata daya per bin angin
    b = pd.cut(have["wind_ms"], np.arange(0, 8.5, 0.5))
    curve = have.groupby(b, observed=True)["power_w"].agg(["mean", "median", "size"])
    curve.index = [iv.mid for iv in curve.index]
    curve.rename_axis("angin").reset_index().round(2).to_csv(OUT / "kurva_daya.csv", index=False)

    # 4. Benchmark: semua metode (RMSE), urut + tabel LaTeX
    if not (RES / "benchmark.csv").exists():
        print("benchmark.csv belum ada: lewati grafik benchmark, contoh prediksi, dan baterai")
        return
    bm = pd.read_csv(RES / "benchmark.csv").sort_values("RMSE_W").reset_index(drop=True)
    tex = lambda s: str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#").replace("×", r"$\times$")
    bm["label"] = bm["metode"].map(lambda s: s.replace(",", ";"))
    bm[["label", "kelompok", "MAE_W", "RMSE_W", "skill_vs_persistence"]].round(3).to_csv(OUT / "benchmark.csv", index=False)
    top = pd.concat([bm.head(12), bm[bm["metode"].str.startswith("persistence")]]).drop_duplicates("metode")
    short = lambda s: tex(s if len(s) <= 38 else s[:36] + "…")
    top.assign(label=[f"{short(n)}: {r:.2f}".replace(".", ",") for n, r in zip(top["metode"], top["RMSE_W"])])[["label", "RMSE_W"]] \
        .round(2).to_csv(OUT / "benchmark_top.csv", index=False, sep=";")
    fmt = lambda x: f"{x:.2f}".replace(".", ",")
    fmt_s = lambda x: f"{x:+.3f}".replace(".", ",")

    def table(df, size):
        lines = [rf"\begin{{{size}}}", r"\begin{longtable}{@{}r p{6.2cm} p{3.4cm} r r r p{2.6cm}@{}}" if size == "small" else
                 r"\begin{tabular}{@{}r p{5.2cm} r r r@{}}", r"\toprule"]
        if size == "small":
            lines.append(r"\# & Metode & Kelompok & MAE (W) & RMSE (W) & Skill & FPGA MAC4 \\ \midrule \endhead")
        else:
            lines.append(r"\# & Metode & MAE & RMSE & Skill \\ \midrule")
        for i, r in df.iterrows():
            bold = "INT8 (QAT" in r["metode"]
            name = (r"\textbf{" + tex(r["metode"]) + "}") if bold else tex(r["metode"])
            if size == "small":
                lines.append(f"{i + 1} & {name} & {tex(r['kelompok'])} & {fmt(r['MAE_W'])} & {fmt(r['RMSE_W'])} & "
                             f"{fmt_s(r['skill_vs_persistence'])} & {tex(r.get('jalan_di_FPGA_MAC4', '') if pd.notna(r.get('jalan_di_FPGA_MAC4')) else '')} \\\\")
            else:
                lines.append(f"{i + 1} & {name} & {fmt(r['MAE_W'])} & {fmt(r['RMSE_W'])} & {fmt_s(r['skill_vs_persistence'])} \\\\")
        lines += [r"\bottomrule", r"\end{longtable}" if size == "small" else r"\end{tabular}", rf"\end{{{size}}}"]
        return "\n".join(lines)
    (OUT / "tabel_benchmark.tex").write_text(table(bm, "small"))
    half = (len(bm) + 1) // 2
    def deck_part(df, start):
        lines = [r"\setlength{\tabcolsep}{3pt}\begin{tabular}{@{}r p{4.1cm} r r@{}}", r"\toprule", r"\# & Metode & RMSE & Skill \\ \midrule"]
        for i, r in df.iterrows():
            name = tex(r["metode"])
            name = r"\textbf{" + name + "}" if "INT8 (QAT" in r["metode"] else name
            lines.append(f"{i + 1} & {name} & {fmt(r['RMSE_W'])} & {fmt_s(r['skill_vs_persistence'])} \\\\")
        return "\n".join(lines + [r"\bottomrule", r"\end{tabular}"])
    (OUT / "tabel_benchmark_deck.tex").write_text(r"{\scriptsize\begin{minipage}[t]{0.49\linewidth}" + deck_part(bm.iloc[:half], 0)
        + r"\end{minipage}\hfill\begin{minipage}[t]{0.49\linewidth}" + deck_part(bm.iloc[half:], half) + r"\end{minipage}}")
    i8 = bm[bm["metode"].str.contains("INT8 \\(QAT", regex=True)].index[0]
    best = bm.iloc[0]
    base = bm[bm["kelompok"] == "Baseline"].iloc[0]
    (OUT / "benchmark_jumlah.tex").write_text(
        f"{len(bm)} metode dibandingkan; MLP INT8 peringkat {i8 + 1}. Terbaik: {tex(best['metode'])} ({fmt(best['RMSE_W'])} W).")
    (OUT / "benchmark_ringkas.tex").write_text(
        rf"\textbf{{Ringkasan.}} {len(bm)} metode diuji. Terbaik: \textbf{{{tex(best['metode'])}}} (RMSE {fmt(best['RMSE_W'])} W, "
        rf"skill {fmt_s(best['skill_vs_persistence'])}). Baseline terbaik: {tex(base['metode'])} ({fmt(base['RMSE_W'])} W). "
        rf"Model yang benar-benar berjalan di FPGA, \textbf{{MLP INT8 (QAT)}}, ada di peringkat {i8 + 1} "
        rf"(RMSE {fmt(bm.loc[i8, 'RMSE_W'])} W): selisihnya dengan model terbaik adalah harga yang dibayar untuk 1.040 MAC INT8, "
        r"tanpa sistem operasi, dan hasil yang dapat diverifikasi bit per bit.")

    # 4b. Simulasi baterai
    if (RES / "baterai_simulasi.json").exists():
        b = json.loads((RES / "baterai_simulasi.json").read_text())
        rows = [r"\begin{center}\small", r"\begin{tabular}{@{}l r r r r@{}}", r"\toprule",
                r"Prediksi daya DC yang dipakai & MAE SoC 1 jam (poin \%) & MAE energi ke baterai (Wh) & Presisi impor PLN & Recall \\ \midrule"]
        for k, v in b["prediksi_1jam"].items():
            rows.append(f"{tex(k)} & {fmt(v['MAE_SoC_1jam_poin_persen'])} & {fmt(v['MAE_energi_ke_baterai_1jam_Wh'])} & "
                        f"{fmt(v['impor_PLN_terprediksi_presisi'])} & {fmt(v['impor_PLN_terprediksi_recall'])} \\\\")
        s = b["ringkasan_simulasi_okt"]
        rows += [r"\bottomrule", r"\end{tabular}", r"\end{center}",
                 rf"Simulasi 1--20 Okt: energi turbin {fmt(s['energi_turbin_DC_Wh'])} Wh, beban {fmt(s['energi_beban_AC_Wh'])} Wh, "
                 rf"dibuang {fmt(s['energi_dibuang_Wh'])} Wh, impor PLN {fmt(s['impor_PLN_Wh'])} Wh; SoC di batas minimum "
                 rf"{fmt(s['persen_waktu_SoC_minimum'])}\% waktu."]
        (OUT / "tabel_baterai.tex").write_text("\n".join(rows))
        i = b["prediksi_1jam"]["MLP INT8 (FPGA)"]
        p = b["prediksi_1jam"]["persistence"]
        (OUT / "baterai_ringkas.tex").write_text(
            rf"Simulasi Okt: galat SoC 1 jam {fmt(i['MAE_SoC_1jam_poin_persen'])} poin (MLP INT8) vs {fmt(p['MAE_SoC_1jam_poin_persen'])} poin (persistence).")

    # 5. Contoh prediksi 2 hari di data test
    p = pd.read_parquet(RES / "prediksi_test.parquet")
    d = np.load(ROOT / "ml" / "forecast" / "model" / "test_set_int8.npz")
    s_y = json.loads((ROOT / "ml" / "forecast" / "model" / "mlp_int8.json").read_text())["skala_keluaran_W_per_lsb"]
    p["int8"] = pd.Series(d["out_q"] * s_y, index=pd.to_datetime(d["time"], utc=True)).reindex(p.index)
    loc = p.index.tz_convert("Asia/Jakarta")
    day = loc.normalize()
    best_day = p.groupby(day)["y"].sum().idxmax()             # hari dengan energi terbesar
    sel = p[(loc >= best_day) & (loc < best_day + pd.Timedelta(days=2))]
    sel = sel.iloc[::10]                                        # tiap 10 menit
    hours = (sel.index.tz_convert("Asia/Jakarta") - best_day).total_seconds() / 3600
    pd.DataFrame({"jam": np.round(hours, 3), "aktual": sel["y"].round(2), "persistence": sel["p_now"].round(2),
                  "int8": sel["int8"].round(2), "p10": sel["P10"].round(2), "p90": sel["P90"].round(2)}
                 ).to_csv(OUT / "contoh_prediksi.csv", index=False)
    (OUT / "contoh_prediksi_tanggal.txt").write_text(str(best_day.date()))

    # 6. Simulasi baterai: SoC 3 hari
    if (RES / "baterai_simulasi.parquet").exists():
        s = pd.read_parquet(RES / "baterai_simulasi.parquet")
        s = s.iloc[: 3 * 1440: 10]
        hrs = (s.index - s.index[0]).total_seconds() / 3600
        pd.DataFrame({"jam": np.round(hrs, 3), "soc": (100 * s["soc"]).round(2)}).to_csv(OUT / "soc_3hari.csv", index=False)
    print("tersimpan:", sorted(x.name for x in OUT.iterdir()))


if __name__ == "__main__":
    main()
