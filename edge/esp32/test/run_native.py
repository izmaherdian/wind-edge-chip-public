"""Uji wec_core (C++ ESP32) di laptop terhadap rujukan Python dan mesin JS Node-RED.

  1. MLP INT8 vs test vector golden model (h1, h2, keluaran) untuk kedua model
  2. Kuantisasi float -> INT8 vs Python (np.round setengah-ke-genap)
  3. 16+16 fitur dari riwayat per menit vs Python (dashboard/wec/test/ref, toleransi sama dengan test_engine.js)
  4. Baterai (langkah + prakiraan SoC) vs engine_core.js, 2.000 kasus acak

Rujukan dibuat oleh: ml/.venv/bin/python dashboard/wec/test/make_reference.py
Jalankan:            python3 edge/esp32/test/run_native.py
"""

import csv
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ESP = ROOT / "edge" / "esp32"
REF = ROOT / "dashboard" / "wec" / "test" / "ref"
fail = 0


def check(name, ok, info=""):
    global fail
    print(f"{'LULUS' if ok else 'GAGAL'}  {name}  {info}")
    fail += not ok


def build(tmp):
    exe = Path(tmp) / "wec_cli"
    cmd = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-DWEC_OM_CAP=6000",
           f"-I{ESP / 'lib' / 'wec_core'}", f"-I{ROOT / 'ml' / 'forecast' / 'model' / 'export'}",
           f"-I{ROOT / 'ml' / 'status' / 'model' / 'export'}",
           str(ESP / "test" / "wec_cli.cpp"), str(ESP / "lib" / "wec_core" / "wec_core.cpp"), "-o", str(exe)]
    subprocess.run(cmd, check=True)
    return exe


def run(exe, lines):
    r = subprocess.run([str(exe)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    return [x.split() for x in r.stdout.splitlines()]


def nz(x):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else repr(float(x))


def load(name):
    return json.loads((REF / name).read_text().replace("NaN", "null"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(tmp)

        # 1. MLP vs test vector
        for md, name, f in ((0, "prediksi daya", "ml/forecast/model/export/test_vectors.csv"),
                            (1, "kurva daya", "ml/status/model/export/test_vectors.csv")):
            rows = list(csv.DictReader(open(ROOT / f)))
            out = run(exe, [f"V {md} " + " ".join(r[f"x{i}"] for i in range(16)) for r in rows])
            bad = sum(o[1:] != [r["out_q"]] + [r[f"h1_{i}"] for i in range(32)] + [r[f"h2_{i}"] for i in range(16)]
                      for o, r in zip(out, rows))
            check(f"MLP {name} vs test vector (h1, h2, out)", bad == 0 and len(out) == len(rows), f"{len(rows)} vektor, {bad} beda")

        # 1a. model offline vs golden model (vektor acak + vektor uji dengan masukan ke-16 = 0)
        sys.path.insert(0, str(ROOT / "ml"))
        from golden_model import GoldenModelINT8
        gmo = GoldenModelINT8(model_path=str(ROOT / "ml" / "forecast" / "model" / "mlp_int8_offline.json"))
        rv = random.Random(3)
        rows = list(csv.DictReader(open(ROOT / "ml/forecast/model/export/test_vectors.csv")))
        xs = [[int(r[f"x{i}"]) for i in range(15)] + [0] for r in rows] + [[rv.randint(-128, 127) for _ in range(16)] for _ in range(500)]
        out = run(exe, [f"V 2 " + " ".join(map(str, x)) for x in xs])
        bad = 0
        for o, x in zip(out, xs):
            y, h1, h2 = gmo.forward(x)
            bad += [int(v) for v in o[1:]] != [y] + list(h1) + list(h2)
        check("MLP offline (tanpa Open-Meteo) vs golden model", bad == 0, f"{len(xs)} vektor, {bad} beda")

        # 1b. paket UART berbingkai + CRC-8 (hw/rtl/top_soc.v, crc8 sama dengan hw/sim/crc8_util.py)
        def crc8(data):
            c = 0
            for x in data:
                c ^= x
                for _ in range(8):
                    c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
            return c
        rnd = random.Random(5)
        xs = [[rnd.randint(-128, 127) for _ in range(16)] for _ in range(300)]
        out = run(exe, ["T " + " ".join(map(str, x)) for x in xs])
        want = [[0xAA, 0x55] + [v & 0xFF for v in x] + [crc8([v & 0xFF for v in x])] for x in xs]
        bad = sum([int(v) for v in o[1:]] != w for o, w in zip(out, want))
        ref_alif = crc8(bytes([1, 2, 255, 0, 3, 254, 1, 0, 255, 2, 1, 0, 255, 1, 0, 2]))
        replies, expect = [], []
        for k in range(300):
            st, pred, cyc = rnd.choice([0, 0, 0, 0xE1, 0xE2]), rnd.randint(0, 127), rnd.randint(0, 65535)
            body = [st, pred, cyc >> 8, cyc & 0xFF]
            fr = [0x55, 0xAA] + body + [crc8(body)]
            rusak = k % 7 == 0
            if rusak:
                fr[3 + k % 3] ^= 0x10                # satu bit terbalik
            replies.append(fr)
            expect.append(st == 0 and not rusak)
        out2 = run(exe, ["R " + " ".join(map(str, f)) for f in replies])
        bad += sum((o[1] == "1") != e for o, e in zip(out2, expect))
        check("paket UART 19 B / 7 B + CRC-8 = protokol top_soc.v", bad == 0,
              f"300 paket kirim + 300 balasan (termasuk CRC rusak, status E1/E2), {bad} beda; CRC contoh Alif 0x{ref_alif:02X}")

        # 2. kuantisasi (rujukan dibuat dari data mentah, tidak masuk git)
        if not (REF / "features.json").exists():
            print("LEWATI  uji 2-4: rujukan belum ada. Buat dulu: ml/.venv/bin/python dashboard/wec/test/make_reference.py")
            sys.exit(1 if fail else 0)
        feats = load("features.json")
        fcn = ["p_now", "p_lag5", "p_lag15", "p_lag30", "p_lag60", "p_mean60", "w_now", "w_mean10", "w_mean60",
               "w3_mean10", "dir_sin", "dir_cos", "hour_sin", "hour_cos", "rho", "om_wind_next"]
        pcn = ["w_now", "w_mean10", "w_mean30", "w_mean60", "w3_mean10", "w3_mean30", "w_max10", "w_std10",
               "dir_sin", "dir_cos", "hour_sin", "hour_cos", "rho", "humidity_pct", "temp_c", "om_wind_now"]
        q = []
        for r in feats:
            q.append("Q 0 " + " ".join(nz(r["fc"][k]) for k in fcn))
            q.append("Q 1 " + " ".join(nz(r["pc"][k]) for k in pcn))
        out = run(exe, q)
        bad = 0
        for k, r in enumerate(feats):
            a, b = out[2 * k], out[2 * k + 1]
            bad += a[1] != "1" or [int(v) for v in a[2:]] != r["xq_fc"] or b[1] != "1" or [int(v) for v in b[2:]] != r["xq_pc"]
        check("kuantisasi 16+16 fitur", bad == 0, f"{len(feats)} sampel, {bad} beda")

        # 3. fitur dari riwayat (ring buffer 256 menit: masukkan menit berurutan, tanya tepat waktunya)
        mins = sorted(load("minutes.json"), key=lambda x: x["m"])
        om = load("om.json")
        lines = [f"O {t // 1000} {nz(w)} {nz(p)}" for t, w, p in zip(om["time"], om["wind"], om["pressure"])]
        queries = sorted(feats, key=lambda r: r["t"])
        j = 0
        for r in queries:
            m = r["t"] // 60000
            while j < len(mins) and mins[j]["m"] <= m:
                x = mins[j]
                lines.append("M {} {} {}".format(x["m"], x.get("n", 1), " ".join(
                    nz(x.get(k)) for k in ("p", "on", "v", "i", "ws", "wsMax", "ds", "dc", "rh", "tc"))))
                j += 1
            lines.append(f"F {m}")
        out = [o for o in run(exe, lines) if o[0] == "F"]
        tol = {"rho": 2e-3, "om_wind_next": 1e-6, "om_wind_now": 1e-6}
        bad, worst, same = 0, {}, 0
        for o, r in zip(out, queries):
            v = [float(x) for x in o[2:]]
            for names, py, off, g in ((fcn, r["fc"], 0, "fc"), (pcn, r["pc"], 16, "pc")):
                for i, k in enumerate(names):
                    d = abs(py[k] - v[off + i])
                    lim = tol.get(k, 1e-6 * max(1, abs(py[k])))
                    if not d <= lim:
                        bad += 1
                        worst[f"{g}.{k}"] = max(worst.get(f"{g}.{k}", 0), d)
            qq = run(exe, ["Q 0 " + " ".join(o[2:18])])[0]
            same += [int(x) for x in qq[2:]] == r["xq_fc"]
        check("fitur C++ = fitur Python", bad == 0 and len(out) == len(queries), f"{len(queries)} sampel, {bad} nilai beda {worst}")
        print(f"      input INT8 dari fitur C++ identik dengan Python: {same}/{len(queries)}")

        # 3b. mode PZEM diam: daya kosong diganti daya wajar, dibandingkan dengan engine_core.js (est)
        rnd = random.Random(1)
        drop = {x["m"] for x in mins if rnd.random() < 0.5}
        gone = {x["m"] for x in mins if rnd.random() < 0.3}           # menit hilang total (Raspi reboot), untuk mode longgar
        est = {x["m"]: round(rnd.uniform(0, 60), 3) for x in mins if x["m"] in drop}
        qs = [r["t"] // 60000 for r in queries[:120]]
        js_in = {"mins": [dict(x, p=None) if x["m"] in drop else x for x in mins if qs[0] - 260 <= x["m"] <= qs[-1] and x["m"] not in gone],
                 "est": [[k, v] for k, v in est.items() if qs[0] - 260 <= k <= qs[-1]], "q": qs, "om": om}
        js = f"""
const {{ createEngine }} = require({json.dumps(str(ROOT / 'dashboard' / 'wec' / 'engine_core.js'))});
const B = JSON.parse(require('fs').readFileSync({json.dumps(str(ROOT / 'dashboard' / 'wec' / 'model_bundle.json'))}, 'utf8').replace(/\\bNaN\\b/g, 'null'));
const E = createEngine(B), d = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const num = (x) => (x === null || x === undefined ? NaN : x);
const hist = new Map(d.mins.map((x) => [x.m, Object.fromEntries(Object.entries(x).map(([k, v]) => [k, num(v)]))]));
const est = new Map(d.est);
const om = {{ time: d.om.time, wind: d.om.wind.map(num), pressure: d.om.pressure.map(num) }};
const row = (f) => [...Object.values(f.fc), ...Object.values(f.pc), f.pEstimated];
console.log(JSON.stringify(d.q.map((m) => [row(E.features(hist, m, om, est)), row(E.features(hist, m, om, est, {{ longgar: true }}))])));
"""
        ref = json.loads(subprocess.run(["node", "-e", js], input=json.dumps(js_in), capture_output=True, text=True, check=True).stdout)
        lines = [f"O {t // 1000} {nz(w)} {nz(p)}" for t, w, p in zip(om["time"], om["wind"], om["pressure"])]
        byk = {x["m"]: x for x in js_in["mins"]}
        estk = dict((k, v) for k, v in js_in["est"])
        qset = set(qs)
        for m in range(qs[0] - 260, qs[-1] + 1):          # urut waktu: ring buffer C++ hanya 256 menit
            x = byk.get(m)
            if x:
                lines.append("M {} {} {}".format(m, x.get("n", 1), " ".join(nz(x.get(k)) for k in ("p", "on", "v", "i", "ws", "wsMax", "ds", "dc", "rh", "tc"))))
            if m in estk:
                lines.append(f"E {m} {estk[m]!r}")
            if m in qset:
                lines.append(f"G {m}")
                lines.append(f"L {m}")
        res = run(exe, lines)
        for tag, k, name in (("G", 0, "mode PZEM diam (daya wajar)"), ("L", 1, "mode celah (syarat longgar, 30% menit hilang)")):
            out = [o for o in res if o[0] == tag]
            bad = 0
            for o, r in zip(out, ref):
                v = [float(x) for x in o[2:34]] + [int(o[-1])]
                for a, b in zip(v, r[k]):
                    if b is None:
                        bad += not math.isnan(a)
                    else:
                        bad += not abs(a - b) <= 1e-6 * max(1, abs(b))
                        if os.environ.get("DEBUG") and not abs(a - b) <= 1e-6 * max(1, abs(b)):
                            print("   beda", tag, o[1], v.index(a), a, b)
            check(f"{name} C++ = engine_core.js", bad == 0 and len(out) == len(ref), f"{len(ref)} menit, {bad} nilai beda")

        # 4. baterai vs engine_core.js
        rnd = random.Random(0)
        cases = [(rnd.uniform(0.05, 1.0), rnd.choice([0, 0.5, rnd.uniform(0, 120)]),
                  1790000000 + rnd.randrange(0, 86400 * 3, 60)) for _ in range(2000)]
        js = f"""
const {{ createEngine }} = require({json.dumps(str(ROOT / 'dashboard' / 'wec' / 'engine_core.js'))});
const B = JSON.parse(require('fs').readFileSync({json.dumps(str(ROOT / 'dashboard' / 'wec' / 'model_bundle.json'))}, 'utf8').replace(/\\bNaN\\b/g, 'null'));
const E = createEngine(B);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify(cases.map(([s, p, t]) => {{ const b = E.batteryStep(s, p, t * 1000), f = E.socForecast(s, p, t * 1000);
  return [b.soc, b.toBatt, b.dumped, b.grid, b.load, f.soc, f.energyWh, f.gridSoon ? 1 : 0]; }})));
"""
        ref = json.loads(subprocess.run(["node", "-e", js], input=json.dumps(cases), capture_output=True, text=True, check=True).stdout)
        out = run(exe, [f"B {s!r} {p!r} {t}" for s, p, t in cases] + [f"S {s!r} {p!r} {t}" for s, p, t in cases])
        bad = 0
        for k, r in enumerate(ref):
            b, s = [float(x) for x in out[k][1:]], [float(x) for x in out[len(cases) + k][1:]]
            bad += any(abs(a - c) > 1e-9 for a, c in zip(b + s, r))
        check("baterai C++ = engine_core.js (langkah + prakiraan SoC)", bad == 0, f"{len(cases)} kasus, {bad} beda")

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
