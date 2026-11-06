"""Buat lib/wec_core/wec_bundle.h dari dashboard/wec/model_bundle.json (sumber yang sama dengan mesin Node-RED).

Skala fitur ditulis dengan presisi penuh (double), supaya kuantisasi INT8 sama persis dengan Python;
skala 6 digit di mlp_int8.h bisa membuat beda 1 LSB di batas pembulatan.

Pemakaian: python3 edge/esp32/tools/gen_bundle.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "dashboard" / "wec" / "model_bundle.json"
OUT = ROOT / "edge" / "esp32" / "lib" / "wec_core" / "wec_bundle.h"


def d(x):
    return repr(float(x))


def arr(name, vals, ctype="double"):
    return f"static const {ctype} {name}[{len(vals)}] = {{{', '.join(d(v) for v in vals)}}};"


def main():
    b = json.loads(SRC.read_text().replace("NaN", "null"))
    s = ["/* Konstanta mesin WEC untuk ESP32. Dihasilkan otomatis oleh edge/esp32/tools/gen_bundle.py",
         f" * dari dashboard/wec/model_bundle.json (dibuat {b.get('dibuat', '?')}). Jangan diedit manual. */",
         "#pragma once", ""]
    for key, pre in (("forecast", "FC"), ("powercurve", "PC")):
        m = b[key]
        s.append(f"/* {key}: " + ", ".join(m["fitur"]) + " */")
        s.append(arr(f"{pre}_CENTER", [m["skala_fitur"][f]["center"] for f in m["fitur"]]))
        s.append(arr(f"{pre}_SCALE", [m["skala_fitur"][f]["scale"] for f in m["fitur"]]))
        s.append(f"static const double {pre}_W_PER_LSB = {d(m['skala_keluaran_W_per_lsb'])};")
        s.append("")
    a = b["powercurve"]["ambang_status"]
    s += [f"static const double STATUS_BAWAH = {d(a['bawah'])};",
          f"static const double STATUS_ATAS = {d(a['atas'])};",
          f"static const double STATUS_MIN_WAJAR_W = {d(a['min_daya_wajar_W'])};", ""]
    t = b["typical"]
    s += [f"static const double TYP_RHO = {d(t['rho'])};",
          f"static const double TYP_TEMP_C = {d(t['temp_c'])};",
          f"static const double TYP_RH = {d(t['humidity_pct'])};", ""]
    bins = b["interval"]["bins"]
    s += [f"/* interval P10-P90 empiris ({b['interval']['sumber']}) */",
          f"#define IV_N {len(bins)}",
          arr("IV_DARI", [x["dari"] for x in bins]), arr("IV_SAMPAI", [x["sampai"] for x in bins]),
          arr("IV_P10", [x["p10"] for x in bins]), arr("IV_P90", [x["p90"] for x in bins]), ""]
    bat = b["battery"]
    s += [f"/* baterai + inverter ({bat['inverter']}) */"]
    for k in ("eta_charge_controller", "kapasitas_Wh", "eta_isi", "eta_buang", "soc_min", "soc_max", "soc_awal",
              "beban_dasar_W", "beban_malam_W"):
        s.append(f"static const double BAT_{k.upper()} = {d(bat[k])};")
    s += [f"static const int BAT_JAM_MALAM_DARI = {int(bat['jam_malam_WIB'][0])};",
          f"static const int BAT_JAM_MALAM_SAMPAI = {int(bat['jam_malam_WIB'][1])};",
          f"#define INV_N {len(bat['inverter_ac_W'])}",
          arr("INV_AC_W", bat["inverter_ac_W"]), arr("INV_DC_W", bat["inverter_dc_W"]), ""]
    OUT.write_text("\n".join(s))
    print("ditulis", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
