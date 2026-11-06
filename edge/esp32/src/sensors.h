// Pembacaan sensor: PZEM-017 (DC) dan stasiun cuaca lewat satu bus RS-485, anemometer optik lewat interupsi.
// Register dan rumus sama dengan program Raspi (edge/ta/akuisisi_raspi.py, anemometer.ino).
#pragma once
#include "wec_core.h"

struct Reading {
  wec::Raw raw;              // masukan cleanSample (V, I, P, angin stasiun, arah, RH, suhu)
  bool pzemOk = false, stationOk = false;
  double energyWh = NAN;     // PZEM register 4..5
  double windArduino = NAN;  // anemometer optik turbin (m/s), tidak dipakai model
  double noise = NAN, rain = NAN;
};

void sensorsBegin();
Reading sensorsRead();       // ±0,3 detik (dua transaksi Modbus)
