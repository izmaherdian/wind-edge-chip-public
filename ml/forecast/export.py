"""Ekspor model INT8 untuk FPGA (Alif) dan ESP32 (Genis).

Keluaran di ml/forecast/model/export/:
- weights.hex, bias.hex      : untuk $readmemh di hw/rtl/top.v (susunan sama dengan versi Alif)
- test_vectors.csv           : 600 sampel test nyata (input INT8, h1, h2, keluaran) dari golden model
- mlp_int8.h                 : bobot + fungsi C integer untuk ESP32 (bit-exact dengan FPGA,
                               dipakai sebagai model cadangan bila FPGA tidak membalas)
- mlp_float_int8.tflite      : model float dikuantisasi TFLite (pembanding; tidak bit-exact dengan FPGA)
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
from golden_model import GoldenModelINT8  # noqa: E402

MODEL = ROOT / "ml" / "forecast" / "model"
OUT = MODEL / "export"
N_VECTORS = 600


def cf(v):
    """Literal float C: 0 -> 0.0f (C tidak menerima 0f)."""
    s = f"{v:.6g}"
    return (s if any(c in s for c in ".e") else s + ".0") + "f"


def test_vectors(gm):
    d = np.load(MODEL / "test_set_int8.npz")
    rng = np.random.default_rng(0)
    # sebagian besar acak, ditambah sampel dengan daya tertinggi supaya jalur saturasi ikut teruji
    idx = np.unique(np.concatenate([rng.choice(len(d["x_q"]), N_VECTORS - 50, replace=False),
                                    np.argsort(d["y_true_w"])[-50:]]))
    rows, mismatch = [], 0
    for k in idx:
        x = d["x_q"][k].tolist()
        out, h1, h2 = gm.forward(x)
        mismatch += out != int(d["out_q"][k])
        rows.append([int(k)] + x + h1 + h2 + [out, round(float(d["y_true_w"][k]), 3)])
    head = (["idx"] + [f"x{i}" for i in range(16)] + [f"h1_{i}" for i in range(32)]
            + [f"h2_{i}" for i in range(16)] + ["out_q", "y_true_w"])
    with open(OUT / "test_vectors.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    return len(rows), mismatch


def c_header(gm, m):
    def arr(name, vals, ctype):
        body = ", ".join(str(v) for v in vals)
        return f"static const {ctype} {name}[{len(vals)}] = {{{body}}};\n"
    flat = lambda w: [w[i][j] for j in range(len(w[0])) for i in range(len(w))]   # per neuron j, lalu input i
    s = ["/* MLP 16-32-16-1 INT8, bit-exact dengan akselerator FPGA (ml/golden_model.py).",
         " * Dihasilkan otomatis oleh ml/forecast/export.py. Jangan diedit manual.",
         " * Prediksi rata-rata daya 60 menit ke depan: watt = out * MLP_OUT_SCALE_W. */",
         "#pragma once", "#include <stdint.h>", "",
         f"#define MLP_OUT_SCALE_W {m['skala_keluaran_W_per_lsb']:.6f}f", ""]
    s.append("/* Urutan fitur dan skala: x_q = clamp(round((x - center) / scale), -128, 127) */")
    for i, f in enumerate(m["fitur"]):
        sc = m["skala_fitur"][f]
        s.append(f"/* {i:2d} {f:13s} center={sc['center']:.6g} scale={sc['scale']:.6g} */")
    s.append(arr("MLP_FEAT_CENTER", [cf(m['skala_fitur'][f]['center']) for f in m["fitur"]], "float"))
    s.append(arr("MLP_FEAT_SCALE", [cf(m['skala_fitur'][f]['scale']) for f in m["fitur"]], "float"))
    s.append(arr("MLP_W1", flat(gm.w1), "int8_t") + arr("MLP_W2", flat(gm.w2), "int8_t") + arr("MLP_W3", flat(gm.w3), "int8_t"))
    s.append(arr("MLP_B1", gm.b1, "int32_t") + arr("MLP_B2", gm.b2, "int32_t") + arr("MLP_B3", gm.b3, "int32_t"))
    s.append("""static inline int8_t mlp_requant(int32_t acc) {
    int32_t v = (acc * 32) >> 8;              /* M=32, S=8, sama dengan post_process.v */
    return (int8_t)(v < 0 ? 0 : (v > 127 ? 127 : v));
}

static inline void mlp_layer(const int8_t *in, int n_in, const int8_t *w, const int32_t *b, int n_out, int8_t *out) {
    for (int j = 0; j < n_out; j++) {
        int32_t acc = b[j];
        for (int i = 0; i < n_in; i++) acc += (int32_t)in[i] * w[j * n_in + i];
        out[j] = mlp_requant(acc);
    }
}

/* x: 16 fitur INT8. Mengembalikan keluaran INT8 0..127. */
static inline int8_t mlp_predict(const int8_t x[16]) {
    int8_t h1[32], h2[16], y;
    mlp_layer(x, 16, MLP_W1, MLP_B1, 32, h1);
    mlp_layer(h1, 32, MLP_W2, MLP_B2, 16, h2);
    mlp_layer(h2, 16, MLP_W3, MLP_B3, 1, &y);
    return y;
}
""")
    (OUT / "mlp_int8.h").write_text("\n".join(s))


def tflite(m):
    """Konversi MLP float ke TFLite INT8 (kuantisasi pasca-latih standar)."""
    import tensorflow as tf
    import torch
    from features import FEATURES, build, split
    from train_mlp import FloatMLP

    tr, _, _ = split(build())
    mu, sd = tr[FEATURES].mean().to_numpy(), tr[FEATURES].std().to_numpy()
    fm = FloatMLP()
    fm.load_state_dict(torch.load(MODEL / "mlp_float.pt"))
    layers = [l for l in fm.net if isinstance(l, torch.nn.Linear)]
    inp = tf.keras.Input((16,))
    h = (inp - mu.astype("float32")) / sd.astype("float32")
    for l in layers:
        dense = tf.keras.layers.Dense(l.out_features, activation="relu")
        h = dense(h)
        dense.set_weights([l.weight.detach().numpy().T, l.bias.detach().numpy()])
    km = tf.keras.Model(inp, h)
    rep = tr[FEATURES].to_numpy("float32")[::50]
    conv = tf.lite.TFLiteConverter.from_keras_model(km)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = lambda: ([r[None]] for r in rep[:500])
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    data = conv.convert()
    (OUT / "mlp_float_int8.tflite").write_bytes(data)
    return len(data)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gm = GoldenModelINT8()
    assert gm.trained, "jalankan train_mlp.py dulu"
    m = json.loads((MODEL / "mlp_int8.json").read_text())
    gm.export_hex(OUT / "weights.hex", OUT / "bias.hex")
    n, mismatch = test_vectors(gm)
    print(f"[OK] {n} test vector; beda golden model vs integer numpy: {mismatch}")
    c_header(gm, m)
    print("[OK] mlp_int8.h")
    print(f"[OK] mlp_float_int8.tflite: {tflite(m)} byte")


if __name__ == "__main__":
    main()
