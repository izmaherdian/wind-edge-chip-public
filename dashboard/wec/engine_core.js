// Mesin WEC: inti perhitungan (tanpa API Node-RED) supaya bisa diuji dengan Node.js.
// Logika sama dengan Python:
//   ml/common/preprocess.py (pembersihan + agregasi 1 menit)
//   ml/forecast/features.py (16 fitur prediksi), ml/status/train_powercurve_mlp.py (16 fitur kurva daya)
//   ml/golden_model.py (MLP INT8 identik RTL), ml/battery/sim_battery.py (baterai)
// Dipakai oleh build_flow.py: file ini disisipkan ke function node "Mesin WEC".

function createEngine(B) {
  const MIN = 60000;
  const WIB = 7 * 3600 * 1000;
  const R_LOAD = 35, P_MAX = 1000, WIND_MAX = 8;

  // ---------- util ----------
  const isNum = (x) => typeof x === "number" && isFinite(x);
  const mean = (a, minN) => { const v = a.filter(isNum); return v.length >= minN && v.length ? v.reduce((s, x) => s + x, 0) / v.length : NaN; };
  const median = (a) => { const v = a.filter(isNum).sort((x, y) => x - y); if (!v.length) return NaN; const k = v.length >> 1; return v.length % 2 ? v[k] : (v[k - 1] + v[k]) / 2; };
  const std = (a, minN) => { const v = a.filter(isNum); if (v.length < minN || v.length < 2) return NaN; const m = v.reduce((s, x) => s + x, 0) / v.length; return Math.sqrt(v.reduce((s, x) => s + (x - m) ** 2, 0) / (v.length - 1)); };
  const maxOf = (a, minN) => { const v = a.filter(isNum); return v.length >= minN && v.length ? Math.max(...v) : NaN; };
  // np.round: pembulatan setengah ke genap
  const roundHalfEven = (x) => { const f = Math.floor(x), d = x - f; if (d > 0.5) return f + 1; if (d < 0.5) return f; return f % 2 === 0 ? f : f + 1; };
  const num = (x) => { if (x === null || x === undefined || x === "" || x === "OFF") return NaN; const v = Number(x); return isFinite(v) && v <= 45000 ? v : NaN; };

  // ---------- MLP INT8 (sama dengan golden_model.py dan RTL) ----------
  function forward(model, xq) {
    let h = xq;
    const hidden = [];
    for (let k = 0; k < model.weights.length; k++) {
      const W = model.weights[k], b = model.bias[k], out = new Array(b.length);
      for (let j = 0; j < b.length; j++) {
        let acc = b[j];
        for (let i = 0; i < h.length; i++) acc += h[i] * W[i][j];
        const s = Math.floor((acc * 32) / 256);           // (acc*32) >> 8, sama dengan RTL
        out[j] = s < 0 ? 0 : s > 127 ? 127 : s;
      }
      hidden.push(out);
      h = out;
    }
    return { out: h[0], h1: hidden[0], h2: hidden[1] };
  }
  function quantize(model, feats) {
    return model.fitur.map((n) => {
      const s = model.skala_fitur[n];
      const q = roundHalfEven((feats[n] - s.center) / s.scale);
      return q < -128 ? -128 : q > 127 ? 127 : q;
    });
  }
  function predict(model, feats) {
    for (const n of model.fitur) if (!isNum(feats[n])) return null;
    const xq = quantize(model, feats);
    const r = forward(model, xq);
    return { xq, out_q: r.out, watt: r.out * model.skala_keluaran_W_per_lsb };
  }

  // ---------- pembersihan sampel (preprocess.py) ----------
  function cleanSample(raw) {
    const off = raw.power === "OFF";
    const v = num(raw.voltage), i = num(raw.current);
    let p = num(raw.power);
    if (!isNum(p) && !off && isNum(v) && isNum(i)) p = v * i;
    if (isNum(p) && (p > P_MAX || (isNum(v) && p > 1.5 * v * v / R_LOAD + 20))) p = NaN;
    if (off) p = 0;
    let ws = num(raw.windspeedstation); if (isNum(ws) && ws > WIND_MAX) ws = NaN;
    let wd = num(raw.winddirdeg); if (wd === -115) wd = NaN;
    let rh = num(raw.humidity); if (isNum(rh) && (rh < 0 || rh > 100)) rh = NaN;
    let tc = num(raw.temperature); if (isNum(tc) && tc < 5) tc = NaN;
    // on: 1 bila PZEM membaca daya, NaN bila PZEM tidak merespons (tidak tahu turbin hidup/mati)
    return { t: raw.t, p, on: off ? 0 : isNum(p) ? 1 : NaN, v, i, ws, wd, rh, tc, ml: raw.ML_Status };
  }
  function aggregate(samples) {
    const rad = samples.map((s) => (isNum(s.wd) ? (s.wd * Math.PI) / 180 : NaN));
    return {
      n: samples.length,
      p: mean(samples.map((s) => s.p), 1),
      on: mean(samples.map((s) => s.on), 1),
      v: mean(samples.map((s) => s.v), 1),
      i: mean(samples.map((s) => s.i), 1),
      ws: median(samples.map((s) => s.ws)),
      wsMax: maxOf(samples.map((s) => s.ws), 1),
      ds: mean(rad.map((r) => (isNum(r) ? Math.sin(r) : NaN)), 1),
      dc: mean(rad.map((r) => (isNum(r) ? Math.cos(r) : NaN)), 1),
      rh: mean(samples.map((s) => s.rh), 1),
      tc: mean(samples.map((s) => s.tc), 1),
    };
  }

  // ---------- Open-Meteo per jam -> per menit ----------
  function omAt(om, t) {
    if (!om || !om.time || !om.time.length) return { w: NaN, p: NaN };
    const T = om.time;
    if (t <= T[0] || t >= T[T.length - 1]) return { w: NaN, p: NaN };
    let k = 0; while (T[k + 1] < t) k++;
    const f = (t - T[k]) / (T[k + 1] - T[k]);
    const lerp = (a) => a[k] + f * (a[k + 1] - a[k]);
    return { w: lerp(om.wind), p: lerp(om.pressure) };
  }

  function airDensity(tc, rh, ph) {
    const tk = tc + 273.15, psat = 6.1078 * Math.pow(10, (7.5 * tc) / (tc + 237.3)), pv = (rh / 100) * psat;
    return ((ph - pv) * 100) / (287.05 * tk) + (pv * 100) / (461.5 * tk);
  }

  // ---------- fitur dari riwayat per menit ----------
  // hist: Map(menitIndex -> agregat); m: menit index (floor(t/60000)) yang baru selesai
  // est (opsional): Map(menitIndex -> daya wajar dari MLP kurva daya). Dipakai sebagai pengganti daya menit yang
  // kosong (PZEM tidak merespons); uji 1-20 Okt: MAE 5,42 W vs 5,41 W dengan daya asli (ml/forecast/eval_tanpa_pzem.py).
  // opt.longgar: syarat jumlah menit diturunkan ke separuh jendela dan lag dicari sampai ±5 menit
  // (dipakai mesin hanya bila syarat ketat gagal, mis. Raspi sering reboot karena internet mati)
  // opt.pulih: cadangan setelah Raspi mati lama: syarat cukup seperempat jendela dan lag yang tetap kosong diisi
  // nilai tertua yang ada sesudahnya di jendela (tetap tanpa data masa depan); diuji test/test_pemulihan.js
  function features(hist, m, om, est, opt) {
    const P = !!(opt && opt.pulih);
    const L = P || !!(opt && opt.longgar);
    const qP = P ? (opt.pulih === true ? 0.25 : opt.pulih) : 0;    // porsi jendela minimal pada mode pulih
    const need = (n, ketat) => (P ? Math.max(1, Math.ceil(n * qP)) : L ? Math.ceil(n / 2) : ketat);
    const raw = (k, key) => { const a = hist.get(k); return a ? a[key] : NaN; };
    const get = (k, key) => {
      const x = raw(k, key);
      if (key !== "p" || isNum(x) || !est) return x;
      const e = est.get(k); return isNum(e) ? e : NaN;
    };
    const win = (key, n) => { const r = []; for (let k = m - n + 1; k <= m; k++) r.push(get(k, key)); return r; };
    const offs = L ? [1, -1, 2, -2, 3, -3, 4, -4, 5, -5] : [1, -1, 2, -2];
    // menit pengganti tidak boleh sesudah m (tidak ada data masa depan saat live)
    const lag = (key, d) => {
      let x = get(m - d, key); if (isNum(x)) return x;
      for (const e of offs) { if (e > d) continue; x = get(m - d + e, key); if (isNum(x)) return x; }
      if (P) for (let k = m - d + 1; k <= m; k++) { x = get(k, key); if (isNum(x)) return x; }
      return NaN;
    };
    const t = m * MIN;
    const wib = new Date(t + WIB);
    const hour = wib.getUTCHours() + wib.getUTCMinutes() / 60;
    const ws = win("ws", 60), ps = win("p", 60);
    const w10 = ws.slice(-10), w30 = ws.slice(-30);
    const s10 = mean(win("ds", 10), need(10, 5)), c10 = mean(win("dc", 10), need(10, 5));
    const nrm = Math.hypot(s10, c10);
    const dirS = isNum(nrm) && nrm > 0 ? s10 / nrm : 0, dirC = isNum(nrm) && nrm > 0 ? c10 / nrm : 0;
    // suhu/kelembapan: rata-rata 30 menit, diisi ke depan maks 180 menit, lalu nilai tipikal
    const ffill = (key) => { for (let back = 0; back <= 180; back++) { const r = []; for (let k = m - back - 29; k <= m - back; k++) r.push(get(k, key)); const x = mean(r, 1); if (isNum(x)) return x; } return NaN; };
    let tc = ffill("tc"), rh = ffill("rh");
    const omNow = omAt(om, t);
    let rho = isNum(tc) && isNum(rh) && isNum(omNow.p) ? airDensity(tc, rh, omNow.p) : NaN;
    if (!isNum(rho)) rho = B.typical.rho;
    if (!isNum(tc)) tc = B.typical.temp_c;
    if (!isNum(rh)) rh = B.typical.humidity_pct;
    const omNext = []; for (let k = 0; k <= 60; k++) omNext.push(omAt(om, t + k * MIN).w);
    const fc = {
      p_now: L ? lag("p", 0) : get(m, "p"), p_lag5: lag("p", 5), p_lag15: lag("p", 15), p_lag30: lag("p", 30), p_lag60: lag("p", 60),
      p_mean60: mean(ps, need(60, 50)),
      w_now: L ? lag("ws", 0) : get(m, "ws"), w_mean10: mean(w10, need(10, 8)), w_mean60: mean(ws, need(60, 50)), w3_mean10: mean(w10.map((x) => x ** 3), need(10, 8)),
      dir_sin: dirS, dir_cos: dirC, hour_sin: Math.sin((2 * Math.PI * hour) / 24), hour_cos: Math.cos((2 * Math.PI * hour) / 24),
      rho, om_wind_next: mean(omNext, 61),
    };
    const pc = {
      w_now: fc.w_now, w_mean10: fc.w_mean10, w_mean30: mean(w30, need(30, 24)), w_mean60: mean(ws, need(60, 48)),
      w3_mean10: fc.w3_mean10, w3_mean30: mean(w30.map((x) => x ** 3), need(30, 24)),
      w_max10: maxOf(win("wsMax", 10), need(10, 8)), w_std10: std(w10, need(10, 8)),
      dir_sin: dirS, dir_cos: dirC, hour_sin: fc.hour_sin, hour_cos: fc.hour_cos,
      rho, humidity_pct: rh, temp_c: tc, om_wind_now: omNow.w,
    };
    const pMean10 = mean(ps.slice(-10), need(10, 8));
    let pEstimated = 0;
    if (est) for (let k = m - 60; k <= m; k++) if (!isNum(raw(k, "p")) && isNum(est.get(k))) pEstimated++;
    return { fc, pc, pMean10, hour, pEstimated };
  }

  // Cadangan tanpa riwayat: daya wajar dari kurva daya pada prakiraan angin Open-Meteo 60 menit ke depan.
  // f: hasil features() (arah, jam, rho, suhu, kelembapan tetap dipakai bila ada). Diuji test/test_pemulihan.js.
  function cuaca(f, om, t) {
    const w = []; for (let k = 0; k <= 60; k++) w.push(omAt(om, t + k * MIN).w);
    const v = mean(w, 61);
    if (!isNum(v)) return null;
    const pc = { ...f.pc, w_now: v, w_mean10: v, w_mean30: v, w_mean60: v, w3_mean10: v ** 3, w3_mean30: v ** 3,
                 w_max10: v, w_std10: 0, om_wind_now: omAt(om, t).w };
    for (const k of ["dir_sin", "dir_cos"]) if (!isNum(pc[k])) pc[k] = 0;
    for (const [k, d] of [["rho", B.typical.rho], ["temp_c", B.typical.temp_c], ["humidity_pct", B.typical.humidity_pct]]) if (!isNum(pc[k])) pc[k] = d;
    return predict(B.powercurve, pc);
  }

  // ---------- interval empiris + status ----------
  function interval(watt) {
    for (const b of B.interval.bins) if (watt >= b.dari && watt < b.sampai) return [b.p10, b.p90];
    const b = B.interval.bins[B.interval.bins.length - 1]; return [b.p10, b.p90];
  }
  function status(actual30, expected30) {
    const a = B.powercurve.ambang_status;
    const e = mean(expected30, 10), x = mean(actual30, 10);
    if (!isNum(e) || !isNum(x)) return { label: "Menunggu data", ratio: NaN, expected: e };
    if (e <= a.min_daya_wajar_W) return { label: "Angin lemah", ratio: NaN, expected: e };
    const r = x / e;
    return { label: r < a.bawah ? "Di bawah normal" : r > a.atas ? "Di atas normal" : "Normal", ratio: r, expected: e };
  }

  // ---------- baterai (sim_battery.py) ----------
  const BAT = B.battery;
  const interp = (x, xs, ys) => { if (x <= xs[0]) return ys[0]; for (let k = 1; k < xs.length; k++) if (x <= xs[k]) return ys[k - 1] + ((x - xs[k - 1]) / (xs[k] - xs[k - 1])) * (ys[k] - ys[k - 1]); return ys[ys.length - 1]; };
  const dcForAc = (ac) => interp(ac, BAT.inverter_ac_W, BAT.inverter_dc_W);
  function loadAt(t) { const h = new Date(t + WIB).getUTCHours(); const [a, b] = BAT.jam_malam_WIB; return BAT.beban_dasar_W + (h >= a && h < b ? BAT.beban_malam_W : 0); }
  function batteryStep(soc, pDc, t) {
    const cap = BAT.kapasitas_Wh, need = dcForAc(loadAt(t));
    const e = ((isNum(pDc) ? pDc : 0) * BAT.eta_charge_controller - need) / 60;
    let toBatt = 0, dumped = 0, grid = 0;
    if (e >= 0) { const room = (BAT.soc_max - soc) * cap; const st = Math.min(e * BAT.eta_isi, room); toBatt = st; dumped = e - st / BAT.eta_isi; soc += st / cap; }
    else { const avail = (soc - BAT.soc_min) * cap; const draw = Math.min(-e / BAT.eta_buang, avail); soc -= draw / cap; toBatt = -draw; grid = -e - draw * BAT.eta_buang; }
    return { soc, toBatt, dumped, grid, load: loadAt(t) };
  }
  function socForecast(soc, pHat, t) {
    let load = 0; for (let k = 1; k <= 60; k++) load += loadAt(t + k * MIN); load /= 60;
    const net = pHat * BAT.eta_charge_controller - dcForAc(load);
    const e = net >= 0 ? net * BAT.eta_isi : net / BAT.eta_buang;
    return { soc: Math.min(BAT.soc_max, Math.max(BAT.soc_min, soc + e / BAT.kapasitas_Wh)), energyWh: e, gridSoon: soc + e / BAT.kapasitas_Wh <= BAT.soc_min };
  }

  return { forward, quantize, predict, cleanSample, aggregate, features, cuaca, interval, status, batteryStep, socForecast, omAt, roundHalfEven, MIN, isNum, mean };
}

if (typeof module !== "undefined") module.exports = { createEngine };
