// Uji kesetaraan mesin WEC (JavaScript) dengan Python.
// Siapkan rujukan: ml/.venv/bin/python dashboard/wec/test/make_reference.py
// Jalankan:        node dashboard/wec/test/test_engine.js
const fs = require("fs");
const path = require("path");
const { createEngine } = require("../engine_core.js");

const dir = path.join(__dirname, "ref");
const readJSON = (f) => JSON.parse(fs.readFileSync(f, "utf8").replace(/\bNaN\b/g, "null"));
const B = readJSON(path.join(__dirname, "..", "model_bundle.json"));
const E = createEngine(B);
const root = path.join(__dirname, "..", "..", "..");
let fail = 0;
const check = (name, ok, info) => { console.log(`${ok ? "LULUS" : "GAGAL"}  ${name}${info ? "  " + info : ""}`); if (!ok) fail++; };

// 1. MLP bit-exact dengan test vector (golden model = RTL)
for (const [name, model, csv] of [
  ["prediksi daya", B.forecast, "ml/forecast/model/export/test_vectors.csv"],
  ["kurva daya", B.powercurve, "ml/status/model/export/test_vectors.csv"],
]) {
  const lines = fs.readFileSync(path.join(root, csv), "utf8").trim().split("\n");
  const head = lines[0].split(",");
  let bad = 0;
  for (const line of lines.slice(1)) {
    const r = Object.fromEntries(line.split(",").map((v, k) => [head[k], Number(v)]));
    const x = [...Array(16).keys()].map((i) => r[`x${i}`]);
    const o = E.forward(model, x);
    const h1ok = o.h1.every((v, i) => v === r[`h1_${i}`]), h2ok = o.h2.every((v, i) => v === r[`h2_${i}`]);
    if (o.out !== r.out_q || !h1ok || !h2ok) bad++;
  }
  check(`MLP ${name} vs test vector (h1, h2, out)`, bad === 0, `${lines.length - 1} vektor, ${bad} beda`);
}

// 2. Kuantisasi fitur float -> INT8 sama dengan Python (np.round setengah-ke-genap)
const ref = readJSON(path.join(dir, "features.json"));
let qbad = 0;
for (const r of ref) {
  const a = E.quantize(B.forecast, r.fc), b = E.quantize(B.powercurve, r.pc);
  if (a.some((v, i) => v !== r.xq_fc[i]) || b.some((v, i) => v !== r.xq_pc[i])) qbad++;
}
check("kuantisasi 16+16 fitur", qbad === 0, `${ref.length} sampel, ${qbad} beda`);

// 3. Fitur dari riwayat per menit vs Python
const hist = new Map();
for (const m of readJSON(path.join(dir, "minutes.json"))) hist.set(m.m, m);
const om = readJSON(path.join(dir, "om.json"));
const tol = { rho: 2e-3, om_wind_next: 1e-6, om_wind_now: 1e-6 };
let fbad = 0, outSame = 0, outClose = 0, worst = {};
for (const r of ref) {
  const m = Math.floor(r.t / 60000);
  const f = E.features(hist, m, om);
  for (const [grp, py, js] of [["fc", r.fc, f.fc], ["pc", r.pc, f.pc]]) {
    for (const k of Object.keys(py)) {
      const d = Math.abs(py[k] - js[k]);
      const lim = tol[k] ?? 1e-6 * Math.max(1, Math.abs(py[k]));
      if (!(d <= lim)) { fbad++; worst[`${grp}.${k}`] = Math.max(worst[`${grp}.${k}`] || 0, d); }
    }
  }
  const p1 = E.predict(B.forecast, f.fc), q1 = E.quantize(B.forecast, r.fc);
  const exact = p1 && p1.xq.every((v, i) => v === q1[i]);
  if (exact) outSame++; else if (p1 && Math.abs(E.forward(B.forecast, q1).out - p1.out_q) <= 1) outClose++;
}
check("fitur JS = fitur Python", fbad === 0, `${ref.length} sampel, ${fbad} nilai beda ${JSON.stringify(worst)}`);
console.log(`      input INT8 identik: ${outSame}/${ref.length}; sisanya selisih keluaran <= 1 LSB: ${outClose}`);

// 4. Baterai: satu langkah sama dengan rumus sim_battery.py
const st = E.batteryStep(0.5, 30, Date.UTC(2026, 9, 1, 5, 0));   // 12.00 WIB, beban 6 W
check("langkah baterai (SoC naik saat surplus)", st.soc > 0.5 && st.grid === 0, `soc=${st.soc.toFixed(5)} load=${st.load}`);

process.exit(fail ? 1 : 0);
