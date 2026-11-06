"""
Regresi RTL Verilog vs Golden Model (Icarus Verilog).

Menjalankan simulasi Verilog SUNGGUHAN (bukan tiruan Python):
  1. tb_regress.v : uji core `top.v` dengan banyak vektor acak, membandingkan
                    setiap neuron Hidden-1, Hidden-2, output, dan jumlah siklus.
  2. tb_soc.v     : uji end-to-end `top_soc.v` lewat pin UART (115200 8N1).

Keluar dengan kode != 0 jika ada kegagalan atau tool tidak tersedia,
sehingga bisa dipakai di CI.

Pemakaian:
  python3 hw/sim/run_regression.py              # default 500 vektor core, 8 vektor SoC
  python3 hw/sim/run_regression.py -n 2000 --soc 16 --seed 7
  python3 hw/sim/run_regression.py --vcd        # simpan waveform core
"""

import argparse
import os
import random
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
RTL_DIR = os.path.join(PROJECT_ROOT, "hw", "rtl")
BUILD_DIR = os.path.join(PROJECT_ROOT, "hw", "build", "sim")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ml"))

from golden_model import GoldenModelINT8, L_H1, L_H2  # noqa: E402

CORE_SRCS = ["weights_rom.v", "mac4_engine.v", "post_process.v", "fsm_controller.v", "top.v"]
SOC_SRCS = CORE_SRCS + ["uart_rx.v", "uart_tx.v", "top_soc.v"]

# Jumlah siklus busy sebelum state DONE:
#   L1: 32 neuron * (4 step + 1 post) + L2: 16 * (8 + 1) + L3: 1 * (4 + 1)
EXPECTED_CYCLES = 32 * (4 + 1) + 16 * (8 + 1) + 1 * (4 + 1)


def make_inputs(n, rng):
    """Campuran pola input: acak penuh, kecil, ekstrem, nol, dan pola khusus."""
    vecs = [
        [0] * 16,
        [127] * 16,
        [-128] * 16,
        [127, -128] * 8,
        [12, -8, 25, 4, 30, -15, 0, 18, -22, 10, 5, -3, 8, 14, -1, 9],  # vektor lama
    ]
    while len(vecs) < n:
        mode = rng.random()
        if mode < 0.4:
            v = [rng.randint(-128, 127) for _ in range(16)]
        elif mode < 0.8:
            v = [rng.randint(-8, 8) for _ in range(16)]
        elif mode < 0.9:
            v = [rng.choice([-128, -1, 0, 1, 127]) for _ in range(16)]
        else:
            v = [rng.randint(-32, 32) for _ in range(16)]
        vecs.append(v)
    return vecs[:n]


def write_vectors(gm, inputs, path):
    stats = {"out_sat_hi": 0, "out_zero": 0, "out_mid": 0, "hid_total": 0, "hid_sat": 0}
    with open(path, "w") as f:
        for x in inputs:
            out, h1, h2 = gm.forward(x)
            assert len(h1) == L_H1 and len(h2) == L_H2
            for b in list(x) + h1 + h2 + [out]:
                f.write(f"{b & 0xFF:02x}\n")
            if out >= 127:
                stats["out_sat_hi"] += 1
            elif out <= 0:
                stats["out_zero"] += 1
            else:
                stats["out_mid"] += 1
            for h in h1 + h2:
                stats["hid_total"] += 1
                if h >= 127:
                    stats["hid_sat"] += 1
    return stats


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def compile_and_run(name, tb, srcs, plusargs):
    out = os.path.join(BUILD_DIR, f"{name}.vvp")
    cmd = ["iverilog", "-g2012", "-Wall", "-Wno-timescale", "-Wno-sensitivity-entire-array", "-o", out, "-s", tb.replace(".v", "")]
    cmd += [os.path.join(RTL_DIR, s) for s in srcs] + [os.path.join(BASE_DIR, tb)]
    res = run(cmd, RTL_DIR)
    if res.returncode != 0:
        print(f"  [GAGAL KOMPILASI]\n{res.stderr}")
        return False
    warnings = [l for l in res.stderr.splitlines() if l.strip()]
    if warnings:
        print("  Peringatan iverilog:")
        for w in warnings[:20]:
            print("    " + w)

    # cwd = RTL_DIR karena top.v memuat weights.hex/bias.hex via path relatif
    res = run(["vvp", "-n", out] + plusargs, RTL_DIR)
    lines = res.stdout.splitlines()
    for l in lines:
        if l.startswith("[V") or l.startswith("CYCLES") or l.startswith("RESULT"):
            print("  " + l)
    return any(l.startswith("RESULT PASS") for l in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=500, help="jumlah vektor uji core")
    ap.add_argument("--soc", type=int, default=8, help="jumlah vektor uji SoC/UART (0 = lewati)")
    ap.add_argument("--seed", type=int, default=1, help="seed generator vektor")
    ap.add_argument("--vcd", action="store_true", help="simpan waveform core ke hw/build/sim/core.vcd")
    args = ap.parse_args()

    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            print(f"[ERROR] '{tool}' tidak ditemukan. Install: sudo apt install iverilog")
            return 2

    os.makedirs(BUILD_DIR, exist_ok=True)
    rng = random.Random(args.seed)

    print("=" * 66)
    print(" REGRESI RTL VERILOG vs GOLDEN MODEL (Icarus Verilog)")
    print("=" * 66)

    gm = GoldenModelINT8()
    gm.export_hex(os.path.join(RTL_DIR, "weights.hex"), os.path.join(RTL_DIR, "bias.hex"))

    inputs = make_inputs(args.n, rng)
    vec_path = os.path.join(BUILD_DIR, "vectors.hex")
    st = write_vectors(gm, inputs, vec_path)
    print(f"\n[Vektor] {args.n} vektor (seed={args.seed})")
    print(f"  Output: {st['out_mid']} di tengah, {st['out_sat_hi']} saturasi 127, {st['out_zero']} nol (ReLU)")
    print(f"  Hidden: {100.0 * st['hid_sat'] / st['hid_total']:.1f}% neuron saturasi 127")
    if st["out_mid"] < args.n * 0.2:
        print("  [CATATAN] Sebagian besar output saturasi/nol -> tes output saja lemah;")
        print("            karena itu setiap neuron hidden juga dicek.")

    ok_all = True

    print(f"\n[1] Core top.v (tb_regress.v), expected cycles = {EXPECTED_CYCLES}")
    plus = [f"+VEC={vec_path}", f"+N={args.n}", f"+CYC={EXPECTED_CYCLES}"]
    if args.vcd:
        plus.append(f"+VCD={os.path.join(BUILD_DIR, 'core.vcd')}")
    ok_all &= compile_and_run("core", "tb_regress.v", CORE_SRCS, plus)

    if args.soc > 0:
        n_soc = min(args.soc, args.n)
        print(f"\n[2] SoC top_soc.v via UART (tb_soc.v), {n_soc} vektor")
        plus = [f"+VEC={vec_path}", f"+N={n_soc}", f"+CYC={EXPECTED_CYCLES}"]
        ok_all &= compile_and_run("soc", "tb_soc.v", SOC_SRCS, plus)

    print("\n" + "=" * 66)
    print(" HASIL: " + ("LULUS" if ok_all else "GAGAL"))
    print("=" * 66)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
