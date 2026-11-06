// Pengukur daya komputasi (env esp32_daya, ESP32 klasik terpisah): dua INA219 di dua bus I2C.
// Nama paket lama dipertahankan; pemasangan 21 Okt tertukar:
//   INA1 (I2C 0, SDA 21 / SCL 22), nama "raspberry_pi" = kanal FPGA+S3 (belum dipasang)
//   INA2 (I2C 1, SDA 18 / SCL 19), nama "fpga" = Raspberry Pi
// Pin, alamat 0x40, dan kalibrasi 32V_2A mengikuti kode tim; keluaran CSV di Serial tetap sama.
// WiFi: eduroam (WPA2-Enterprise) bila diisi di secrets.h, bergantian dengan hotspot (include/wifi_mulai.h).
// Tiap 1 detik dikirim ke MQTT WEC/daya; Node-RED meneruskannya ke panel "Konsumsi Daya" (/dashboard/hackathon).
#include <Adafruit_INA219.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "config.h"
#include "ina219_reading.h"
#include "wifi_mulai.h"

TwoWire I2C_1 = TwoWire(0);
TwoWire I2C_2 = TwoWire(1);
Adafruit_INA219 ina1(0x40);
Adafruit_INA219 ina2(0x40);

static WiFiClient net;
static PubSubClient mqtt(net);

struct Kanal {
  const char *nama;
  Adafruit_INA219 *ina;
  TwoWire *bus;
  bool ok = false;
  double energiWh = 0;
  float v = NAN, i = NAN, p = NAN;
  float shuntMv = NAN;
  bool valid = false;
  const char *error = "not_connected";
  bool snapshot = false;
  uint16_t rawBus = 0, rawShunt = 0, rawCurrent = 0, rawPower = 0, rawConfig = 0, rawCalibration = 0;
  double validSeconds = 0;
};
static Kanal kanal[2] = {{"raspberry_pi", &ina1, &I2C_1}, {"fpga", &ina2, &I2C_2}};

static const unsigned long INTERVAL = 1000;
static unsigned long prevMs = 0, lastTry = 0, lastSensorTry = 0;

// Tidak berhenti selamanya bila sensor belum terpasang: coba lagi tiap 10 detik.
static void mulaiSensor(Kanal &k) {
  if (k.ok) return;
  k.ok = k.ina->begin(k.bus);
  if (k.ok) k.ina->setCalibration_32V_2A();
  Serial.printf("Sensor %s %s\n", k.nama, k.ok ? "terhubung" : "tidak terdeteksi");
}

static bool tulisReg(Kanal &k, uint8_t reg, uint16_t value) {
  k.bus->beginTransmission(0x40);
  k.bus->write(reg);
  k.bus->write(uint8_t(value >> 8));
  k.bus->write(uint8_t(value));
  return k.bus->endTransmission() == 0;
}

static bool bacaReg(Kanal &k, uint8_t reg, uint16_t &value) {
  k.bus->beginTransmission(0x40);
  k.bus->write(reg);
  if (k.bus->endTransmission(false) != 0) return false;
  if (k.bus->requestFrom(uint8_t(0x40), uint8_t(2)) != 2) return false;
  value = uint16_t(k.bus->read()) << 8;
  value |= uint8_t(k.bus->read());
  return true;
}

static void baca(Kanal &k, float dtJam) {
  const bool sebelumnyaValid = k.valid;
  k.valid = false;
  k.snapshot = false;
  k.v = k.i = k.p = k.shuntMv = NAN;
  k.error = "not_connected";
  if (!k.ok) return;
  k.error = "i2c_error";
  // Trigger a single shunt + bus conversion, 16-sample averaging each.
  // Registers stay stable after completion; every transaction is checked.
  if (!tulisReg(k, 5, 4096) || !tulisReg(k, 0, 0x3e63)) { k.ok = false; return; }
  uint16_t bus = 0, shunt = 0, current = 0, power = 0;
  const unsigned long start = millis();
  do {
    if (!bacaReg(k, 2, bus)) { k.ok = false; return; }
    if (bus & 2) break;
    delay(1);
  } while (millis() - start < 100);
  if (!(bus & 2)) { k.error = "conversion_timeout"; return; }
  // Read power last: it clears the conversion-ready bit.
  if (!bacaReg(k, 1, shunt) || !bacaReg(k, 4, current) || !bacaReg(k, 3, power)) {
    k.ok = false; return;
  }
  if (!bacaReg(k, 0, k.rawConfig) || !bacaReg(k, 5, k.rawCalibration)) { k.ok = false; return; }
  k.rawBus = bus; k.rawShunt = shunt; k.rawCurrent = current; k.rawPower = power;
  k.snapshot = true;
  const auto r = decodeIna219(bus, int16_t(shunt), int16_t(current), power);
  k.v = r.voltage; k.i = r.current; k.shuntMv = r.shuntMv;
  k.error = r.error;
  if (k.rawCalibration != 4096) k.error = "calibration_readback_mismatch";
  else if (k.rawConfig != 0x3e63) k.error = "config_readback_mismatch";
  k.valid = !*k.error;
  k.p = k.valid ? r.power : NAN;
  // Never integrate across invalid samples, reconnections or long loop stalls.
  if (k.valid && sebelumnyaValid && dtJam > 0 && dtJam <= 2.5f / 3600) {
    k.energiWh += k.p * dtJam;
    k.validSeconds += dtJam * 3600;
  }
}

static void isi(JsonObject o, const Kanal &k) {
  auto put = [&](const char *key, double x, int d) {
    if (isfinite(x)) { double s = pow(10, d); o[key] = round(x * s) / s; } else o[key] = nullptr;
  };
  put("voltage_v", k.v, 3); put("current_a", k.i, 4); put("power_w", k.p, 4); put("energy_wh", k.energiWh, 4);
  o["sensor_ok"] = k.ok;
  o["measurement_valid"] = k.valid;
  o["error"] = k.error;
  put("shunt_mv", k.shuntMv, 3);
  put("energy_valid_time_s", k.validSeconds, 3);
  if (k.snapshot) {
    JsonObject raw = o["registers"].to<JsonObject>();
    raw["bus"] = k.rawBus; raw["shunt"] = k.rawShunt;
    raw["current"] = k.rawCurrent; raw["power"] = k.rawPower;
    raw["config"] = k.rawConfig; raw["calibration"] = k.rawCalibration;
  }
}

static void kirim() {
  if (!mqtt.connected()) return;
  JsonDocument d;
  d["schema_version"] = 2;
  d["shunt_ohm"] = 0.1;
  time_t now = time(nullptr);
  // milidetik sebagai bilangan bulat (double diserialkan 9 digit -> terpotong ke 10 detik); tanpa NTP, dashboard memakai waktu terima
  if (now > 1700000000) { struct timeval tv; gettimeofday(&tv, nullptr); d["t"] = (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000; }
  isi(d["raspberry_pi"].to<JsonObject>(), kanal[0]);
  isi(d["fpga"].to<JsonObject>(), kanal[1]);
  char buf[1536];
  serializeJson(d, buf, sizeof buf);
  mqtt.publish("WEC/daya", buf);
}

void setup() {
  Serial.begin(115200);
  I2C_1.begin(21, 22);
  I2C_2.begin(18, 19);
  I2C_1.setClock(100000); I2C_2.setClock(100000);
  I2C_1.setTimeOut(50); I2C_2.setTimeOut(50);
  for (Kanal &k : kanal) mulaiSensor(k);
  wifiMulai();
  configTime(0, 0, NTP_1, NTP_2);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(2048);
  Serial.println("Time_ms,V1,I1,P1,V2,I2,P2");
}

void loop() {
  wifiJaga();
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected() && millis() - lastTry > 5000) {
    lastTry = millis();
    char id[40];
    snprintf(id, sizeof id, "wec-esp32-daya-%06lx", (unsigned long)(ESP.getEfuseMac() & 0xffffff));
    if (mqtt.connect(id, MQTT_USER, MQTT_PASS)) Serial.printf("MQTT tersambung lewat %s (IP %s)\n", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str());
  }
  mqtt.loop();
  if ((!kanal[0].ok || !kanal[1].ok) && millis() - lastSensorTry > 10000) {
    lastSensorTry = millis();
    for (Kanal &k : kanal) mulaiSensor(k);
  }
  unsigned long now = millis();
  if (now - prevMs >= INTERVAL) {
    float dtJam = prevMs ? (now - prevMs) / 3600000.0f : 0;
    prevMs = now;
    for (Kanal &k : kanal) baca(k, dtJam);
    Serial.printf("%lu,%.3f,%.4f,%.4f,%.3f,%.4f,%.4f\n", now, kanal[0].v, kanal[0].i, kanal[0].p, kanal[1].v, kanal[1].i, kanal[1].p);
    kirim();
  }
}
