#include "sensors.h"

#include <Arduino.h>
#include <ModbusMaster.h>

#include "config.h"

static ModbusMaster pzem, station;
static volatile uint32_t pulses = 0, lastUs = 0;
static uint32_t lastSampleMs = 0;

static void IRAM_ATTR onPulse() {
  uint32_t now = micros();
  if (now - lastUs >= 2000) { pulses++; lastUs = now; }   // debounce 2 ms, sama dengan anemometer.ino
}
static void preTx() { if (RS485_DE >= 0) digitalWrite(RS485_DE, HIGH); }
static void postTx() { if (RS485_DE >= 0) digitalWrite(RS485_DE, LOW); }

// Satu bus dipakai dua perangkat dengan baud berbeda: UART2 dibuka ulang sebelum tiap transaksi.
static void busFor(uint32_t baud, uint32_t cfg) {
  Serial2.flush();
  Serial2.end();
  Serial2.begin(baud, cfg, RS485_RX, RS485_TX);
}

void sensorsBegin() {
  if (RS485_DE >= 0) { pinMode(RS485_DE, OUTPUT); digitalWrite(RS485_DE, LOW); }
  Serial2.begin(9600, SERIAL_8N2, RS485_RX, RS485_TX);
  pzem.begin(PZEM_ADDR, Serial2);
  station.begin(STATION_ADDR, Serial2);
  for (ModbusMaster *m : {&pzem, &station}) { m->preTransmission(preTx); m->postTransmission(postTx); }
  pinMode(ANEMO_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ANEMO_PIN), onPulse, FALLING);
  lastSampleMs = millis();
}

static bool readPzem(Reading &r) {
  busFor(9600, SERIAL_8N2);
  if (pzem.readInputRegisters(0x0000, 6) != pzem.ku8MBSuccess) return false;
  r.raw.voltage = pzem.getResponseBuffer(0) * 0.01;
  r.raw.current = pzem.getResponseBuffer(1) * 0.01;
  r.raw.power = (((uint32_t)pzem.getResponseBuffer(3) << 16) | pzem.getResponseBuffer(2)) * 0.1;
  r.energyWh = ((uint32_t)pzem.getResponseBuffer(5) << 16) | pzem.getResponseBuffer(4);
  return true;
}

static bool readStation(Reading &r) {
  busFor(4800, SERIAL_8N1);
  uint16_t v[7];
  if (station.readHoldingRegisters(0x01F4, 7) == station.ku8MBSuccess) {
    for (int k = 0; k < 7; k++) v[k] = station.getResponseBuffer(k);
  } else {   // sebagian stasiun hanya melayani baca satu register (cara Raspi)
    const uint16_t reg[5] = {0x01F4, 0x01F7, 0x01F8, 0x01F9, 0x01FA};
    const int at[5] = {0, 3, 4, 5, 6};
    for (int k = 0; k < 5; k++) {
      if (station.readHoldingRegisters(reg[k], 1) != station.ku8MBSuccess) return false;
      v[at[k]] = station.getResponseBuffer(0);
    }
  }
  r.raw.ws = v[0] * 0.01;
  r.raw.wd = (double)v[3] - 115;                  // 0 mentah -> -115 (sentinel, dibuang cleanSample)
  r.raw.rh = (v[4] * 0.1 - 3.265) / 1.073;
  r.raw.tc = (int16_t)v[5] * 0.1;
  r.noise = v[6] * 0.1;
  if (station.readHoldingRegisters(0x0201, 1) == station.ku8MBSuccess) r.rain = station.getResponseBuffer(0) * 0.1;
  return true;
}

Reading sensorsRead() {
  Reading r;
  r.pzemOk = readPzem(r);
  r.stationOk = readStation(r);
  uint32_t now = millis(), n;
  noInterrupts(); n = pulses; pulses = 0; interrupts();
  float dt = (now - lastSampleMs) / 1000.0f;
  lastSampleMs = now;
  if (dt > 0) r.windArduino = 2 * PI * ANEMO_RADIUS_M * ((float)n / ANEMO_SLOTS) / dt * ANEMO_CALIB;
  return r;
}
