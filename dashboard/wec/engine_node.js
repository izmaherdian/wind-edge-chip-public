// ===== Pembungkus Node-RED untuk Mesin WEC (disisipkan build_flow.py setelah engine_core.js + BUNDLE) =====
// Masukan:
//   msg.topic "TurbinAngin/<besaran>"  : data live Raspi tiap ±3 detik (ML_Status = akhir satu batch)
//   msg.topic "wec/tick"               : inject tiap menit -> hitung fitur 1, 2, 3 untuk menit yang baru selesai
//   msg.topic "wec/openmeteo"          : respons Open-Meteo (JSON) dari http request
//   msg.payload === "connect" / topic "replay" : browser baru tersambung -> kirim ulang hasil terakhir
//   msg.topic "WEC/state"              : snapshot riwayat (retained) -> dipulihkan sekali setelah deploy/restart
//   msg.topic "WEC/fpga"               : hasil akselerator FPGA dari edge/bridge/fpga_bridge.py (byte xq dari WEC/prediksi)
// Keluaran 1 -> ui-template dashboard: prediction_1h (format panel Genis), wec_ml, wec_live, wec_model, wec_fpga
// Keluaran 2 -> MQTT: WEC/prediksi, WEC/status, WEC/baterai (retain), WEC/state (retain, tiap 5 menit)
const E = createEngine(BUNDLE);
// Status disimpan di flow context (bertahan saat node ini di-deploy ulang) dan di MQTT WEC/state (bertahan saat server restart)
const st = context.get("st") || flow.get("wec_st") || { cur: {}, samples: [], hist: new Map(), pcHist: new Map(), fcHist: new Map(), evals: [], soc: BUNDLE.battery.soc_awal, om: null, last: null };
if (!st.pEst) st.pEst = new Map();       // daya wajar per menit dari MLP kurva daya (pengganti saat PZEM diam)
context.set("st", st);
flow.set("wec_st", st);
const MIN = E.MIN;
const nowMs = Date.now();
const r2 = (x, d = 2) => (E.isNum(x) ? Number(x.toFixed(d)) : null);

function modelMsg() {
  const pick = (m) => ({ fitur: m.fitur, skala_fitur: m.skala_fitur, skala_keluaran_W_per_lsb: m.skala_keluaran_W_per_lsb, weights: m.weights, bias: m.bias });
  return { topic: "wec_model", payload: { forecast: pick(BUNDLE.forecast), interval: BUNDLE.interval, kurva_daya: BUNDLE.kurva_daya } };
}

// --- browser baru tersambung ---
if (msg.payload === "connect" || msg.topic === "replay" || msg.topic === "wec/replay") {
  const out = [modelMsg()];
  if (st.last) out.push(...st.last);
  if (st.fpga) out.push({ topic: "wec_fpga", payload: st.fpga });
  // satu pesan (template membongkarnya berurutan); kalau diminta template, hanya ke browser itu
  return [{ topic: "wec_replay", payload: out, ...(msg._client ? { _client: msg._client } : {}) }, null];
}

// --- hasil chip FPGA (jembatan laptop/ESP32) ---
if (msg.topic === "WEC/fpga") {
  let d; try { d = typeof msg.payload === "string" ? JSON.parse(msg.payload) : msg.payload; } catch (e) { return null; }
  if (!d || typeof d.out_q_fpga !== "number") return null;
  st.fpga = { ...d, diterima: nowMs };
  return [{ topic: "wec_fpga", payload: st.fpga }, null];
}

// --- pulihkan riwayat dari snapshot retained: hanya menit yang belum ada yang ditambahkan ---
if (msg.topic === "WEC/state") {
  const first = !st.restored;
  st.restored = true;
  let d; try { d = typeof msg.payload === "string" ? JSON.parse(msg.payload) : msg.payload; } catch (e) { return null; }
  if (!d || d.v !== 1) return null;
  const num = (x) => (x === null || x === undefined ? NaN : x);
  const K = ["n", "p", "on", "v", "i", "ws", "wsMax", "ds", "dc", "rh", "tc"];
  for (const r of d.hist || []) if (!st.hist.has(r[0]) || (st.sheetHistoryMinutes && st.sheetHistoryMinutes.has(r[0]))) { if (st.sheetHistoryMinutes) st.sheetHistoryMinutes.delete(r[0]); const a = {}; K.forEach((k, j) => (a[k] = num(r[j + 1]))); st.hist.set(r[0], a); }
  for (const [k, v] of d.pEst || []) if (!st.pEst.has(k)) st.pEst.set(k, v);
  for (const [k, a, e] of d.pcHist || []) if (!st.pcHist.has(k)) st.pcHist.set(k, { a, e });
  for (const [k, p, pers] of d.fcHist || []) if (!st.fcHist.has(k)) st.fcHist.set(k, { p, pers: num(pers) });
  if (!st.evals.length && d.evals) st.evals = d.evals.map(([m, err, errP]) => ({ m, err, errP }));
  if (first && typeof d.soc === "number") st.soc = d.soc;
  if (d.hist && d.hist.length && !st.lastData) st.lastData = (d.hist[d.hist.length - 1][0] + 1) * MIN;
  if (first) node.status({ fill: "blue", shape: "ring", text: `riwayat dipulihkan: ${(d.hist || []).length} menit` });
  return null;
}

// Merge measured history only. Do not emit predictions, update SoC/evaluations,
// mark historical measurements as live, or overwrite existing MQTT/snapshot data.
if (msg.topic === 'wec/history') {
  const d = msg.payload;
  if (!d || d.source !== 'google-sheet' || !Array.isArray(d.rows) || d.rows.length > 15000) return null;
  const grouped = new Map(), lastClosed = Math.floor(nowMs / MIN) - 1;
  if (!st.sheetHistoryMinutes) st.sheetHistoryMinutes = new Set();
  for (const minute of st.sheetHistoryMinutes) if (minute < lastClosed - 180 || !st.hist.has(minute)) st.sheetHistoryMinutes.delete(minute);
  for (const r of d.rows) {
    const t = r && r.serverTime;
    if (typeof t !== 'number' || !Number.isFinite(t) || t < nowMs - 3 * 3600000 || t > nowMs) continue;
    const minute = Math.floor(t / MIN);
    if (minute > lastClosed || st.hist.has(minute)) continue;
    if (!grouped.has(minute)) grouped.set(minute, []);
    grouped.get(minute).push(E.cleanSample({ ...r, t }));
  }
  for (const [minute, samples] of grouped) { st.hist.set(minute, E.aggregate(samples)); st.sheetHistoryMinutes.add(minute); }
  st.historyRecovery = { source: 'Google Sheets', imported_minutes: grouped.size, loaded_at: nowMs };
  node.status({ fill: 'blue', shape: 'ring', text: `riwayat Sheet: +${grouped.size} menit; live tetap MQTT` });
  return null;
}

// --- Open-Meteo per jam ---
if (msg.topic === "wec/openmeteo") {
  const h = msg.payload && msg.payload.hourly;
  if (h && Array.isArray(h.time)) {
    st.om = { time: h.time.map((s) => Date.parse(s + "Z")), wind: h.wind_speed_10m, pressure: h.surface_pressure, fetched: nowMs };
    node.status({ fill: "green", shape: "dot", text: "Open-Meteo " + new Date(nowMs).toISOString().slice(11, 16) + " UTC" });
  }
  return null;
}

// --- sampel live dari Raspi ---
if (typeof msg.topic === "string" && msg.topic.startsWith("TurbinAngin/")) {
  const key = msg.topic.split("/").pop();
  // batch baru dimulai tanpa ML_Status di batch sebelumnya (PZEM tidak merespons): kirim angin/arah saja
  // ke panel live; tidak masuk st.samples, jadi model tetap hanya memakai batch lengkap
  if (key === "Windspeed" && "windspeedstation" in st.cur && !("ML_Status" in st.cur)) {
    const s = E.cleanSample({ ...st.cur, t: nowMs });
    st.samples.push(s);                   // angin/arah/suhu tetap dipakai (fitur kurva daya + estimasi daya)
    if (st.samples.length > 400) st.samples.splice(0, st.samples.length - 400);
    st.cur = {};
    st.cur[key] = typeof msg.payload === "string" ? msg.payload.trim() : msg.payload;
    return [{ topic: "wec_live", payload: { t: nowMs, p: null, on: null, ws: r2(s.ws), wd: r2(s.wd, 0), v: null, i: null, ml: null, pzem: false } }, null];
  }
  st.cur[key] = typeof msg.payload === "string" ? msg.payload.trim() : msg.payload;
  if (key !== "ML_Status") return null;
  const s = E.cleanSample({ ...st.cur, t: nowMs });
  st.samples.push(s);
  if (st.samples.length > 400) st.samples.splice(0, st.samples.length - 400);
  st.cur = {};
  return [{ topic: "wec_live", payload: { t: nowMs, p: r2(s.p, 1), on: s.on, ws: r2(s.ws), wd: r2(s.wd, 0), v: r2(s.v), i: r2(s.i, 3), ml: s.ml } }, null];
}

if (msg.topic !== "wec/tick") return null;
for (const x of st.samples) if (!st.lastData || x.t > st.lastData) st.lastData = x.t;

// --- tiap menit: agregasi menit yang baru selesai ---
const m = Math.floor(nowMs / MIN) - 1;
const inMin = st.samples.filter((s) => Math.floor(s.t / MIN) === m);
st.samples = st.samples.filter((s) => Math.floor(s.t / MIN) > m);
if (inMin.length) { st.hist.set(m, E.aggregate(inMin)); if (st.sheetHistoryMinutes) st.sheetHistoryMinutes.delete(m); }
for (const store of [st.hist, st.pcHist, st.fcHist, st.pEst]) for (const k of store.keys()) if (k < m - 1500) store.delete(k);

// baterai (fitur 3, simulasi): melangkah tiap menit; menit tanpa data dianggap 0 W
const agg = st.hist.get(m);
const bat = E.batteryStep(st.soc, agg ? agg.p : 0, m * MIN);
st.soc = bat.soc;

// f0: hanya daya terukur (status, persistence). f: daya kosong diganti daya wajar dari kurva daya (prediksi).
// Kalau syarat menit ketat gagal (data berlubang, mis. Raspi reboot), hitung ulang dengan syarat longgar (separuh jendela).
let celah = false;
let f0 = E.features(st.hist, m, st.om);
let pc = E.predict(BUNDLE.powercurve, f0.pc);
if (!pc) { const g = E.features(st.hist, m, st.om, null, { longgar: true }); pc = E.predict(BUNDLE.powercurve, g.pc); if (pc) { f0 = g; celah = true; } }
// Angin di bawah ambang putar: PZEM-017 mati saat keluaran turbin < 7 V (maks 7^2/35 = 1,4 W), jadi daya kosong = 0 W,
// sama dengan aturan data latih (OFF = 0 W). Ambang 1,4 m/s: di bawahnya PZEM kosong > 50% menit (data Mar-Okt).
const CUT_IN = 1.4;
const xm = st.hist.get(m);
if (xm && !E.isNum(xm.p) && E.isNum(xm.ws) && xm.ws < CUT_IN) st.pEst.set(m, 0);
else if (pc) st.pEst.set(m, pc.watt);
let f = E.features(st.hist, m, st.om, st.pEst);
let fc = E.predict(BUNDLE.forecast, f.fc);
if (!fc) { const g = E.features(st.hist, m, st.om, st.pEst, { longgar: true }); fc = E.predict(BUNDLE.forecast, g.fc); if (fc) { f = g; celah = true; } }
// Mode offline: prakiraan Open-Meteo kosong (internet putus > 3 hari) -> model INT8 offline (masukan ke-16 = 0).
// Uji 1-20 Okt: MAE 5,62 W vs 5,48 W dengan Open-Meteo (ml/forecast/train_mlp_offline.py).
let offline = false;
if (!fc && BUNDLE.forecast_offline && !E.isNum(f.fc.om_wind_next)) {
  for (const L of [false, true]) {
    const g = L ? E.features(st.hist, m, st.om, st.pEst, { longgar: true }) : f;
    const o = E.predict(BUNDLE.forecast_offline, { ...g.fc, om_wind_next: 0 });
    if (o) { fc = o; f = { ...g, fc: { ...g.fc, om_wind_next: 0 } }; offline = true; celah = celah || L; break; }
  }
}
// Mode pemulihan: Raspi baru kembali setelah mati lama (> 30 menit data hilang), cukup 3 menit data.
// Uji 1-20 Okt, Raspi mati 75 menit: MAE 6,04 W vs persistence 8,73 W, data utuh 5,99 W (test/test_pemulihan.js).
let pulih = false;
if (!fc) {
  const g = E.features(st.hist, m, st.om, st.pEst, { pulih: 0.05 });
  let o = E.predict(BUNDLE.forecast, g.fc), gg = g;
  if (!o && BUNDLE.forecast_offline && !E.isNum(g.fc.om_wind_next)) { gg = { ...g, fc: { ...g.fc, om_wind_next: 0 } }; o = E.predict(BUNDLE.forecast_offline, gg.fc); offline = !!o; }
  if (o) { fc = o; f = gg; pulih = true; celah = true; }
}
let menitCutIn = 0; for (let k = m - 60; k <= m; k++) { const x = st.hist.get(k); if (x && !E.isNum(x.p) && E.isNum(x.ws) && x.ws < CUT_IN) menitCutIn++; }
const mode = !fc ? null : f.pEstimated === 0 ? "normal" : f.pEstimated >= 55 ? "cadangan" : "campuran";
if (pc && E.isNum(f0.pMean10)) st.pcHist.set(m, { a: f0.pMean10, e: pc.watt });
const a30 = [], e30 = [];
for (let k = m - 29; k <= m; k++) { const x = st.pcHist.get(k); a30.push(x ? x.a : NaN); e30.push(x ? x.e : NaN); }
const status = E.status(a30, e30);
let pzemDiam = 0; for (let k = m - 9; k <= m; k++) { const x = st.hist.get(k); if (x && !E.isNum(x.p) && E.isNum(x.ws)) pzemDiam++; }
if (status.label === "Menunggu data" && pzemDiam >= 5) status.label = "PZEM tidak merespons";
let tanpaAngin = 0; for (let k = m - 9; k <= m; k++) { const x = st.hist.get(k); if (x && !E.isNum(x.ws)) tanpaAngin++; }
if (status.label === "Menunggu data" && tanpaAngin >= 5) status.label = "Stasiun cuaca diam";

// evaluasi live: prediksi yang dibuat 60 menit lalu vs rata-rata aktual 60 menit terakhir
if (fc) st.fcHist.set(m, { p: fc.watt, pers: f0.fc.p_now });
const past = st.fcHist.get(m - 60);
if (past) {
  const act = []; for (let k = m - 59; k <= m; k++) { const x = st.hist.get(k); act.push(x ? x.p : NaN); }
  const y = E.mean(act, 50);
  if (E.isNum(y)) st.evals.push({ m, err: Math.abs(past.p - y), errP: Math.abs(past.pers - y) });
}
st.evals = st.evals.filter((e) => e.m > m - 1440);
const evP = st.evals.filter((e) => E.isNum(e.errP));
const mae = st.evals.length ? st.evals.reduce((s, e) => s + e.err, 0) / st.evals.length : null;
const maeP = evP.length ? evP.reduce((s, e) => s + e.errP, 0) / evP.length : null;

let warm = 0; for (let k = m - 59; k <= m; k++) if (st.hist.has(k)) warm++;
let warm10 = 0; for (let k = m - 9; k <= m; k++) if (st.hist.has(k)) warm10++;
const genAt = (m + 1) * MIN;
const out = [];
let socF = null;
if (fc) {
  const [p10, p90] = E.interval(fc.watt);
  socF = E.socForecast(st.soc, fc.watt, genAt);
  out.push({ topic: "prediction_1h", payload: { power_w: r2(fc.watt), wind_ms: r2(f.fc.om_wind_next), energy_wh: r2(fc.watt),
    model: "MLP INT8 16-32-16-1 (identik FPGA) · Node-RED" + (mode !== "normal" ? " · daya dari angin (PZEM diam)" : "") + (pulih ? " · pemulihan setelah Raspi mati" : celah ? " · data berlubang" : "") + (offline ? " · offline (tanpa Open-Meteo)" : ""), generated_at: genAt, target_at: genAt + 3600000, horizon_minutes: 60 } });
}
const ml = {
  t: genAt, warmup: warm, menit_data_60: warm,
  forecast: fc ? { power_w: r2(fc.watt), p10: r2(E.interval(fc.watt)[0]), p90: r2(E.interval(fc.watt)[1]), out_q: fc.out_q, xq: fc.xq,
                   persistence_w: r2(f0.fc.p_now), om_wind_next: r2(f.fc.om_wind_next),
                   mode, menit_estimasi: f.pEstimated, menit_cut_in: Math.min(menitCutIn, f.pEstimated), celah, offline, pulih, menit_data_60: warm } : null,
  alasan: fc ? null : warm10 === 0 ? (st.lastData ? "tidak ada data turbin masuk sejak " + new Date(st.lastData + 7 * 3600000).toISOString().slice(11, 16) + " WIB (Raspi/internet di lokasi)" : "belum ada data turbin masuk sejak mesin dimulai")
    : !st.om ? "menunggu prakiraan Open-Meteo"
    : "data belum lengkap: " + BUNDLE.forecast.fitur.filter((k) => !E.isNum(f.fc[k])).join(", "),
  features: f.fc,
  status: { label: status.label, ratio: r2(status.ratio), expected_w: r2(status.expected), actual_w: r2(E.mean(a30, 10)),
            ambang: BUNDLE.powercurve.ambang_status },
  battery: { soc: r2(st.soc * 100, 1), soc_1h: socF ? r2(socF.soc * 100, 1) : null, energy_1h_wh: socF ? r2(socF.energyWh, 1) : null,
             pln_soon: socF ? socF.gridSoon : null, load_w: bat.load, grid_w: r2(bat.grid * 60, 1), kapasitas_wh: BUNDLE.battery.kapasitas_Wh },
  eval: { n: st.evals.length, mae_w: r2(mae), mae_persistence_w: r2(maeP) },
  openmeteo: st.om ? { fetched: st.om.fetched } : null,
  live: agg ? { p: r2(agg.p), ws: r2(agg.ws), on: r2(agg.on) } : null,
};
out.push({ topic: "wec_ml", payload: ml });
st.last = out;
node.status({ fill: fc ? (mode === "normal" ? "green" : "blue") : "yellow", shape: "dot",
  text: fc ? `P1j ${ml.forecast.power_w} W (${mode}) · ${status.label}` : `menunggu: ${ml.alasan}` });
const mq = [
  // xq ikut: 16 byte yang sama untuk FPGA. Mode offline: FPGA tetap berisi bobot model utama, jadi out_q (model offline)
  // tidak dikirim; jembatan ESP32 menghitung pembandingnya sendiri dengan bobot yang sama dengan FPGA.
  { topic: "WEC/prediksi", retain: true, payload: JSON.stringify({ t: genAt, ...(ml.forecast || {}), ...(offline ? { out_q: undefined } : {}) }) },
  { topic: "WEC/status", retain: true, payload: JSON.stringify({ t: genAt, ...ml.status }) },
  { topic: "WEC/baterai", retain: true, payload: JSON.stringify({ t: genAt, ...ml.battery }) },
];
// snapshot riwayat 240 menit tiap 5 menit (retained), supaya deploy/restart tidak mengulang pemanasan
if (m % 5 === 0) {
  const rr = (x) => (E.isNum(x) ? Number(x.toFixed(4)) : null);
  const K = ["n", "p", "on", "v", "i", "ws", "wsMax", "ds", "dc", "rh", "tc"];
  const hist = [...st.hist.entries()].filter(([k]) => k > m - 240).map(([k, a]) => [k, ...K.map((x) => rr(a[x]))]);
  mq.push({ topic: "WEC/state", retain: true, payload: JSON.stringify({ v: 1, m, soc: st.soc, hist,
    pEst: [...st.pEst.entries()].filter(([k]) => k > m - 240).map(([k, v]) => [k, rr(v)]),
    pcHist: [...st.pcHist.entries()].filter(([k]) => k > m - 30).map(([k, x]) => [k, rr(x.a), rr(x.e)]),
    fcHist: [...st.fcHist.entries()].filter(([k]) => k > m - 61).map(([k, x]) => [k, rr(x.p), rr(x.pers)]),
    evals: st.evals.map((e) => [e.m, rr(e.err), rr(e.errP)]) }) });
}
return [out, mq];
