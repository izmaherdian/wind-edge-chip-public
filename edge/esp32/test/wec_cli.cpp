// Pembungkus baris perintah untuk menguji wec_core di laptop (dipakai run_native.py).
// Masukan stdin, satu perintah per baris:
//   M m n p on v i ws wsMax ds dc rh tc   simpan agregat menit m (nan boleh)
//   O t_s wind pres                       tambah satu jam prakiraan Open-Meteo
//   F m                                   -> "F m fc0..15 pc0..15 pMean10"
//   E m w                                 simpan daya wajar menit m (pengganti saat PZEM diam)
//   G m                                   -> sama dengan F, tetapi daya kosong diganti daya wajar + "nEst"
//   L m                                   -> sama dengan G, dengan syarat menit longgar (data berlubang)
//   V md x0..x15                          -> "V out h1_0..31 h2_0..15"
//   Q md f0..f15                          -> "Q ok x0..15"
//   B soc p t_s                           -> "B soc toBatt dumped grid load"
//   S soc p t_s                           -> "S soc energyWh gridSoon"
//   T x0..x15                             -> "T b0..b18" (paket UART ke FPGA)
//   R b0..b6                              -> "R ok status out cycles" (balasan FPGA)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "wec_core.h"

using namespace wec;

static History H;
static OmForecast OM;
static PowerEst EST;

int main() {
  char line[4096];
  while (fgets(line, sizeof line, stdin)) {
    char *p = line, *e;
    char c = *p++;
    auto num = [&]() { double v = strtod(p, &e); p = e; return v; };
    if (c == 'M') {
      int64_t m = (int64_t)num();
      Minute a; a.n = (int)num();
      a.p = num(); a.on = num(); a.v = num(); a.i = num(); a.ws = num(); a.wsMax = num();
      a.ds = num(); a.dc = num(); a.rh = num(); a.tc = num();
      H.put(m, a);
    } else if (c == 'O') {
      if (OM.n < OmForecast::CAP) { OM.t[OM.n] = (int64_t)num(); OM.wind[OM.n] = num(); OM.pres[OM.n] = num(); OM.n++; }
    } else if (c == 'F') {
      int64_t m = (int64_t)num();
      Features f = features(H, m, OM.n ? &OM : nullptr);
      printf("F %lld", (long long)m);
      for (double x : f.fc) printf(" %.17g", x);
      for (double x : f.pc) printf(" %.17g", x);
      printf(" %.17g\n", f.pMean10);
    } else if (c == 'E') {
      int64_t m = (int64_t)num(); EST.put(m, num());
    } else if (c == 'G' || c == 'L') {
      int64_t m = (int64_t)num();
      Features f = features(H, m, OM.n ? &OM : nullptr, &EST, c == 'L');
      printf("%c %lld", c, (long long)m);
      for (double x : f.fc) printf(" %.17g", x);
      for (double x : f.pc) printf(" %.17g", x);
      printf(" %.17g %d\n", f.pMean10, f.pEstimated);
    } else if (c == 'V') {
      Model md = (Model)(int)num();
      int8_t x[16], h1[32], h2[16];
      for (int j = 0; j < 16; j++) x[j] = (int8_t)num();
      int8_t y = forward(md, x, h1, h2);
      printf("V %d", y);
      for (int8_t v : h1) printf(" %d", v);
      for (int8_t v : h2) printf(" %d", v);
      printf("\n");
    } else if (c == 'Q') {
      Model md = (Model)(int)num();
      double f[16]; int8_t x[16];
      for (int j = 0; j < 16; j++) f[j] = num();
      bool ok = quantize(md, f, x);
      printf("Q %d", ok);
      for (int8_t v : x) printf(" %d", ok ? v : 0);
      printf("\n");
    } else if (c == 'T') {
      int8_t x[16]; uint8_t buf[24];
      for (int j = 0; j < 16; j++) x[j] = (int8_t)num();
      int n = fpgaFrame(MODEL_FORECAST, x, false, buf);
      printf("T");
      for (int j = 0; j < n; j++) printf(" %d", buf[j]);
      printf("\n");
    } else if (c == 'R') {
      uint8_t rx[7]; int8_t out = 0; uint16_t cyc = 0; uint8_t stt = 0;
      for (int j = 0; j < 7; j++) rx[j] = (uint8_t)num();
      bool ok = fpgaParse(rx, &out, &cyc, &stt);
      printf("R %d %d %d %d\n", ok, stt, out, cyc);
    } else if (c == 'B') {
      double soc = num(), pw = num(); int64_t t = (int64_t)num();
      BatStep b = batteryStep(soc, pw, t);
      printf("B %.17g %.17g %.17g %.17g %.17g\n", b.soc, b.toBatt, b.dumped, b.grid, b.load);
    } else if (c == 'S') {
      double soc = num(), pw = num(); int64_t t = (int64_t)num();
      SocFc s = socForecast(soc, pw, t);
      printf("S %.17g %.17g %d\n", s.soc, s.energyWh, s.gridSoon);
    }
    fflush(stdout);
  }
  return 0;
}
