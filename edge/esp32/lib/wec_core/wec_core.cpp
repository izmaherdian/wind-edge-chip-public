// Inti mesin WEC. Lihat wec_core.h; padanan baris per baris dengan dashboard/wec/engine_core.js.
#include "wec_core.h"

#include "mlp_int8.h"              // ml/forecast/model/export (bobot fitur 2 + mlp_layer)
#include "mlp_offline_int8.h"       // ml/forecast/model/export (bobot mode offline)
#include "mlp_powercurve_int8.h"   // ml/status/model/export (bobot fitur 1)
#include "wec_bundle.h"            // skala fitur presisi penuh, ambang, baterai

namespace wec {

static const double R_LOAD = 35, P_MAX = 1000, WIND_MAX = 8, SEL_RUSAK = 45000;
static const double PI_D = 3.14159265358979323846;

bool isNum(double x) { return !isnan(x) && !isinf(x); }

// ---------- util (sama dengan mean/median/std/maxOf di engine_core.js) ----------
static double meanOf(const double *a, int n, int minN) {
  double s = 0; int k = 0;
  for (int j = 0; j < n; j++) if (isNum(a[j])) { s += a[j]; k++; }
  return k >= minN && k ? s / k : NAN;
}
static double maxOf(const double *a, int n, int minN) {
  double mx = -INFINITY; int k = 0;
  for (int j = 0; j < n; j++) if (isNum(a[j])) { if (a[j] > mx) mx = a[j]; k++; }
  return k >= minN && k ? mx : NAN;
}
static double stdOf(const double *a, int n, int minN) {
  double m = meanOf(a, n, 1); int k = 0; double s = 0;
  for (int j = 0; j < n; j++) if (isNum(a[j])) { s += (a[j] - m) * (a[j] - m); k++; }
  return k >= minN && k >= 2 ? sqrt(s / (k - 1)) : NAN;
}
static double medianOf(const double *a, int n) {
  double v[MinuteAcc::CAP]; int k = 0;
  for (int j = 0; j < n && k < MinuteAcc::CAP; j++) if (isNum(a[j])) v[k++] = a[j];
  if (!k) return NAN;
  for (int x = 1; x < k; x++) { double t = v[x]; int y = x - 1; while (y >= 0 && v[y] > t) { v[y + 1] = v[y]; y--; } v[y + 1] = t; }
  return k % 2 ? v[k / 2] : (v[k / 2 - 1] + v[k / 2]) / 2;
}
static double cleanNum(double x) { return isNum(x) && x <= SEL_RUSAK ? x : NAN; }

// ---------- pembersihan sampel (preprocess.py) ----------
Sample cleanSample(const Raw &r) {
  Sample s;
  s.v = cleanNum(r.voltage);
  s.i = cleanNum(r.current);
  double p = cleanNum(r.power);
  if (!isNum(p) && !r.off && isNum(s.v) && isNum(s.i)) p = s.v * s.i;
  if (isNum(p) && (p > P_MAX || (isNum(s.v) && p > 1.5 * s.v * s.v / R_LOAD + 20))) p = NAN;
  if (r.off) p = 0;
  s.p = p;
  s.on = r.off ? 0 : 1;
  s.ws = cleanNum(r.ws); if (isNum(s.ws) && s.ws > WIND_MAX) s.ws = NAN;
  s.wd = cleanNum(r.wd); if (s.wd == -115) s.wd = NAN;
  s.rh = cleanNum(r.rh); if (isNum(s.rh) && (s.rh < 0 || s.rh > 100)) s.rh = NAN;
  s.tc = cleanNum(r.tc); if (isNum(s.tc) && s.tc < 5) s.tc = NAN;
  return s;
}

Minute MinuteAcc::aggregate() const {
  double a[CAP] = {}, sn[CAP] = {}, cs[CAP] = {};
  Minute m;
  m.n = n;
  auto col = [&](double Sample::*f) { for (int j = 0; j < n; j++) a[j] = s[j].*f; return a; };
  m.p = meanOf(col(&Sample::p), n, 1);
  m.on = meanOf(col(&Sample::on), n, 1);
  m.v = meanOf(col(&Sample::v), n, 1);
  m.i = meanOf(col(&Sample::i), n, 1);
  m.ws = medianOf(col(&Sample::ws), n);
  m.wsMax = maxOf(col(&Sample::ws), n, 1);
  for (int j = 0; j < n; j++) {
    double r = isNum(s[j].wd) ? s[j].wd * PI_D / 180 : NAN;
    sn[j] = isNum(r) ? sin(r) : NAN;
    cs[j] = isNum(r) ? cos(r) : NAN;
  }
  m.ds = meanOf(sn, n, 1);
  m.dc = meanOf(cs, n, 1);
  m.rh = meanOf(col(&Sample::rh), n, 1);
  m.tc = meanOf(col(&Sample::tc), n, 1);
  return m;
}

// ---------- riwayat ----------
static int slot(int64_t m) { return (int)(((m % History::CAP) + History::CAP) % History::CAP); }
void History::put(int64_t m, const Minute &a) { int k = slot(m); idx_[k] = m; v_[k] = a; used_[k] = true; }
const Minute *History::get(int64_t m) const { int k = slot(m); return used_[k] && idx_[k] == m ? &v_[k] : nullptr; }
double History::val(int64_t m, int key) const {
  const Minute *a = get(m);
  if (!a) return NAN;
  switch (key) {
    case K_P: return a->p; case K_ON: return a->on; case K_V: return a->v; case K_I: return a->i;
    case K_WS: return a->ws; case K_WSMAX: return a->wsMax; case K_DS: return a->ds; case K_DC: return a->dc;
    case K_RH: return a->rh; case K_TC: return a->tc;
  }
  return NAN;
}
int History::count(int64_t from, int64_t to) const { int c = 0; for (int64_t k = from; k <= to; k++) if (get(k)) c++; return c; }

// ---------- Open-Meteo ----------
void OmForecast::at(int64_t ts, double *w, double *p) const {
  *w = *p = NAN;
  if (n < 2 || ts <= t[0] || ts >= t[n - 1]) return;
  int k = 0; while (t[k + 1] < ts) k++;
  double f = (double)(ts - t[k]) / (double)(t[k + 1] - t[k]);
  *w = wind[k] + f * (wind[k + 1] - wind[k]);
  *p = pres[k] + f * (pres[k + 1] - pres[k]);
}

static double airDensity(double tc, double rh, double ph) {
  double tk = tc + 273.15, psat = 6.1078 * pow(10, (7.5 * tc) / (tc + 237.3)), pv = (rh / 100) * psat;
  return ((ph - pv) * 100) / (287.05 * tk) + (pv * 100) / (461.5 * tk);
}

// ---------- fitur ----------
Features features(const History &h, int64_t m, const OmForecast *om, const PowerEst *est, bool longgar) {
  Features F;
  auto need = [&](int n, int ketat) { return longgar ? (n + 1) / 2 : ketat; };
  auto get = [&](int64_t k, int key) {
    double x = h.val(k, key);
    if (key != K_P || isNum(x) || !est) return x;
    return est->get(k);
  };
  auto win = [&](int key, int n, double *out) { for (int j = 0; j < n; j++) out[j] = get(m - n + 1 + j, key); };
  auto lag = [&](int key, int d) {
    double x = get(m - d, key); if (isNum(x)) return x;
    const int e[10] = {1, -1, 2, -2, 3, -3, 4, -4, 5, -5};
    const int ne = longgar ? 10 : 4;
    for (int j = 0; j < ne; j++) { if (e[j] > d) continue; x = get(m - d + e[j], key); if (isNum(x)) return x; }   // tanpa menit sesudah m
    return (double)NAN;
  };
  int64_t ts = m * 60;
  F.hour = (double)(((m + 420) % 1440 + 1440) % 1440) / 60.0;     // WIB = UTC+7, m = menit utuh
  double ws[60], ps[60], ds10[10], dc10[10], wmax10[10], cube[60];
  win(K_WS, 60, ws); win(K_P, 60, ps); win(K_DS, 10, ds10); win(K_DC, 10, dc10); win(K_WSMAX, 10, wmax10);
  const double *w10 = ws + 50, *w30 = ws + 30;
  double s10 = meanOf(ds10, 10, need(10, 5)), c10 = meanOf(dc10, 10, need(10, 5)), nrm = hypot(s10, c10);
  double dirS = isNum(nrm) && nrm > 0 ? s10 / nrm : 0, dirC = isNum(nrm) && nrm > 0 ? c10 / nrm : 0;
  // suhu/kelembapan: rata-rata 30 menit, diisi ke depan maks 180 menit, lalu nilai tipikal
  auto ffill = [&](int key) {
    double r[30];
    for (int back = 0; back <= 180; back++) {
      for (int j = 0; j < 30; j++) r[j] = h.val(m - back - 29 + j, key);
      double x = meanOf(r, 30, 1); if (isNum(x)) return x;
    }
    return (double)NAN;
  };
  double tc = ffill(K_TC), rh = ffill(K_RH);
  double omW = NAN, omP = NAN;
  if (om) om->at(ts, &omW, &omP);
  double rho = isNum(tc) && isNum(rh) && isNum(omP) ? airDensity(tc, rh, omP) : NAN;
  if (!isNum(rho)) rho = TYP_RHO;
  if (!isNum(tc)) tc = TYP_TEMP_C;
  if (!isNum(rh)) rh = TYP_RH;
  double omNext[61], dummy;
  for (int k = 0; k <= 60; k++) { omNext[k] = NAN; if (om) om->at(ts + k * 60, &omNext[k], &dummy); }

  double *fc = F.fc;
  fc[0] = longgar ? lag(K_P, 0) : get(m, K_P); fc[1] = lag(K_P, 5); fc[2] = lag(K_P, 15); fc[3] = lag(K_P, 30); fc[4] = lag(K_P, 60);
  fc[5] = meanOf(ps, 60, need(60, 50));
  fc[6] = longgar ? lag(K_WS, 0) : h.val(m, K_WS); fc[7] = meanOf(w10, 10, need(10, 8)); fc[8] = meanOf(ws, 60, need(60, 50));
  for (int j = 0; j < 60; j++) cube[j] = ws[j] * ws[j] * ws[j];
  fc[9] = meanOf(cube + 50, 10, need(10, 8));
  fc[10] = dirS; fc[11] = dirC;
  fc[12] = sin(2 * PI_D * F.hour / 24); fc[13] = cos(2 * PI_D * F.hour / 24);
  fc[14] = rho; fc[15] = meanOf(omNext, 61, 61);

  double *pc = F.pc;
  pc[0] = fc[6]; pc[1] = fc[7]; pc[2] = meanOf(w30, 30, need(30, 24)); pc[3] = meanOf(ws, 60, need(60, 48));
  pc[4] = fc[9]; pc[5] = meanOf(cube + 30, 30, need(30, 24));
  pc[6] = maxOf(wmax10, 10, need(10, 8)); pc[7] = stdOf(w10, 10, need(10, 8));
  pc[8] = dirS; pc[9] = dirC; pc[10] = fc[12]; pc[11] = fc[13];
  pc[12] = rho; pc[13] = rh; pc[14] = tc; pc[15] = omW;
  F.pMean10 = meanOf(ps + 50, 10, need(10, 8));
  F.pEstimated = 0;
  if (est) for (int64_t k = m - 60; k <= m; k++) if (!isNum(h.val(k, K_P)) && isNum(est->get(k))) F.pEstimated++;
  return F;
}

// ---------- MLP INT8 ----------
double roundHalfEven(double x) {
  double f = floor(x), d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return fmod(f, 2) == 0 ? f : f + 1;
}
bool quantize(Model md, const double f[16], int8_t xq[16]) {
  const bool fcs = md != MODEL_POWERCURVE;   // MODEL_OFFLINE memakai skala MODEL_FORECAST
  const double *c = fcs ? FC_CENTER : PC_CENTER, *s = fcs ? FC_SCALE : PC_SCALE;
  for (int j = 0; j < 16; j++) if (!isNum(f[j])) return false;
  for (int j = 0; j < 16; j++) {
    double q = roundHalfEven((f[j] - c[j]) / s[j]);
    xq[j] = (int8_t)(q < -128 ? -128 : q > 127 ? 127 : q);
  }
  return true;
}
int8_t forward(Model md, const int8_t xq[16], int8_t *h1o, int8_t *h2o) {
  int8_t h1[32], h2[16], y;
  if (md == MODEL_FORECAST) {
    mlp_layer(xq, 16, MLP_W1, MLP_B1, 32, h1); mlp_layer(h1, 32, MLP_W2, MLP_B2, 16, h2); mlp_layer(h2, 16, MLP_W3, MLP_B3, 1, &y);
  } else if (md == MODEL_OFFLINE) {
    mlp_layer(xq, 16, OFF_W1, OFF_B1, 32, h1); mlp_layer(h1, 32, OFF_W2, OFF_B2, 16, h2); mlp_layer(h2, 16, OFF_W3, OFF_B3, 1, &y);
  } else {
    mlp_layer(xq, 16, PC_W1, PC_B1, 32, h1); mlp_layer(h1, 32, PC_W2, PC_B2, 16, h2); mlp_layer(h2, 16, PC_W3, PC_B3, 1, &y);
  }
  if (h1o) for (int j = 0; j < 32; j++) h1o[j] = h1[j];
  if (h2o) for (int j = 0; j < 16; j++) h2o[j] = h2[j];
  return y;
}
double wattPerLsb(Model md) { return md == MODEL_POWERCURVE ? PC_W_PER_LSB : FC_W_PER_LSB; }

// ---------- interval + status ----------
void interval(double watt, double *p10, double *p90) {
  for (int k = 0; k < IV_N; k++) if (watt >= IV_DARI[k] && watt < IV_SAMPAI[k]) { *p10 = IV_P10[k]; *p90 = IV_P90[k]; return; }
  *p10 = IV_P10[IV_N - 1]; *p90 = IV_P90[IV_N - 1];
}
const char *statusLabel(Status s) {
  switch (s) {
    case ST_ANGIN_LEMAH: return "Angin lemah";
    case ST_NORMAL: return "Normal";
    case ST_BAWAH: return "Di bawah normal";
    case ST_ATAS: return "Di atas normal";
    default: return "Menunggu data";
  }
}
Status status(const double actual30[30], const double expected30[30], double *ratio, double *expected) {
  double e = meanOf(expected30, 30, 10), x = meanOf(actual30, 30, 10);
  *ratio = NAN; *expected = e;
  if (!isNum(e) || !isNum(x)) return ST_MENUNGGU;
  if (e <= STATUS_MIN_WAJAR_W) return ST_ANGIN_LEMAH;
  *ratio = x / e;
  return *ratio < STATUS_BAWAH ? ST_BAWAH : *ratio > STATUS_ATAS ? ST_ATAS : ST_NORMAL;
}

// ---------- baterai (sim_battery.py) ----------
static double dcForAc(double ac) {
  if (ac <= INV_AC_W[0]) return INV_DC_W[0];
  for (int k = 1; k < INV_N; k++)
    if (ac <= INV_AC_W[k]) return INV_DC_W[k - 1] + (ac - INV_AC_W[k - 1]) / (INV_AC_W[k] - INV_AC_W[k - 1]) * (INV_DC_W[k] - INV_DC_W[k - 1]);
  return INV_DC_W[INV_N - 1];
}
double loadAt(int64_t ts) {
  int hh = (int)((((ts + 7 * 3600) % 86400) + 86400) % 86400 / 3600);
  return BAT_BEBAN_DASAR_W + (hh >= BAT_JAM_MALAM_DARI && hh < BAT_JAM_MALAM_SAMPAI ? BAT_BEBAN_MALAM_W : 0);
}
BatStep batteryStep(double soc, double pDc, int64_t ts) {
  const double cap = BAT_KAPASITAS_WH, need = dcForAc(loadAt(ts));
  double e = ((isNum(pDc) ? pDc : 0) * BAT_ETA_CHARGE_CONTROLLER - need) / 60;
  BatStep r = {soc, 0, 0, 0, loadAt(ts)};
  if (e >= 0) {
    double room = (BAT_SOC_MAX - soc) * cap, st = fmin(e * BAT_ETA_ISI, room);
    r.toBatt = st; r.dumped = e - st / BAT_ETA_ISI; r.soc = soc + st / cap;
  } else {
    double avail = (soc - BAT_SOC_MIN) * cap, draw = fmin(-e / BAT_ETA_BUANG, avail);
    r.soc = soc - draw / cap; r.toBatt = -draw; r.grid = -e - draw * BAT_ETA_BUANG;
  }
  return r;
}
SocFc socForecast(double soc, double pHat, int64_t ts) {
  double load = 0;
  for (int k = 1; k <= 60; k++) load += loadAt(ts + k * 60);
  load /= 60;
  double net = pHat * BAT_ETA_CHARGE_CONTROLLER - dcForAc(load);
  double e = net >= 0 ? net * BAT_ETA_ISI : net / BAT_ETA_BUANG;
  double s = soc + e / BAT_KAPASITAS_WH;
  return {fmin(BAT_SOC_MAX, fmax(BAT_SOC_MIN, s)), e, s <= BAT_SOC_MIN};
}

// Histeresis supaya relai tidak bolak-balik tiap menit.
static const double PLN_KEMBALI = 0.15;   // kembali ke baterai setelah SoC naik 15 poin di atas batas bawah
static const double DUMP_LEPAS = 0.05;    // beban buang dilepas setelah SoC turun 5 poin dari penuh
Relay decide(const Relay &prev, double soc, const SocFc &fc, double pNow) {
  Relay r = prev;
  if (!prev.pln && (soc <= BAT_SOC_MIN + 0.02 || fc.gridSoon)) r.pln = true;
  else if (prev.pln && soc >= BAT_SOC_MIN + PLN_KEMBALI && !fc.gridSoon) r.pln = false;
  bool surplus = isNum(pNow) && pNow * BAT_ETA_CHARGE_CONTROLLER > dcForAc(BAT_BEBAN_DASAR_W);
  if (!prev.dump && soc >= BAT_SOC_MAX - 0.01 && surplus) r.dump = true;
  else if (prev.dump && (soc < BAT_SOC_MAX - DUMP_LEPAS || !surplus)) r.dump = false;
  return r;
}

// ---------- UART FPGA ----------
uint8_t crc8(const uint8_t *d, int n) {
  uint8_t c = 0x00;
  for (int k = 0; k < n; k++) {
    c ^= d[k];
    for (int b = 0; b < 8; b++) c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
  }
  return c;
}
int fpgaFrame(Model md, const int8_t xq[16], bool dual, uint8_t *buf) {
  int k = 0;
  buf[k++] = 0xAA; buf[k++] = 0x55;
  if (dual) buf[k++] = (uint8_t)md;
  for (int j = 0; j < 16; j++) buf[k++] = (uint8_t)xq[j];
  buf[k] = crc8(buf + 2, k - 2);
  return k + 1;
}
bool fpgaParse(const uint8_t rx[7], int8_t *out, uint16_t *cycles, uint8_t *status) {
  *status = 0xFF;
  if (rx[0] != 0x55 || rx[1] != 0xAA || crc8(rx + 2, 4) != rx[6]) return false;
  *status = rx[2];
  *out = (int8_t)rx[3];
  *cycles = (uint16_t)((rx[4] << 8) | rx[5]);
  return *status == 0x00 && *out >= 0;
}

}  // namespace wec
