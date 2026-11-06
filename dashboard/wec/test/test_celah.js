// Uji mesin WEC saat data berlubang (Raspi reboot karena internet mati, ±4 menit hilang tiap 10-30 menit).
// Dibandingkan pada menit yang sama dengan mesin yang menerima data utuh. Jalankan: node dashboard/wec/test/test_celah.js
const fs = require("fs"), path = require("path");
const here = path.join(__dirname, "..");
const core = fs.readFileSync(path.join(here, "engine_core.js"), "utf8").replace(/if \(typeof module[^\n]*\n/, "");
let body = core + "\nconst BUNDLE = " + fs.readFileSync(path.join(here, "model_bundle.json"), "utf8") + ";\n" + fs.readFileSync(path.join(here, "engine_node.js"), "utf8");
if (process.env.KETAT) body = body.split("{ longgar: true }").join("{ longgar: false }");   // pembanding: perilaku sebelum mode celah
const fn = new Function("msg", "context", "flow", "node", body);
const readJSON = (f) => JSON.parse(fs.readFileSync(f, "utf8").replace(/\bNaN\b/g, "null"));
const mins = readJSON(path.join(here, "test", "ref", "minutes.json"));
const om = readJSON(path.join(here, "test", "ref", "om.json"));
const byM = new Map(mins.map((x) => [x.m, x]));
let fake = 0; Date.now = () => fake;
let fail = 0;
const check = (name, ok, info) => { console.log(`${ok ? "LULUS" : "GAGAL"}  ${name}  ${info || ""}`); if (!ok) fail++; };
function engine() {
  const store = {}, ctx = { get: (k) => store[k], set: (k, v) => { store[k] = v; } }, fl = { get: () => undefined, set: () => {} };
  const call = (msg) => fn(msg, ctx, fl, { status: () => {} });
  fake = mins[0].m * 60000;
  call({ topic: "wec/openmeteo", payload: { hourly: { time: om.time.map((t) => new Date(t).toISOString().slice(0, 16)), wind_speed_10m: om.wind, surface_pressure: om.pressure } } });
  return call;
}
function minute(call, x, on) {
  if (on) for (let k = 0; k < 12; k++) {
    fake = x.m * 60000 + k * 5000 + 100;
    const send = (key, val) => call({ topic: "TurbinAngin/" + key, payload: val });
    const off = x.on < 0.5;
    send("power", off ? "OFF" : String(x.p)); send("voltage", off ? "OFF" : "30"); send("current", off ? "OFF" : String(x.p / 30));
    send("windspeedstation", x.ws === null ? "0" : String(x.ws));
    send("winddirdeg", String(x.ds === null ? -115 : Math.atan2(x.ds, x.dc) * 180 / Math.PI));
    send("humidity", String(x.rh ?? 70)); send("temperature", String(x.tc ?? 24)); send("ML_Status", "Normal");
  }
  fake = (x.m + 1) * 60000 + 500;
  const r = call({ topic: "wec/tick" });
  return r && r[0] && r[0].find((o) => o.topic === "wec_ml");
}
const actual60 = (m) => { const v = []; for (let k = m + 1; k <= m + 60; k++) { const x = byM.get(k); if (x && x.p !== null) v.push(x.p); } return v.length >= 50 ? v.reduce((a, b) => a + b, 0) / v.length : null; };
const mae = (a) => a.reduce((s, x) => s + x, 0) / a.length;
// pola reboot: tiap 10-30 menit, 4 menit hilang (seperti log_reboot.txt 21 Okt: 07.00, 07.10, 07.40)
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const start = Math.floor(Date.UTC(2026, 9, 1) / 60000), stop = Math.floor(Date.UTC(2026, 9, Number(process.env.HARI || 20) + 1) / 60000);
const hilang = new Set(); for (let t = start - 200; t < stop; t += 10 + Math.floor(rnd() * 21)) for (let k = 0; k < 4; k++) hilang.add(t + k);
const A = engine(), N = engine();
let dinilai = 0, adaA = 0, adaN = 0, celah = 0; const eA = [], eN = [], eP = [];
for (let m = start - 200; m < stop; m++) {
  const x = byM.get(m); if (!x) continue;
  const a = minute(A, x, !hilang.has(m)), n = minute(N, x, true);
  if (m < start) continue;
  const fa = a && a.payload.forecast, fnn = n && n.payload.forecast, y = actual60(m);
  if (fnn && y !== null) { dinilai++; if (fa) adaA++; adaN++; }
  if (fa && fa.celah) celah++;
  if (fa && fnn && y !== null && fnn.persistence_w !== null) { eA.push(Math.abs(fa.power_w - y)); eN.push(Math.abs(fnn.power_w - y)); eP.push(Math.abs(fnn.persistence_w - y)); }
}
const kover = adaA / dinilai;
console.log(`      ${hilang.size} menit dibuang (${(100 * hilang.size / (stop - start + 200)).toFixed(0)}%); prediksi dengan mode celah: ${celah} menit`);
check("prediksi tetap ada walau data berlubang", kover > 0.9, `cakupan ${(100 * kover).toFixed(1)}% dari ${dinilai} menit`);
check("akurasi dengan celah mendekati data utuh", mae(eA) < 1.15 * mae(eN) && mae(eA) < mae(eP),
  `MAE berlubang ${mae(eA).toFixed(2)} W · utuh ${mae(eN).toFixed(2)} W · persistence ${mae(eP).toFixed(2)} W (${eA.length} menit sama)`);
process.exit(fail ? 1 : 0);
