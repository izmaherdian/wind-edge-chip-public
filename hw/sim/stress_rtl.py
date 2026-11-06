"""
Stress Test: Golden Model (ml/golden_model.py) vs Mirror RTL (hw/sim/sim_rtl.py)

Menjalankan vektor uji ekstrem + acak, lalu membandingkan output akhir
SERTA aktivasi antar-lapisan (h1, h2) bit-per-bit. Lebih ketat daripada
sim_rtl.py yang hanya memeriksa output final.

Cara pakai (dari root repo):
    py hw/sim/stress_rtl.py             # default 200 vektor acak
    py hw/sim/stress_rtl.py -n 1000     # 1000 vektor acak
    py hw/sim/stress_rtl.py --seed 7    # seed acak berbeda
"""

import argparse
import os
import random
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
RTL_DIR = os.path.join(PROJECT_ROOT, "hw", "rtl")
ML_DIR = os.path.join(PROJECT_ROOT, "ml")

sys.path.append(ML_DIR)

from golden_model import GoldenModelINT8
from sim_rtl import RTLSimulator


def build_cases(n_random, seed):
    cases = [
        [0] * 16,                 # baseline nol
        [-128] * 16,              # ekstrem minimum
        [127] * 16,               # ekstrem maksimum
        [-128, 127] * 8,          # ekstrem campur
        [12, -8, 25, 4, 30, -15, 0, 18, -22, 10, 5, -3, 8, 14, -1, 9],  # vektor tb_top.v
    ]
    rng = random.Random(seed)
    for _ in range(n_random):
        cases.append([rng.randint(-128, 127) for _ in range(16)])
    return cases


def main():
    parser = argparse.ArgumentParser(description="Stress test golden model vs RTL mirror")
    parser.add_argument("-n", "--count", type=int, default=200,
                        help="Jumlah vektor acak (default: 200)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed random untuk reproduksibilitas (default: 42)")
    args = parser.parse_args()

    gm = GoldenModelINT8()
    sim = RTLSimulator(RTL_DIR, vcd_path=None)

    print("=" * 65)
    print("  STRESS TEST: GOLDEN MODEL vs RTL (output + h1 + h2 bit-per-bit)")
    print("=" * 65)

    fails = 0
    cases = build_cases(args.count, args.seed)
    for idx, x in enumerate(cases):
        exp_pred, exp_h1, exp_h2 = gm.forward(x)
        sim.set_input_features(x)
        act_pred, cycles = sim.run()

        if not (exp_pred == act_pred and exp_h1 == sim.h1_buf and exp_h2 == sim.h2_buf):
            fails += 1
            if fails <= 5:
                print(f"\n[MISMATCH] kasus #{idx}: input={x}")
                if exp_pred != act_pred:
                    print(f"  output : golden={exp_pred}  rtl={act_pred}")
                if exp_h1 != sim.h1_buf:
                    print(f"  h1     : diff={[i for i in range(16) if exp_h1[i] != sim.h1_buf[i]]}")
                if exp_h2 != sim.h2_buf:
                    print(f"  h2     : diff={[i for i in range(16) if exp_h2[i] != sim.h2_buf[i]]}")

    print(f"\nJumlah kasus     : {len(cases)}")
    print(f"Kegagalan        : {fails}")
    if fails == 0:
        print("HASIL: LULUS - output, h1, dan h2 identik bit-per-bit pada semua kasus.")
    else:
        print("HASIL: GAGAL - lihat detail mismatch di atas.")
    print("=" * 65)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
