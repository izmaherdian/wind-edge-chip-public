// Simulasi function node "Mesin WEC": putar ulang data per menit (Okt) sebagai pesan MQTT, lalu cek keluaran.
const fs = require("fs"), path = require("path");
const here = path.join(__dirname, "..");
const core = fs.readFileSync(path.join(here, "engine_core.js"), "utf8").replace(/if \(typeof module[^\n]*\n/, "");
const wrap = fs.readFileSync(path.join(here, "engine_node.js"), "utf8");
const bundle = fs.readFileSync(path.join(here, "model_bundle.json"), "utf8");
const body = core + "\nconst BUNDLE = " + bundle + ";\n" + wrap;
const fn = new Function("msg", "context", "flow", "node", body);
const store = {}, ctx = { get: (k) => store[k], set: (k, v) => { store[k] = v; } };
const flowCtx = { get: () => undefined, set: () => {} };
const node = { status: () => {} };
const readJSON = (f) => JSON.parse(fs.readFileSync(f, "utf8").replace(/\bNaN\b/g, "null"));
const mins = readJSON(path.join(here, "test", "ref", "minutes.json"));
const om = readJSON(path.join(here, "test", "ref", "om.json"));
let fake = 0; const realNow = Date.now; Date.now = () => fake;
// Open-Meteo dalam format API (waktu ISO tanpa Z)
fake = mins[0].m * 60000;
fn({ topic: "wec/openmeteo", payload: { hourly: { time: om.time.map((t) => new Date(t).toISOString().slice(0, 16)), wind_speed_10m: om.wind, surface_pressure: om.pressure } } }, ctx, flowCtx, node);
const start = Math.floor(Date.UTC(2026, 9, 1) / 60000), stop = start + 3 * 1440;
let n = 0, preds = [], last;
for (const x of mins) {
  if (x.m < start - 120 || x.m > stop) continue;
  for (let k = 0; k < 12; k++) {                     // 12 sampel/menit (tiap 5 detik)
    fake = x.m * 60000 + k * 5000 + 100;
    const off = x.on < 0.5;
    const send = (key, val) => fn({ topic: "TurbinAngin/" + key, payload: val }, ctx, flowCtx, node);
    send("power", off ? "OFF" : String(x.p)); send("voltage", off ? "OFF" : "30"); send("current", off ? "OFF" : String(x.p / 30));
    send("windspeedstation", x.ws === null ? "0" : String(x.ws));
    const deg = x.ds === null ? -115 : Math.atan2(x.ds, x.dc) * 180 / Math.PI;
    send("winddirdeg", String(deg)); send("humidity", String(x.rh ?? 70)); send("temperature", String(x.tc ?? 24)); send("ML_Status", "Normal");
  }
  fake = (x.m + 1) * 60000 + 500;
  const r = fn({ topic: "wec/tick" }, ctx, flowCtx, node);
  if (r && r[0]) { const p = r[0].find((o) => o.topic === "prediction_1h"); const ml = r[0].find((o) => o.topic === "wec_ml"); if (p) preds.push(p.payload.power_w); last = ml && ml.payload; n++; }
}
const replay = fn({ payload: "connect" }, ctx, flowCtx, node);
Date.now = realNow;
console.log("tick:", n, "| prediksi dibuat:", preds.length, "| contoh:", preds.slice(-5));
console.log("wec_ml terakhir:", JSON.stringify({ status: last.status, battery: last.battery, eval: last.eval, warm: last.warmup }));
console.log("replay saat connect:", replay[0].topic, replay[0].payload.map((o) => o.topic));
// simpan pesan contoh untuk pratinjau template (dashboard/wec/test/preview.html)
const sampleLive = { topic: "wec_live", payload: { t: Date.now(), p: 42.5, on: 1, ws: 3.4, wd: 120, v: 48.2, i: 0.88, ml: "Optimal" } };
fs.writeFileSync(path.join(here, "test", "ref", "sample_msgs.json"), JSON.stringify([...replay[0].payload, sampleLive]));
