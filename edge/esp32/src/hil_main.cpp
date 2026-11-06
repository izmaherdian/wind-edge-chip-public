// Firmware uji HIL ESP32-S3 <-> Tang Nano 4K (env esp32s3_hil). Tanpa sensor dan tanpa WiFi.
// Tiap ronde: satu transaksi dicetak byte demi byte (diagnosis kabel), lalu 597 vektor uji nyata dikirim ke FPGA
// dan dibandingkan dengan golden model (test_vectors.csv) serta MLP di CPU ESP32.
// Pemakaian: pio run -d edge/esp32 -e esp32s3_hil -t upload && pio device monitor -d edge/esp32 -e esp32s3_hil
#include <Arduino.h>

#include "config.h"
#include "fpga_link.h"
#include "hil_vectors.h"
#include "wec_core.h"

static void dumpOne() {
  uint8_t tx[wec::FPGA_TX_LEN], rx[32];
  int n = wec::fpgaFrame(wec::MODEL_FORECAST, HIL_X[0], false, tx);
  while (Serial1.available()) Serial1.read();
  Serial1.write(tx, n);
  uint32_t t0 = millis();
  int k = 0;
  while (millis() - t0 < 30 && k < (int)sizeof rx) if (Serial1.available()) rx[k++] = (uint8_t)Serial1.read();
  Serial.print("TX:");
  for (int j = 0; j < n; j++) Serial.printf(" %02X", tx[j]);
  Serial.printf("\nRX (%d byte):", k);
  for (int j = 0; j < k; j++) Serial.printf(" %02X", rx[j]);
  if (k == 0) Serial.print("  <- tidak ada balasan: cek kabel TX/RX, GND, level tegangan, dan bitstream 921600");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  fpgaBegin();
  Serial.printf("\nHIL Wind Edge Chip: ESP32-S3 TX=GPIO%d RX=GPIO%d -> FPGA pin 44/46, %d bps, %d vektor\n",
                FPGA_TX, FPGA_RX, FPGA_BAUD, HIL_N);
}

void loop() {
  static int ronde = 0;
  ronde++;
  dumpOne();
  int ok = 0, beda = 0, gagal = 0;
  uint32_t usSum = 0, usMax = 0;
  uint16_t cyc = 0;
  for (int k = 0; k < HIL_N; k++) {
    FpgaResult r = fpgaInfer(wec::MODEL_FORECAST, HIL_X[k]);
    int8_t cpu = wec::forward(wec::MODEL_FORECAST, HIL_X[k]);
    if (!r.ok) { gagal++; continue; }
    usSum += r.us; if (r.us > usMax) usMax = r.us; cyc = r.cycles;
    if (r.out == HIL_OUT[k] && r.out == cpu) ok++;
    else { beda++; if (beda <= 5) Serial.printf("[V%d] fpga=%d cpu=%d golden=%d\n", k, r.out, cpu, HIL_OUT[k]); }
  }
  int dijawab = ok + beda;
  Serial.printf("HIL ronde %d: %d/%d identik, %d beda, %d tanpa jawaban | siklus FPGA %u | pulang-pergi rata-rata %.1f us (maks %u us) | coba ulang %u\n",
                ronde, ok, HIL_N, beda, gagal, cyc, dijawab ? (float)usSum / dijawab : 0.0f, usMax, fpgaStats().resync);
  delay(5000);
}
