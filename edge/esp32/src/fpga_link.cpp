#include "fpga_link.h"

#include <Arduino.h>

#include "config.h"

static FpgaStats stats;
FpgaStats &fpgaStats() { return stats; }

// Terima 7 byte balasan; byte sebelum 0x55 0xAA dibuang (derau atau sisa paket lama).
static bool readFrame(uint8_t rx[wec::FPGA_RX_LEN], uint32_t timeoutMs) {
  uint32_t t0 = millis();
  int k = 0;
  while (k < wec::FPGA_RX_LEN && millis() - t0 < timeoutMs) {
    if (!Serial1.available()) continue;
    uint8_t b = (uint8_t)Serial1.read();
    if (k == 0 && b != 0x55) continue;
    if (k == 1 && b != 0xAA) { k = b == 0x55 ? 1 : 0; continue; }
    rx[k++] = b;
  }
  return k == wec::FPGA_RX_LEN;
}

void fpgaBegin() {
  if (FPGA_RST >= 0) { pinMode(FPGA_RST, OUTPUT); digitalWrite(FPGA_RST, HIGH); }
  Serial1.begin(FPGA_BAUD, SERIAL_8N1, FPGA_RX, FPGA_TX);
}

// Paket berbingkai + CRC-8 (top_soc.v): FPGA membuang paket rusak dan menjawab status 0xE1, dan watchdog-nya
// mengembalikan penerima ke awal bila paket terputus. ESP32 cukup mencoba ulang sekali.
FpgaResult fpgaInfer(wec::Model md, const int8_t xq[16]) {
  FpgaResult r;
  if (!FPGA_DUAL_MODEL && md != wec::MODEL_FORECAST) return r;   // RTL sekarang hanya memuat model prediksi
  uint8_t tx[wec::FPGA_TX_LEN + 1], rx[wec::FPGA_RX_LEN], status = 0xFF;
  int n = wec::fpgaFrame(md, xq, FPGA_DUAL_MODEL, tx);
  for (int coba = 0; coba < 2; coba++) {
    while (Serial1.available()) Serial1.read();
    uint32_t t0 = micros();
    Serial1.write(tx, n);
    if (readFrame(rx, FPGA_TIMEOUT_MS) && wec::fpgaParse(rx, &r.out, &r.cycles, &status)) {
      r.us = micros() - t0;
      r.ok = true;
      stats.ok++;
      return r;
    }
    stats.resync++;                      // dihitung sebagai percobaan ulang (CRC/status/timeout)
  }
  if (FPGA_RST >= 0) { digitalWrite(FPGA_RST, LOW); delay(2); digitalWrite(FPGA_RST, HIGH); }
  stats.timeout++;
  return r;
}
