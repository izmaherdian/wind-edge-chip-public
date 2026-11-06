"""Ekspor MLP kurva daya (fitur 1) untuk FPGA dan ESP32: ml/status/model/export/.

Format sama persis dengan model prediksi (ml/forecast/export.py), sehingga RTL MAC4 yang sama
bisa memakainya sebagai set bobot kedua: weights.hex, weights32.hex, bias.hex,
test_vectors.csv, mlp_powercurve_int8.h.
"""

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
from golden_model import GoldenModelINT8  # noqa: E402

MODEL = ROOT / "ml" / "status" / "model"
OUT = MODEL / "export"



def cf(v):
    """Literal float C: 0 -> 0.0f (C tidak menerima 0f)."""
    s = f"{v:.6g}"
    return (s if any(c in s for c in ".e") else s + ".0") + "f"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gm = GoldenModelINT8(model_path=str(MODEL / "powercurve_int8.json"))
    assert gm.trained
    gm.export_hex(OUT / "weights.hex", OUT / "bias.hex")
    d = np.load(MODEL / "test_set_int8.npz")
    idx = np.random.default_rng(0).choice(len(d["x_q"]), 600, replace=False)
    rows, mismatch = [], 0
    for k in sorted(idx):
        x = d["x_q"][k].tolist()
        out, h1, h2 = gm.forward(x)
        mismatch += out != int(d["out_q"][k])
        rows.append([int(k)] + x + h1 + h2 + [out, round(float(d["y_true_w"][k]), 3)])
    head = ["idx"] + [f"x{i}" for i in range(16)] + [f"h1_{i}" for i in range(32)] + [f"h2_{i}" for i in range(16)] + ["out_q", "y_true_w"]
    with open(OUT / "test_vectors.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    print(f"[OK] {len(rows)} test vector; beda golden vs integer numpy: {mismatch}")

    flat = lambda w: [w[i][j] for j in range(len(w[0])) for i in range(len(w))]
    arr = lambda name, vals, t: f"static const {t} {name}[{len(vals)}] = {{{', '.join(str(v) for v in vals)}}};\n"
    h = ["/* MLP kurva daya wajar (fitur 1, status turbin) INT8 16-32-16-1, bit-exact dengan FPGA.",
         " * Dihasilkan oleh ml/status/export_powercurve.py. Pakai mlp_layer/mlp_requant dari mlp_int8.h. */",
         "#pragma once", "#include <stdint.h>", "",
         f"#define PC_OUT_SCALE_W {gm.output_scale:.6f}f", ""]
    for i, n in enumerate(gm.features):
        s = gm.feature_scales[n]
        h.append(f"/* {i:2d} {n:13s} center={s['center']:.6g} scale={s['scale']:.6g} */")
    h.append(arr("PC_FEAT_CENTER", [cf(gm.feature_scales[n]['center']) for n in gm.features], "float"))
    h.append(arr("PC_FEAT_SCALE", [cf(gm.feature_scales[n]['scale']) for n in gm.features], "float"))
    h.append(arr("PC_W1", flat(gm.w1), "int8_t") + arr("PC_W2", flat(gm.w2), "int8_t") + arr("PC_W3", flat(gm.w3), "int8_t"))
    h.append(arr("PC_B1", gm.b1, "int32_t") + arr("PC_B2", gm.b2, "int32_t") + arr("PC_B3", gm.b3, "int32_t"))
    (OUT / "mlp_powercurve_int8.h").write_text("\n".join(h))
    print("[OK] mlp_powercurve_int8.h")


if __name__ == "__main__":
    main()
