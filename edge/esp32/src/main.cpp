// Edge node Wind Edge Chip: ESP32 membaca sensor turbin, menyusun 16 fitur INT8, meminta prediksi ke FPGA
// (cadangan: MLP yang sama di ESP32), menentukan status turbin dan relai baterai/PLN, lalu kirim lewat MQTT.
//
// Tiap SAMPLE_MS : baca PZEM + stasiun + anemometer -> <TOPIC_DATA>/<besaran> (format Raspi)
// Tiap menit     : agregat 1 menit -> fitur 1 (status), 2 (prediksi 1 jam), 3 (baterai + relai)
//                  -> <TOPIC_WEC>/menit|prediksi|status|baterai (JSON; antre di flash kalau MQTT putus)
#include <Arduino.h>
#include <ArduinoJson.h>
#include <time.h>

#include "config.h"
#include "fpga_link.h"
#include "net.h"
#include "sensors.h"
#include "wec_core.h"

using namespace wec;

static History hist;
static MinuteAcc acc;
static OmForecast om;
static PowerEst pEst;          // daya wajar per menit (pengganti daya saat PZEM diam)
static int64_t accMinute = -1;
static double soc = 0.5;
static Relay relay = {false, false};
static const char *lastStatus = "Menunggu data";
static uint32_t lastSample = 0;

// riwayat kecil untuk status (30 menit) dan evaluasi live (prediksi 60 menit lalu vs aktual)
struct PcPoint { int64_t m = -1; double a = NAN, e = NAN; };
struct FcPoint { int64_t m = -1; double p = NAN, pers = NAN; };
static PcPoint pcRing[30];
static FcPoint fcRing[61];
static float errM[1440], errP[1440];
static int64_t errIdx[1440];

static double r2(double x, int d = 2) { double k = pow(10, d); return round(x * k) / k; }
static void put(JsonVariant v, double x, int d = 2) { if (isNum(x)) v.set(r2(x, d)); else v.set(nullptr); }

static void setRelay(int pin, bool on) {
  if (pin >= 0) digitalWrite(pin, (on == (bool)RELAY_ACTIVE_HIGH) ? HIGH : LOW);
}

static void sendJson(const char *name, JsonDocument &doc, bool retain) {
  char topic[64], buf[1024];
  snprintf(topic, sizeof topic, "%s/%s", TOPIC_WEC, name);
  serializeJson(doc, buf, sizeof buf);
  publish(topic, buf, retain, true);
}

static void publishRaw(const Reading &r) {
  char topic[64], val[24];
  auto pub = [&](const char *key, double x, int d) {
    if (!isNum(x)) return;
    snprintf(topic, sizeof topic, "%s/%s", TOPIC_DATA, key);
    snprintf(val, sizeof val, "%.*f", d, x);
    publish(topic, val);
  };
  if (r.pzemOk) { pub("voltage", r.raw.voltage, 2); pub("current", r.raw.current, 2); pub("power", r.raw.power, 1); pub("energy", r.energyWh, 0); }
  pub("Windspeed", r.windArduino, 2);
  if (r.stationOk) {
    pub("windspeedstation", r.raw.ws, 2); pub("winddirdeg", r.raw.wd, 2); pub("humidity", r.raw.rh, 2);
    pub("temperature", r.raw.tc, 2); pub("noise", r.noise, 2); pub("rainfall", r.rain, 2);
  }
  snprintf(topic, sizeof topic, "%s/ML_Status", TOPIC_DATA);   // penanda akhir batch (sama dengan Raspi)
  publish(topic, lastStatus);
}

// Satu langkah per menit untuk menit m yang baru selesai (padanan tick di dashboard/wec/engine_node.js).
static void minuteStep(int64_t m) {
  const Minute *agg = nullptr;
  if (acc.n) { hist.put(m, acc.aggregate()); agg = hist.get(m); }
  acc.clear();
  const int64_t ts = m * 60, genAt = (m + 1) * 60;

  BatStep bat = batteryStep(soc, agg ? agg->p : 0, ts);
  soc = bat.soc;
  // f0: hanya daya terukur (status, persistence). f: daya kosong diganti daya wajar (prediksi), sama dengan Node-RED.
  // Kalau syarat menit ketat gagal (data berlubang), hitung ulang dengan syarat longgar, sama dengan Node-RED.
  const OmForecast *omp = om.n ? &om : nullptr;
  bool celah = false;
  Features f0 = features(hist, m, omp);
  int8_t xp[16];
  if (!quantize(MODEL_POWERCURVE, f0.pc, xp)) {
    Features g = features(hist, m, omp, nullptr, true);
    if (quantize(MODEL_POWERCURVE, g.pc, xp)) { f0 = g; celah = true; }
  }

  // fitur 1: daya wajar dari kurva daya (dihitung dulu karena dipakai sebagai pengganti daya)
  double expected = NAN;
  if (quantize(MODEL_POWERCURVE, f0.pc, xp)) {
    FpgaResult pr = fpgaInfer(MODEL_POWERCURVE, xp);
    expected = (pr.ok ? pr.out : forward(MODEL_POWERCURVE, xp)) * wattPerLsb(MODEL_POWERCURVE);
    pEst.put(m, expected);
  }
  Features f = features(hist, m, omp, &pEst);
  int8_t xtmp[16];
  if (!quantize(MODEL_FORECAST, f.fc, xtmp)) {
    Features g = features(hist, m, omp, &pEst, true);
    if (quantize(MODEL_FORECAST, g.fc, xtmp)) { f = g; celah = true; }
  }
  // mode offline: prakiraan Open-Meteo kosong (> 3 hari tanpa internet) -> model offline di CPU, masukan ke-16 = 0
  bool offline = false;
  if (!quantize(MODEL_FORECAST, f.fc, xtmp) && !isNum(f.fc[15])) {
    for (int L = 0; L < 2 && !offline; L++) {
      Features g = L ? features(hist, m, omp, &pEst, true) : f;
      g.fc[15] = 0;
      if (quantize(MODEL_OFFLINE, g.fc, xtmp)) { f = g; offline = true; celah = celah || L; }
    }
  }
  const char *mode = f.pEstimated == 0 ? "normal" : f.pEstimated >= 55 ? "cadangan" : "campuran";

  // fitur 2: prediksi rata-rata daya 60 menit ke depan, FPGA dulu lalu cadangan CPU
  int8_t xq[16];
  bool fcOk = quantize(offline ? MODEL_OFFLINE : MODEL_FORECAST, f.fc, xq);
  FpgaResult fr;
  int8_t outQ = 0;
  if (fcOk && offline) {
    uint32_t t0 = micros();
    outQ = forward(MODEL_OFFLINE, xq);   // FPGA berisi bobot MODEL_FORECAST, jadi mode offline dihitung di CPU
    fr.us = micros() - t0;
  } else if (fcOk) {
    fr = fpgaInfer(MODEL_FORECAST, xq);
    uint32_t t0 = micros();
    int8_t cpu = forward(MODEL_FORECAST, xq);
    uint32_t cpuUs = micros() - t0;
    if (fr.ok && fr.out != cpu) fpgaStats().mismatch++;
    outQ = fr.ok ? fr.out : cpu;
    if (!fr.ok) fr.us = cpuUs;
  }
  double watt = fcOk ? outQ * wattPerLsb(MODEL_FORECAST) : NAN;

  // status: rasio aktual/wajar 30 menit (hanya daya terukur)
  if (isNum(expected) && isNum(f0.pMean10)) pcRing[m % 30] = {m, f0.pMean10, expected};
  double a30[30], e30[30];
  for (int k = 0; k < 30; k++) {
    const PcPoint &x = pcRing[(m - 29 + k) % 30];
    bool ok = x.m == m - 29 + k;
    a30[k] = ok ? x.a : NAN; e30[k] = ok ? x.e : NAN;
  }
  double ratio, expMean;
  Status st = status(a30, e30, &ratio, &expMean);
  lastStatus = statusLabel(st);
  int diam = 0;
  for (int64_t k = m - 9; k <= m; k++) { const Minute *x = hist.get(k); if (x && !isNum(x->p) && isNum(x->ws)) diam++; }
  if (st == ST_MENUNGGU && diam >= 5) lastStatus = "PZEM tidak merespons";

  // evaluasi live
  if (fcOk) fcRing[m % 61] = {m, watt, f0.fc[0]};
  const FcPoint &past = fcRing[(m - 60) % 61];
  if (past.m == m - 60) {
    double s = 0; int n = 0;
    for (int64_t k = m - 59; k <= m; k++) { double p = hist.val(k, K_P); if (isNum(p)) { s += p; n++; } }
    if (n >= 50) { int k = m % 1440; errIdx[k] = m; errM[k] = fabs(past.p - s / n); errP[k] = isNum(past.pers) ? fabs(past.pers - s / n) : NAN; }
  }
  double sM = 0, sP = 0; int nE = 0, nP = 0;
  for (int k = 0; k < 1440; k++) if (errIdx[k] > m - 1440 && errIdx[k] <= m) { sM += errM[k]; nE++; if (isNum(errP[k])) { sP += errP[k]; nP++; } }

  // fitur 3: baterai + relai
  SocFc sf = fcOk ? socForecast(soc, watt, genAt) : SocFc{soc, 0, false};
  relay = decide(relay, soc, sf, agg ? agg->p : NAN);
  setRelay(RELAY_PLN, relay.pln);
  setRelay(RELAY_DUMP, relay.dump);

  // ---------- kirim ----------
  const double tMs = (double)genAt * 1000;
  JsonDocument d;
  d["t"] = tMs; d["sumber"] = "esp32";
  if (agg) {
    d["n"] = agg->n; put(d["p"], agg->p); put(d["on"], agg->on); put(d["v"], agg->v); put(d["i"], agg->i, 3);
    put(d["ws"], agg->ws); put(d["ws_max"], agg->wsMax); put(d["ds"], agg->ds, 4); put(d["dc"], agg->dc, 4);
    put(d["rh"], agg->rh); put(d["tc"], agg->tc);
  } else d["n"] = 0;
  sendJson("menit", d, false);

  d.clear();
  d["t"] = tMs;
  if (fcOk) {
    double p10, p90; interval(watt, &p10, &p90);
    put(d["power_w"], watt); put(d["p10"], p10); put(d["p90"], p90); d["out_q"] = outQ;
    put(d["persistence_w"], f0.fc[0]); put(d["om_wind_next"], f.fc[15]);
    d["mode"] = mode; d["menit_estimasi"] = f.pEstimated; d["celah"] = celah; d["offline"] = offline;
  } else d["power_w"] = nullptr;
  JsonObject fp = d["fpga"].to<JsonObject>();
  fp["ok"] = fr.ok; fp["cycles"] = fr.cycles; fp["us"] = fr.us;
  fp["n_ok"] = fpgaStats().ok; fp["n_timeout"] = fpgaStats().timeout; fp["n_beda"] = fpgaStats().mismatch;
  JsonObject ev = d["eval"].to<JsonObject>();
  ev["n"] = nE; put(ev["mae_w"], nE ? sM / nE : NAN); put(ev["mae_persistence_w"], nP ? sP / nP : NAN);
  d["menit_data_60"] = hist.count(m - 59, m);
  d["sumber"] = "esp32";
  sendJson("prediksi", d, true);

  d.clear();
  d["t"] = tMs; d["label"] = lastStatus; put(d["ratio"], ratio); put(d["expected_w"], expMean);
  double am = 0; int an = 0; for (double x : a30) if (isNum(x)) { am += x; an++; }
  put(d["actual_w"], an >= 10 ? am / an : NAN);
  d["sumber"] = "esp32";
  sendJson("status", d, true);

  d.clear();
  d["t"] = tMs; put(d["soc"], soc * 100, 1);
  if (fcOk) { put(d["soc_1h"], sf.soc * 100, 1); put(d["energy_1h_wh"], sf.energyWh, 1); d["pln_soon"] = sf.gridSoon; }
  put(d["load_w"], bat.load); put(d["grid_w"], bat.grid * 60, 1);
  d["relay_pln"] = relay.pln; d["relay_dump"] = relay.dump;
  d["antre_bytes"] = queueBytes(); d["sumber"] = "esp32";
  sendJson("baterai", d, true);

  Serial.printf("[%lld] n=%d P1j=%s W status=%s soc=%.1f%% fpga=%s (%u us)\n", (long long)m, agg ? agg->n : 0,
                fcOk ? String(watt, 1).c_str() : "-", lastStatus, soc * 100, fr.ok ? "ok" : "cpu", fr.us);
}

void setup() {
  Serial.begin(115200);
  if (LED_PIN >= 0) pinMode(LED_PIN, OUTPUT);
  for (int pin : {RELAY_PLN, RELAY_DUMP}) if (pin >= 0) { pinMode(pin, OUTPUT); setRelay(pin, false); }
  for (int k = 0; k < 1440; k++) errIdx[k] = -1;
  sensorsBegin();
  fpgaBegin();
  netBegin();
  Serial.println("Wind Edge Chip edge node siap");
}

void loop() {
  netLoop();
  omRefresh(om);
  if (millis() - lastSample < SAMPLE_MS) return;
  lastSample = millis();
  if (LED_PIN >= 0) digitalWrite(LED_PIN, HIGH);

  Reading r = sensorsRead();
  if (timeValid()) {
    int64_t m = (int64_t)time(nullptr) / 60;
    if (accMinute >= 0 && m > accMinute) minuteStep(accMinute);   // menit sebelumnya selesai
    accMinute = m;
    if (r.pzemOk || r.stationOk) acc.add(cleanSample(r.raw));
  }
  publishRaw(r);
  if (LED_PIN >= 0) digitalWrite(LED_PIN, LOW);
}
