"""
Golden Model untuk Inferensi Multi-Layer Perceptron (MLP) INT8
Topologi: Input (16) -> Hidden 1 (32) -> Hidden 2 (16) -> Output (1)

Murni Python Standard Library (tanpa numpy), aritmetika bilangan bulat,
identik bit-per-bit dengan akselerator FPGA (hw/rtl/ di branch feature/fpga):
    acc = bias + sum(x * w)
    out = clamp((acc * 32) >> 8, 0, 127)       # post_process.v: M=32, S=8, ReLU, clamp

Bobot: dibaca dari ml/forecast/model/mlp_int8.json (hasil ml/forecast/train_mlp.py,
prediksi rata-rata daya 60 menit ke depan). Kalau file itu tidak ada, dipakai bobot
acak lama (seed) supaya simulasi hw/sim/ tetap bisa jalan.
Interface sama dengan versi Alif: GoldenModelINT8(), forward(x) -> (out, h1, h2), export_hex().
"""

import json
import os
import random

# Definisi Topologi
L_IN = 16
L_H1 = 32
L_H2 = 16
L_OUT = 1

TOTAL_WEIGHTS = (L_IN * L_H1) + (L_H1 * L_H2) + (L_H2 * L_OUT)  # 512 + 512 + 16 = 1040
TOTAL_BIAS = L_H1 + L_H2 + L_OUT  # 32 + 16 + 1 = 49

MODEL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forecast", "model", "mlp_int8.json")


class GoldenModelINT8:
    def __init__(self, seed=42, model_path=MODEL_JSON):
        # Parameter Re-kuantisasi Fixed-Point (sama untuk semua lapisan, sesuai RTL)
        self.multiplier = 32   # Skala proporsional
        self.shift = 8        # Dibagi 256
        self.trained = os.path.exists(model_path)
        if self.trained:
            with open(model_path) as f:
                m = json.load(f)
            assert m["topologi"] == [L_IN, L_H1, L_H2, L_OUT]
            assert m["requantize"]["multiplier"] == self.multiplier and m["requantize"]["shift"] == self.shift
            # weights[k][i][j]: input i -> neuron j (sama dengan susunan w1[i][j] versi lama)
            self.w1, self.w2, self.w3 = m["weights"]
            self.b1, self.b2, self.b3 = m["bias"]
            self.feature_scales = m["skala_fitur"]
            self.features = m["fitur"]
            self.output_scale = m["skala_keluaran_W_per_lsb"]
        else:
            random.seed(seed)
            # Inisialisasi bobot dan bias yang seimbang
            self.w1 = [[random.randint(-15, 15) for _ in range(L_H1)] for _ in range(L_IN)]
            self.b1 = [random.randint(20, 60) for _ in range(L_H1)]
            self.w2 = [[random.randint(-12, 12) for _ in range(L_H2)] for _ in range(L_H1)]
            self.b2 = [random.randint(20, 50) for _ in range(L_H2)]
            # Layer output: bobot kecil agar akumulasi di rentang dinamis [10..100]
            self.w3 = [[random.randint(1, 3) for _ in range(L_OUT)] for _ in range(L_H2)]
            self.b3 = [15]
            self.feature_scales, self.features, self.output_scale = None, None, None
        for row in self.w1 + self.w2 + self.w3:
            assert all(-128 <= w <= 127 for w in row), "bobot di luar INT8"

    def requantize(self, acc_val):
        """Re-kuantisasi INT32 -> INT8 dengan aktivasi ReLU dan clipping."""
        # Skalakan fixed-point: (acc * M) >> S
        scaled = (acc_val * self.multiplier) >> self.shift
        # ReLU: jika negatif -> 0
        if scaled < 0:
            return 0
        # Saturation clipping ke batas atas 8-bit positif [0, 127]
        return min(scaled, 127)

    def forward(self, x_in):
        """
        Menjalankan forward pass secara deterministik.
        x_in: list berisi 16 integer bertanda [-128, 127]
        """
        assert len(x_in) == L_IN
        x = [int(v) for v in x_in]
        assert all(-128 <= v <= 127 for v in x)

        # --- Layer 1 (16 -> 32) ---
        h1 = [0] * L_H1
        for j in range(L_H1):
            acc = self.b1[j]
            for i in range(L_IN):
                acc += x[i] * self.w1[i][j]
            h1[j] = self.requantize(acc)

        # --- Layer 2 (32 -> 16) ---
        h2 = [0] * L_H2
        for j in range(L_H2):
            acc = self.b2[j]
            for i in range(L_H1):
                acc += h1[i] * self.w2[i][j]
            h2[j] = self.requantize(acc)

        # --- Layer 3 / Output (16 -> 1) ---
        acc = self.b3[0]
        for i in range(L_H2):
            acc += h2[i] * self.w3[i][0]
        out_val = self.requantize(acc)

        return out_val, h1, h2

    def quantize_features(self, values):
        """Fitur float (urutan self.features) -> 16 INT8, sama seperti yang dikerjakan ESP32."""
        out = []
        for name, v in zip(self.features, values):
            s = self.feature_scales[name]
            q = round((v - s["center"]) / s["scale"])
            out.append(max(-128, min(127, q)))
        return out

    def to_watt(self, out_val):
        return out_val * self.output_scale

    def export_hex(self, weights_hex_path, bias_hex_path):
        """Mengekspor bobot dan bias ke format .hex untuk dibaca $readmemh di Verilog."""
        all_weights = []
        # Layer 1: iterasi per-neuron (j), lalu per-input (i)
        for j in range(L_H1):
            for i in range(L_IN):
                all_weights.append(self.w1[i][j])
        # Layer 2
        for j in range(L_H2):
            for i in range(L_H1):
                all_weights.append(self.w2[i][j])
        # Layer 3
        for j in range(L_OUT):
            for i in range(L_H2):
                all_weights.append(self.w3[i][j])

        assert len(all_weights) == TOTAL_WEIGHTS

        with open(weights_hex_path, "w") as f:
            for w in all_weights:
                f.write(f"{(w & 0xFF):02x}\n")

        # Ekspor format 32-bit (4 bobot per word) untuk inferred Block RAM (BSRAM Gowin)
        weights32_path = os.path.join(os.path.dirname(weights_hex_path), "weights32.hex")
        with open(weights32_path, "w") as f:
            for idx in range(0, len(all_weights), 4):
                w0 = all_weights[idx + 0] & 0xFF
                w1 = all_weights[idx + 1] & 0xFF
                w2 = all_weights[idx + 2] & 0xFF
                w3 = all_weights[idx + 3] & 0xFF
                word32 = (w3 << 24) | (w2 << 16) | (w1 << 8) | w0
                f.write(f"{word32:08x}\n")

        all_bias = self.b1 + self.b2 + self.b3
        assert len(all_bias) == TOTAL_BIAS

        with open(bias_hex_path, "w") as f:
            for b in all_bias:
                f.write(f"{(b & 0xFFFFFFFF):08x}\n")

        print(f"[OK] Bobot diekspor: {len(all_weights)} byte ke {weights_hex_path} & {len(all_weights)//4} word ke {weights32_path}")
        print(f"[OK] Bias diekspor: {len(all_bias)} dword ke {bias_hex_path}")


if __name__ == "__main__":
    gm = GoldenModelINT8()
    print(f"[INFO] Bobot: {'hasil training (' + MODEL_JSON + ')' if gm.trained else 'acak (seed)'}")

    rtl_dir = os.path.join(os.path.dirname(__file__), "..", "hw", "rtl")
    os.makedirs(rtl_dir, exist_ok=True)

    w_path = os.path.join(rtl_dir, "weights.hex")
    b_path = os.path.join(rtl_dir, "bias.hex")
    gm.export_hex(w_path, b_path)

    dummy_input = [12, -8, 25, 4, 30, -15, 0, 18, -22, 10, 5, -3, 8, 14, -1, 9]
    pred, h1, h2 = gm.forward(dummy_input)
    print(f"[TEST] Input: {dummy_input}")
    print(f"[TEST] Hidden 1 (sample first 4): {h1[:4]}")
    print(f"[TEST] Output Prediksi Golden Model (INT8): {pred}")
    if gm.trained:
        print(f"[TEST] = {gm.to_watt(pred):.1f} W (rata-rata 60 menit ke depan)")
