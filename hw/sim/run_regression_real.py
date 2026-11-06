"""
Regresi RTL Verilog vs Golden Model dengan VEKTOR DATA TURBIN NYATA (Icarus Verilog).

Melengkapi run_regression.py (vektor acak): vektor diambil dari
ml/forecast/model/export/test_vectors.csv (597 sampel uji 1-20 Okt 2026),
bobot dari ml/forecast/model/mlp_int8.json (hasil training).

Pemakaian:
  python3 hw/sim/run_regression_real.py            # semua vektor core + 50 vektor SoC
  python3 hw/sim/run_regression_real.py --soc 0    # tanpa uji UART
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_regression as rr  # noqa: E402

CSV_PATH = os.path.join(rr.PROJECT_ROOT, "ml", "forecast", "model", "export", "test_vectors.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soc", type=int, default=50, help="jumlah vektor uji SoC/UART (0 = lewati)")
    args = ap.parse_args()

    gm = rr.GoldenModelINT8()
    if not getattr(gm, "trained", False):
        print("[ERROR] golden model tidak memuat bobot training (ml/forecast/model/mlp_int8.json)")
        return 2
    rows = list(csv.DictReader(open(CSV_PATH)))
    inputs = [[int(r[f"x{i}"]) for i in range(16)] for r in rows]
    gm.export_hex(os.path.join(rr.RTL_DIR, "weights.hex"), os.path.join(rr.RTL_DIR, "bias.hex"))
    os.makedirs(rr.BUILD_DIR, exist_ok=True)
    vec = os.path.join(rr.BUILD_DIR, "vectors_real.hex")
    rr.write_vectors(gm, inputs, vec)
    mismatch = sum(gm.forward(x)[0] != int(r["out_q"]) for x, r in zip(inputs, rows))
    print(f"[Vektor] {len(rows)} sampel nyata; golden vs out_q di CSV: {mismatch} beda")

    ok = mismatch == 0
    ok &= rr.compile_and_run("core_real", "tb_regress.v", rr.CORE_SRCS,
                             [f"+VEC={vec}", f"+N={len(inputs)}", f"+CYC={rr.EXPECTED_CYCLES}"])
    if args.soc > 0:
        ok &= rr.compile_and_run("soc_real", "tb_soc.v", rr.SOC_SRCS,
                                 [f"+VEC={vec}", f"+N={min(args.soc, len(inputs))}", f"+CYC={rr.EXPECTED_CYCLES}"])
    print("HASIL DATA NYATA: " + ("LULUS" if ok else "GAGAL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
