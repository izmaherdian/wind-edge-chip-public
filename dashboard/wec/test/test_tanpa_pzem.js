// Uji function node "Mesin WEC" untuk dua kasus yang dulu membuat dashboard tertahan di "menunggu":
//   1. PZEM tidak merespons (Raspi hanya mengirim data cuaca, tanpa power/voltage/current/ML_Status)
//      -> prediksi tetap dibuat (mode cadangan: daya dari kurva daya), status "PZEM tidak merespons"
//   2. Deploy/restart -> riwayat dipulihkan dari snapshot WEC/state, prediksi langsung ada tanpa pemanasan 60 menit
// Jalankan: node dashboard/wec/test/test_tanpa_pzem.js
const fs = require("fs"), path = require("path");
const here = path.join(__dirname, "..");
const core = fs.readFileSync(path.join(here, "engine_core.js"), "utf8").replace(/if \(typeof module[^\n]*\n/, "");
const body = core + "\nconst BUNDLE = " + fs.readFileSync(path.join(here, "model_bundle.json"), "utf8") + ";\n" + fs.readFileSync(path.join(here, "engine_node.js"), "utf8");
const fn = new Function("msg", "context", "flow", "node", body);
const readJSON = (f) => JSON.parse(fs.readFileSync(f, "utf8").replace(/\bNaN\b/g, "null"));
const mins = readJSON(path.join(here, "test", "ref", "minutes.json"));
const om = readJSON(path.join(here, "test", "ref", "om.json"));
const byM = new Map(mins.map((x) => [x.m, x]));
let fake = 0; Date.now = () => fake;
let fail = 0;
const check = (name, ok, info) => { console.log(`${ok ? "LULUS" : "GAGAL"}  ${name}  ${info || ""}`); if (!ok) fail++; };

function engine() {
  const store = {}, ctx = { get: (k) => store[k], set: (k, v) => { store[k] = v; } };
  const fl = { get: () => undefined, set: () => {} };          // flow context kosong: meniru server baru restart
  const call = (msg) => fn(msg, ctx, fl, { status: () => {} });
  fake = mins[0].m * 60000;
  call({ topic: "wec/openmeteo", payload: { hourly: { time: om.time.map((t) => new Date(t).toISOString().slice(0, 16)), wind_speed_10m: om.wind, surface_pressure: om.pressure } } });
  return call;
}
// satu menit data: 12 batch (tiap 5 detik); pzem=false meniru Raspi saat PZEM diam (hanya topik cuaca)
function minute(call, x, pzem) {
  for (let k = 0; k < 12; k++) {
    fake = x.m * 60000 + k * 5000 + 100;
    const send = (key, val) => call({ topic: "TurbinAngin/" + key, payload: val });
    send("Windspeed", "1.2");
    if (pzem) { const off = x.on < 0.5; send("power", off ? "OFF" : String(x.p)); send("voltage", off ? "OFF" : "30"); send("current", off ? "OFF" : String(x.p / 30)); }
    send("windspeedstation", x.ws === null ? "0" : String(x.ws));
    send("winddirdeg", String(x.ds === null ? -115 : Math.atan2(x.ds, x.dc) * 180 / Math.PI));
    send("humidity", String(x.rh ?? 70)); send("temperature", String(x.tc ?? 24));
    if (pzem) send("ML_Status", "Normal");
  }
  fake = (x.m + 1) * 60000 + 500;
  return call({ topic: "wec/tick" });
}
const pick = (r, t) => r && r[0] && r[0].find((o) => o.topic === t);
const actual60 = (m) => { const v = []; for (let k = m + 1; k <= m + 60; k++) { const x = byM.get(k); if (x && x.p !== null) v.push(x.p); } return v.length >= 50 ? v.reduce((a, b) => a + b, 0) / v.length : null; };
const mae = (a) => a.reduce((s, x) => s + x, 0) / a.length;

// ---------- 1. PZEM diam selama data uji 1-20 Okt (3 jam pertama normal) vs PZEM normal, menit yang sama ----------
const start = Math.floor(Date.UTC(2026, 9, 1) / 60000), stop = Math.floor(Date.UTC(2026, 9, Number(process.env.HARI || 20) + 1) / 60000);
const cad = engine(), nor = engine();
const eC = [], eN = [], eP = [], modes = {};
let lastMl;
for (let m = start - 180; m < stop; m++) {
  const x = byM.get(m); if (!x) continue;
  const mc = pick(minute(cad, x, m < start), "wec_ml"), mn = pick(minute(nor, x, true), "wec_ml");
  if (m < start || !mc) continue;
  lastMl = mc.payload;
  const c = mc.payload.forecast, n = mn && mn.payload.forecast, y = actual60(m);
  if (c) modes[c.mode] = (modes[c.mode] || 0) + 1;
  if (c && n && n.persistence_w !== null && y !== null) { eC.push(Math.abs(c.power_w - y)); eN.push(Math.abs(n.power_w - y)); eP.push(Math.abs(n.persistence_w - y)); }
}
check("prediksi tetap dibuat saat PZEM diam", eC.length > 250 * Number(process.env.HARI || 20), `${eC.length} menit dinilai, mode ${JSON.stringify(modes)}`);
check("mode cadangan lebih baik dari persistence (yang butuh PZEM)", mae(eC) < mae(eP),
  `MAE cadangan ${mae(eC).toFixed(2)} W · normal ${mae(eN).toFixed(2)} W · persistence ${mae(eP).toFixed(2)} W (menit yang sama)`);
check("label status menjelaskan penyebab", lastMl.status.label === "PZEM tidak merespons", lastMl.status.label);

// ---------- 2. snapshot + pulihkan: cari 130 menit bersambung ----------
let s0 = start; for (;;) { let ok = true; for (let k = 0; k < 131; k++) if (!byM.get(s0 + k)) { ok = false; s0 += k + 1; break; } if (ok) break; }
const a = engine();
let state = null;
for (let m = s0; m < s0 + 130; m++) { const r = minute(a, byM.get(m), true); const s = r && r[1] && r[1].find((o) => o.topic === "WEC/state"); if (s) state = s; }
check("snapshot WEC/state retained dikirim", state && state.retain === true, state ? `${(state.payload.length / 1024).toFixed(1)} KB` : "");
const b = engine();                                        // node baru (setelah deploy), konteks kosong
b({ topic: "WEC/state", payload: state.payload });
const ml2 = pick(minute(b, byM.get(s0 + 130), true), "wec_ml");
check("setelah restart prediksi langsung ada (tanpa pemanasan 60 menit)", ml2 && ml2.payload.forecast && ml2.payload.forecast.power_w !== null,
  ml2 && ml2.payload.forecast ? `P1j ${ml2.payload.forecast.power_w} W, menit data 60 = ${ml2.payload.menit_data_60}` : JSON.stringify(ml2 && ml2.payload.alasan));
process.exit(fail ? 1 : 0);
