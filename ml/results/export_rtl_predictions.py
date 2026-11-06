"""Simulasikan RTL Alif dan buat bukti prediksi untuk deck.

  ml/.venv/bin/python ml/results/export_rtl_predictions.py --hw-root /path/to/integ/hw

Tidak memerlukan data mentah: input, hidden, golden, dan target ada di CSV ekspor.
Simulator berjalan di direktori sementara berisi vectors.hex, weights32.hex, bias.hex.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ["weights_rom.v", "mac4_engine.v", "post_process.v", "fsm_controller.v", "top.v"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    if "ERROR:" in result.stdout or "ERROR:" in result.stderr:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hw-root", type=Path, default=ROOT / "hw")
    args = parser.parse_args()
    rtl = args.hw_root.resolve() / "rtl"
    src = [rtl / name for name in SOURCES]
    tb = ROOT / "hw/sim/tb_predictions.v"
    model = ROOT / "ml/forecast/model/mlp_int8.json"
    export = model.parent / "export"
    vectors = export / "test_vectors.csv"
    rows = list(csv.DictReader(vectors.open()))
    if len(rows) != 597:
        raise ValueError(f"Diharapkan 597 vektor untuk slide ini, ditemukan {len(rows)}")
    for path in src + [tb, model, vectors, export / "weights32.hex", export / "bias.hex"]:
        if not path.is_file():
            raise FileNotFoundError(f"{path}; berikan --hw-root checkout yang memuat RTL")
    with tempfile.TemporaryDirectory(prefix="wec-rtl-") as tmp:
        tmp = Path(tmp)
        for name in ("weights32.hex", "bias.hex"):
            shutil.copyfile(export / name, tmp / name)
        keys = ([f"x{k}" for k in range(16)] + [f"h1_{k}" for k in range(32)]
                + [f"h2_{k}" for k in range(16)] + ["out_q"])
        (tmp / "vectors.hex").write_text("".join(f"{int(row[key]) & 255:02x}\n" for row in rows for key in keys))
        run(["iverilog", "-g2012", "-s", "tb_predictions", "-o", "sim.vvp",
             *map(str, src), str(tb)], tmp)
        log = run(["vvp", "-n", "sim.vvp", f"+N={len(rows)}"], tmp)
    logs = [line.split()[1:] for line in log.splitlines() if line.startswith("OUTLOG ")]
    if len(logs) != len(rows) or f"RESULT PASS vectors={len(rows)}" not in log:
        raise RuntimeError("Log RTL tidak lengkap:\n" + log[-2000:])
    scale = json.loads(model.read_text())["skala_keluaran_W_per_lsb"]
    samples = []
    for i, (values, row) in enumerate(zip(logs, rows)):
        pos, out, cycles = map(int, values)  # X/Z langsung ditolak oleh parser.
        if pos != i or cycles != 309 or out != int(row["out_q"]):
            raise RuntimeError(f"Hasil RTL tidak cocok pada baris {i}")
        samples.append({"idx": int(row["idx"]), "actual_w": float(row["y_true_w"]),
                        "rtl_q": out, "golden_q": int(row["out_q"]), "rtl_w": out * scale, "cycles": cycles})
    errors = [s["rtl_w"] - s["actual_w"] for s in samples]
    metrics = {"n": len(samples), "mismatch": 0, "cycles_min": 309, "cycles_max": 309,
               "mae_w": sum(map(abs, errors)) / len(errors),
               "rmse_w": math.sqrt(sum(e*e for e in errors) / len(errors))}
    report = {"kind": "simulasi RTL Icarus Verilog; bukan pengukuran papan", "metrics": metrics,
              "selection": "550 indeks acak seed 0 + 50 target tertinggi, deduplikasi: 597; bukan seluruh test set",
              "target": "rata-rata daya t+1 sampai t+60 menit, W; target CSV dibulatkan 0,001 W",
              "sha256": {**{f"hw/rtl/{p.name}": digest(p) for p in src},
                         str(tb.relative_to(ROOT)): digest(tb), str(model.relative_to(ROOT)): digest(model),
                         str(vectors.relative_to(ROOT)): digest(vectors),
                         **{str((export / n).relative_to(ROOT)): digest(export / n) for n in ("weights32.hex", "bias.hex")}},
              "samples": samples}
    (ROOT / "ml/results/fpga_predictions.json").write_text(json.dumps(report, indent=2) + "\n")
    (ROOT / "ml/results/fpga_predictions.log").write_text(log)
    tex = ("% Dibuat oleh ml/results/export_rtl_predictions.py; jangan diedit manual.\n"
           f"\\newcommand{{\\RtlN}}{{{metrics['n']}}}\n"
           f"\\newcommand{{\\RtlMismatch}}{{{metrics['mismatch']}}}\n"
           f"\\newcommand{{\\RtlCycles}}{{{metrics['cycles_min']}}}\n"
           f"\\newcommand{{\\RtlMae}}{{{metrics['mae_w']:.2f}}}\n"
           f"\\newcommand{{\\RtlRmse}}{{{metrics['rmse_w']:.2f}}}\n")
    (ROOT / "docs/presentasi/data/fpga_ringkas.tex").write_text(tex)
    plot(samples)
    print(json.dumps(metrics, indent=2))


def plot(samples):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": "#3a2e28", "text.color": "#3a2e28"})
    fig, ax = plt.subplots(figsize=(7.2, 4.8), layout="constrained")
    x = [s["actual_w"] for s in samples]
    y = [s["rtl_w"] for s in samples]
    limit = math.ceil(max(x+y) / 10) * 10
    ax.plot([0, limit], [0, limit], "--", color="#807468", lw=1.2, label="Prediksi = aktual")
    ax.scatter(x, y, s=18, alpha=0.55, color="#ba6840", edgecolors="none", label="597 keluaran RTL")
    ax.set(xlim=(-2, limit), ylim=(-2, limit), xlabel="Daya aktual rata-rata 60 menit berikutnya (W)",
           ylabel="Prediksi akselerator, simulasi RTL (W)")
    ax.grid(alpha=0.15)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    dest = ROOT / "docs/presentasi/gambar/prediksi-rtl"
    fig.savefig(dest.with_suffix(".pdf"))
    fig.savefig(dest.with_suffix(".png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
