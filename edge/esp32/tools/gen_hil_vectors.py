"""Buat include/hil_vectors.h dari ml/forecast/model/export/test_vectors.csv (597 sampel uji nyata 1-20 Okt).

Pemakaian: python3 edge/esp32/tools/gen_hil_vectors.py
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "ml" / "forecast" / "model" / "export" / "test_vectors.csv"
OUT = ROOT / "edge" / "esp32" / "include" / "hil_vectors.h"

rows = list(csv.DictReader(open(SRC)))
xs = ",\n".join("  {" + ", ".join(r[f"x{i}"] for i in range(16)) + "}" for r in rows)
OUT.write_text(f"""/* Vektor uji HIL dari {SRC.relative_to(ROOT)}. Dihasilkan otomatis oleh tools/gen_hil_vectors.py. */
#pragma once
#include <stdint.h>

#define HIL_N {len(rows)}
static const int8_t HIL_X[HIL_N][16] = {{
{xs}
}};
static const int8_t HIL_OUT[HIL_N] = {{{", ".join(r["out_q"] for r in rows)}}};
""")
print("ditulis", OUT.relative_to(ROOT), len(rows), "vektor")
