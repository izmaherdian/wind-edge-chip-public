// Uji cadangan setelah Raspi mati lama (22 Okt: mati ±75 menit, prediksi kosong ±60 menit setelah data kembali).
// Simulasi: tiap 3 jam pada 1-20 Okt data hilang 75 menit; untuk menit ke-r setelah data kembali dibandingkan
// mode pemulihan (features pulih), mode cuaca (kurva daya pada prakiraan Open-Meteo), persistence, dan model
// dengan data utuh. Jalankan: node dashboard/wec/test/test_pemulihan.js
const fs = require("fs"), path = require("path");
const here = path.join(__dirname, "..");
const { createEngine } = require(path.join(here, "engine_core.js"));
const E = createEngine(JSON.parse(fs.readFileSync(path.join(here, "model_bundle.json"), "utf8")));
const B = JSON.parse(fs.readFileSync(path.join(here, "model_bundle.json"), "utf8"));
const readJSON = (f) => JSON.parse(fs.readFileSync(f, "utf8").replace(/\bNaN\b/g, "null"));
const nanify = (x) => Object.fromEntries(Object.entries(x).map(([k, v]) => [k, v === null ? NaN : v]));
const mins = readJSON(path.join(here, "test", "ref", "minutes.json")).map(nanify);
const om = readJSON(path.join(here, "test", "ref", "om.json"));
const hist = new Map(mins.map((x) => [x.m, x]));
const MATI = 75, Q = Number(process.env.Q || 0.05);   // 0,05 x 60 = 3 menit: syarat yang dipasang di engine_node.js
const actual60 = (m) => { const v = []; for (let k = m + 1; k <= m + 60; k++) { const x = hist.get(k); if (x && E.isNum(x.p)) v.push(x.p); } return v.length >= 50 ? v.reduce((a, b) => a + b, 0) / v.length : null; };
const start = Math.floor(Date.UTC(2026, 9, 1) / 60000) + 120, stop = Math.floor(Date.UTC(2026, 9, 21) / 60000) - 200;
const kelompok = [[1, 2], [3, 5], [6, 10], [11, 15], [16, 30], [31, 60]];
const hasil = kelompok.map(() => ({ n: 0, pulih: [], cuaca: [], pers: [], utuh: [], celah: 0, adaP: 0, adaC: 0 }));
let fail = 0;
for (let s = start; s < stop; s += 180) {
  const H = { get: (k) => (k >= s && k < s + MATI ? undefined : hist.get(k)) };
  for (let r = 1; r <= 60; r++) {
    const m = s + MATI - 1 + r, y = actual60(m);
    if (y === null) continue;
    const g = kelompok.findIndex(([a, b]) => r >= a && r <= b), h = hasil[g];
    const fl = E.features(H, m, om, null, { longgar: true });
    if (E.predict(B.forecast, fl.fc)) { h.celah++; continue; }          // mode celah sudah cukup: cadangan tidak dipakai
    const fp = E.features(H, m, om, null, { pulih: Q });
    const p = E.predict(B.forecast, fp.fc), c = E.cuaca(fp, om, (m + 1) * E.MIN);
    const full = E.predict(B.forecast, E.features(hist, m, om).fc);
    if (!p || !c || !full || !E.isNum(fp.fc.p_now)) continue;
    h.n++; h.pulih.push(Math.abs(p.watt - y)); h.cuaca.push(Math.abs(c.watt - y)); h.pers.push(Math.abs(fp.fc.p_now - y)); h.utuh.push(Math.abs(full.watt - y));
  }
}
const mae = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN);
console.log("menit setelah pulih | n | pulih | cuaca | persistence | data utuh (acuan) | sudah tertangani mode celah");
const ringkas = {};
hasil.forEach((h, i) => {
  const [a, b] = kelompok[i];
  const row = { n: h.n, pulih: mae(h.pulih), cuaca: mae(h.cuaca), pers: mae(h.pers), utuh: mae(h.utuh), celah: h.celah };
  ringkas[`${a}-${b}`] = row;
  console.log(`${String(a).padStart(2)}-${String(b).padEnd(2)} | ${h.n} | ${row.pulih.toFixed(2)} | ${row.cuaca.toFixed(2)} | ${row.pers.toFixed(2)} | ${row.utuh.toFixed(2)} | ${h.celah}`);
});
const semua = (k) => mae(hasil.flatMap((h) => h[k]));
const check = (name, ok, info) => { console.log(`${ok ? "LULUS" : "GAGAL"}  ${name}  ${info}`); if (!ok) fail++; };
const terisi = hasil.filter((h) => h.n);
check("mode pemulihan lebih baik dari persistence di semua rentang", terisi.every((h) => mae(h.pulih) < mae(h.pers)),
  `MAE pulih ${semua("pulih").toFixed(2)} W · persistence ${semua("pers").toFixed(2)} W · data utuh ${semua("utuh").toFixed(2)} W (${terisi.reduce((a, h) => a + h.n, 0)} menit)`);
check("mode pemulihan mendekati data utuh (selisih < 15%)", semua("pulih") < 1.15 * semua("utuh"), "");
check("mode cuaca tidak dipakai karena tidak lebih baik dari persistence", semua("cuaca") > semua("pers"), `MAE cuaca ${semua("cuaca").toFixed(2)} W`);
// Integrasi: function node Node-RED utuh (engine_node.js) menerima pesan MQTT, Raspi "mati" 75 menit.
{
  const core = fs.readFileSync(path.join(here, "engine_core.js"), "utf8").replace(/if \(typeof module[^\n]*\n/, "");
  const body = core + "\nconst BUNDLE = " + fs.readFileSync(path.join(here, "model_bundle.json"), "utf8") + ";\n" + fs.readFileSync(path.join(here, "engine_node.js"), "utf8");
  const fn = new Function("msg", "context", "flow", "node", body);
  let fake = 0; const asliNow = Date.now; Date.now = () => fake;
  const store = {}, ctx = { get: (k) => store[k], set: (k, v) => { store[k] = v; } }, fl = { get: () => undefined, set: () => {} };
  const call = (msg) => fn(msg, ctx, fl, { status: () => {} });
  const m0 = Math.floor(Date.UTC(2026, 9, 10, 4) / 60000);                 // 10 Okt 11.00 WIB
  fake = (m0 - 150) * 60000;
  call({ topic: "wec/openmeteo", payload: { hourly: { time: om.time.map((t) => new Date(t).toISOString().slice(0, 16)), wind_speed_10m: om.wind, surface_pressure: om.pressure } } });
  const minute = (x, on) => {
    if (on) for (let k = 0; k < 12; k++) {
      fake = x.m * 60000 + k * 5000 + 100;
      const send = (key, val) => call({ topic: "TurbinAngin/" + key, payload: val });
      send("power", E.isNum(x.p) ? String(x.p) : "OFF"); send("voltage", "30"); send("current", E.isNum(x.p) ? String(x.p / 30) : "OFF");
      send("windspeedstation", E.isNum(x.ws) ? String(x.ws) : "0"); send("winddirdeg", String(E.isNum(x.ds) ? Math.atan2(x.ds, x.dc) * 180 / Math.PI : -115));
      send("humidity", String(E.isNum(x.rh) ? x.rh : 70)); send("temperature", String(E.isNum(x.tc) ? x.tc : 24)); send("ML_Status", "Normal");
    }
    fake = (x.m + 1) * 60000 + 500;
    const r = call({ topic: "wec/tick" });
    return r && r[0] && r[0].find((o) => o.topic === "wec_ml");
  };
  let pertama = null, labelPulih = false;
  for (let m = m0 - 150; m < m0 + 20; m++) {
    const x = hist.get(m); if (!x) continue;
    const mati = m >= m0 - MATI && m < m0;
    const o = minute(x, !mati);
    if (m >= m0 && o && o.payload.forecast && pertama === null) { pertama = m - m0 + 1; labelPulih = !!o.payload.forecast.pulih; }
  }
  Date.now = asliNow;
  check("Node-RED: prediksi kembali cepat setelah Raspi mati 75 menit", pertama !== null && pertama <= 5 && labelPulih,
    `prediksi pertama pada menit ke-${pertama} setelah data kembali, label pemulihan: ${labelPulih}`);
}
process.exit(fail ? 1 : 0);
