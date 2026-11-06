"""Ekspor model INT8 offline ke header C untuk ESP32 (ml/forecast/model/export/mlp_offline_int8.h).

Bobot saja (awalan OFF_); fungsi mlp_layer dan skala fitur dipakai dari mlp_int8.h karena topologi,
aritmetika, dan skala fiturnya sama. Pemakaian: ml/.venv/bin/python ml/forecast/export_offline.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
from golden_model import GoldenModelINT8  # noqa: E402

MODEL = ROOT / "ml" / "forecast" / "model" / "mlp_int8_offline.json"
OUT = ROOT / "ml" / "forecast" / "model" / "export" / "mlp_offline_int8.h"


def main():
    gm = GoldenModelINT8(model_path=str(MODEL))
    arr = lambda name, vals, t: f"static const {t} {name}[{len(vals)}] = {{{', '.join(str(v) for v in vals)}}};"
    flat = lambda w: [w[i][j] for j in range(len(w[0])) for i in range(len(w))]   # per neuron j, lalu input i
    s = ["/* MLP INT8 MODE OFFLINE (tanpa Open-Meteo; masukan ke-16 = 0). Dihasilkan ml/forecast/export_offline.py.",
         " * Topologi, requantize, dan skala fitur sama dengan mlp_int8.h (pakai mlp_layer dan MLP_FEAT_* dari sana).",
         " * watt = out * MLP_OUT_SCALE_W. Jangan diedit manual. */",
         "#pragma once", "#include <stdint.h>", "",
         arr("OFF_W1", flat(gm.w1), "int8_t"), arr("OFF_W2", flat(gm.w2), "int8_t"), arr("OFF_W3", flat(gm.w3), "int8_t"), "",
         arr("OFF_B1", gm.b1, "int32_t"), arr("OFF_B2", gm.b2, "int32_t"), arr("OFF_B3", gm.b3, "int32_t"), ""]
    OUT.write_text("\n".join(s))
    print("ditulis", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
