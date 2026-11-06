// Inti mesin WEC untuk ESP32 (C++ murni, tanpa Arduino), supaya bisa diuji di laptop.
// Logika sama dengan dashboard/wec/engine_core.js dan Python:
//   ml/common/preprocess.py (pembersihan + agregasi 1 menit)
//   ml/forecast/features.py (16 fitur prediksi), ml/status/train_powercurve_mlp.py (16 fitur kurva daya)
//   ml/golden_model.py (MLP INT8 identik RTL), ml/battery/sim_battery.py (baterai)
// Uji: python3 edge/esp32/test/run_native.py
#pragma once
#include <math.h>
#include <stdint.h>

namespace wec {

// ---------- sampel mentah (satu bacaan sensor, ±3 detik) ----------
struct Raw {
  double voltage = NAN, current = NAN, power = NAN;   // PZEM; NaN = tidak terbaca
  bool off = false;                                   // turbin OFF (daya dianggap 0 W)
  double ws = NAN, wd = NAN, rh = NAN, tc = NAN;      // stasiun cuaca
};

struct Sample {
  double p, on, v, i, ws, wd, rh, tc;
};

struct Minute {        // agregat 1 menit (preprocess.py)
  int n = 0;
  double p, on, v, i, ws, wsMax, ds, dc, rh, tc;
};

bool isNum(double x);
Sample cleanSample(const Raw &r);
// Kumpulkan sampel satu menit, lalu agregat(). Kapasitas 40 sampel (cukup untuk interval 3 detik).
struct MinuteAcc {
  static const int CAP = 40;
  Sample s[CAP];
  int n = 0;
  void add(const Sample &x) { if (n < CAP) s[n++] = x; }
  Minute aggregate() const;
  void clear() { n = 0; }
};

// ---------- riwayat per menit (ring buffer) ----------
// 256 menit: cukup untuk lag 60 (+2) dan isi-ke-depan suhu/kelembapan 180+29 menit.
class History {
 public:
  static const int CAP = 256;
  void put(int64_t m, const Minute &a);
  const Minute *get(int64_t m) const;          // nullptr bila tidak ada
  double val(int64_t m, int key) const;        // NaN bila tidak ada
  int count(int64_t from, int64_t to) const;   // jumlah menit berisi di [from, to]
 private:
  int64_t idx_[CAP];
  Minute v_[CAP];
  bool used_[CAP] = {false};
};
enum Key { K_P, K_ON, K_V, K_I, K_WS, K_WSMAX, K_DS, K_DC, K_RH, K_TC };

// ---------- prakiraan Open-Meteo per jam ----------
#ifndef WEC_OM_CAP
#define WEC_OM_CAP 96  // 4 hari per jam (forecast_days=3 + 1 hari lalu)
#endif
struct OmForecast {
  static const int CAP = WEC_OM_CAP;
  int n = 0;
  int64_t t[CAP];      // detik UTC
  double wind[CAP];    // wind_speed_10m (m/s)
  double pres[CAP];    // surface_pressure (hPa)
  void at(int64_t t_s, double *w, double *p) const;   // interpolasi linear; NaN di luar rentang
};

// ---------- daya wajar per menit (pengganti daya saat PZEM diam) ----------
class PowerEst {
 public:
  static const int CAP = 256;
  void put(int64_t m, double w) { int k = (int)(((m % CAP) + CAP) % CAP); idx_[k] = m; v_[k] = w; used_[k] = true; }
  double get(int64_t m) const { int k = (int)(((m % CAP) + CAP) % CAP); return used_[k] && idx_[k] == m ? v_[k] : NAN; }
 private:
  int64_t idx_[CAP];
  double v_[CAP];
  bool used_[CAP] = {false};
};

// ---------- fitur ----------
struct Features {
  double fc[16];       // urutan = docs/kontrak-kuantisasi.md (byte ke FPGA)
  double pc[16];       // fitur kurva daya (fitur 1)
  double pMean10;      // rata-rata daya 10 menit (pembanding kurva daya)
  double hour;         // jam WIB desimal
  int pEstimated;      // menit m-60..m yang dayanya diganti daya wajar
};
// est (opsional): daya kosong diganti daya wajar dari MLP kurva daya, sama dengan engine_core.js
// longgar: syarat jumlah menit separuh jendela + lag dicari sampai ±5 menit (data berlubang); sama dengan opt.longgar di JS
Features features(const History &h, int64_t m, const OmForecast *om, const PowerEst *est = nullptr, bool longgar = false);

// ---------- MLP INT8 (bit-exact dengan golden_model.py dan RTL) ----------
// MODEL_OFFLINE: prediksi tanpa Open-Meteo (masukan ke-16 = 0), skala fitur sama dengan MODEL_FORECAST; hanya CPU
// (FPGA berisi bobot MODEL_FORECAST). Uji 1-20 Okt: MAE 5,62 W vs 5,48 W dengan Open-Meteo.
enum Model { MODEL_FORECAST = 0, MODEL_POWERCURVE = 1, MODEL_OFFLINE = 2 };
bool quantize(Model md, const double f[16], int8_t xq[16]);   // false bila ada fitur NaN
int8_t forward(Model md, const int8_t xq[16], int8_t *h1 = nullptr, int8_t *h2 = nullptr);
double wattPerLsb(Model md);
double roundHalfEven(double x);

// ---------- interval + status (fitur 1) ----------
void interval(double watt, double *p10, double *p90);
enum Status { ST_MENUNGGU, ST_ANGIN_LEMAH, ST_NORMAL, ST_BAWAH, ST_ATAS };
const char *statusLabel(Status s);
// actual30/expected30: 30 menit terakhir (NaN bila kosong)
Status status(const double actual30[30], const double expected30[30], double *ratio, double *expected);

// ---------- baterai (fitur 3) ----------
struct BatStep { double soc, toBatt, dumped, grid, load; };
double loadAt(int64_t t_s);
BatStep batteryStep(double soc, double pDc, int64_t t_s);
struct SocFc { double soc, energyWh; bool gridSoon; };
SocFc socForecast(double soc, double pHat, int64_t t_s);

// Keputusan relai: beban ke baterai/inverter atau ke PLN, dengan histeresis.
struct Relay { bool pln; bool dump; };
Relay decide(const Relay &prev, double soc, const SocFc &fc, double pNow);

// ---------- paket UART ke FPGA (hw/rtl/top_soc.v, branch feature/fpga 21 Okt) ----------
// Host -> FPGA 19 byte: [0xAA, 0x55, 16 fitur INT8, CRC8(16 fitur)]
// FPGA -> host 7 byte : [0x55, 0xAA, status, prediksi, siklus MSB, siklus LSB, CRC8(status..siklus LSB)]
// CRC-8 polinomial 0x07, awal 0x00 (hw/sim/crc8_util.py). status 0x00 = OK, 0xE1 = CRC salah, 0xE2 = timeout.
// dual = usulan docs/usulan-rtl-dua-model.md: model_id disisipkan sebelum fitur (ikut dihitung CRC).
static const int FPGA_TX_LEN = 19, FPGA_RX_LEN = 7;
uint8_t crc8(const uint8_t *d, int n);
int fpgaFrame(Model md, const int8_t xq[16], bool dual, uint8_t *buf);   // mengembalikan panjang
// true bila sinkron, CRC cocok, dan status OK; *status diisi kode status (0xFF bila sinkron/CRC salah)
bool fpgaParse(const uint8_t rx[7], int8_t *out, uint16_t *cycles, uint8_t *status);

}  // namespace wec
