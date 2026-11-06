// Tautan UART ke akselerator MLP di FPGA (hw/rtl/top_soc.v): paket 19 byte [AA 55, 16 fitur INT8, CRC8] ->
// 7 byte [55 AA, status, prediksi, siklus MSB, LSB, CRC8], 921600 bps. Kalau FPGA tidak menjawab benar,
// pemanggil memakai wec::forward (bit-exact).
#pragma once
#include "wec_core.h"

struct FpgaResult {
  bool ok = false;
  int8_t out = 0;
  uint16_t cycles = 0;
  uint32_t us = 0;           // waktu kirim + hitung + terima (mikrodetik)
};
struct FpgaStats { uint32_t ok = 0, timeout = 0, resync = 0, mismatch = 0; };   // resync = percobaan ulang

void fpgaBegin();
FpgaResult fpgaInfer(wec::Model md, const int8_t xq[16]);
FpgaStats &fpgaStats();
