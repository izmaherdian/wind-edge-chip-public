// ESP32-S3 sebagai jembatan live (env esp32s3_bridge), selama sensor RS-485 belum dirakit:
//   MQTT WEC/prediksi (mesin ML Node-RED, tiap menit; berisi xq = 16 fitur INT8 dan out_q dari CPU)
//   -> paket 19 B ke Tang Nano 4K lewat UART1 -> balasan 7 B -> MQTT WEC/fpga (sumber "tang-nano-4k")
// WiFi: eduroam (WPA2-Enterprise) bila diisi di secrets.h, bergantian dengan hotspot (include/wifi_mulai.h).
// Dashboard /dashboard/hackathon menampilkannya di baris "Chip". Pengganti edge/bridge/fpga_bridge.py di laptop.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "config.h"
#include "wifi_mulai.h"
#include "fpga_link.h"
#include "wec_core.h"

static WiFiClient net;
static PubSubClient mqtt(net);
static int64_t lastT = 0;
static uint32_t lastTry = 0, nJawab = 0, nCocok = 0;
static uint32_t benchmarkUntil = 0;

static void onMessage(char *topic, uint8_t *payload, unsigned int len) {
  JsonDocument d;
  if (deserializeJson(d, payload, len)) return;
  JsonArray xa = d["xq"].as<JsonArray>();
  const bool benchmark = strcmp(topic, "WEC/benchmark/request") == 0;
  const char *phase = d["phase"] | "";
  if (benchmark) {
    if (!d["run_id"].is<const char *>() || !d["seq"].is<int>() ||
        (strcmp(phase, "baseline") != 0 && strcmp(phase, "active") != 0)) return;
    // Suppress normal minute inference during the benchmark; sensor acquisition
    // on the Pi continues. A short deadline releases automatically on disconnect.
    benchmarkUntil = millis() + 5000;
  } else if ((int32_t)(millis() - benchmarkUntil) < 0) return;
  // Preserve the exact sample ID (UTC milliseconds). Floating-point JSON
  // serialization can round large timestamps, breaking request/reply matching.
  int64_t t = d["t"].as<int64_t>();
  if (xa.size() != 16 || t <= 0 || (!benchmark && t == lastT)) return;
  if (!benchmark) lastT = t;
  int8_t xq[16];
  for (int j = 0; j < 16; j++) {
    if (!xa[j].is<int>() || xa[j].as<int>() < -128 || xa[j].as<int>() > 127) return;
    xq[j] = (int8_t)xa[j].as<int>();
  }
  if (benchmark) {
    const bool execute = strcmp(phase, "active") == 0;
    FpgaResult result;
    if (execute) result = fpgaInfer(wec::MODEL_FORECAST, xq);
    JsonDocument out;
    out["t"] = t; out["run_id"] = d["run_id"]; out["seq"] = d["seq"];
    out["phase"] = phase; out["executed"] = execute;
    out["ok"] = !execute || result.ok;
    out["source"] = "esp32s3+fpga"; out["xq"] = d["xq"];
    if (execute && result.ok) {
      out["out_q"] = result.out; out["uart_us"] = result.us; out["cycles"] = result.cycles;
    } else { out["out_q"] = nullptr; out["uart_us"] = nullptr; out["cycles"] = nullptr; }
    char buffer[640]; serializeJson(out, buffer, sizeof buffer);
    mqtt.publish("WEC/benchmark/fpga", buffer, false);
    return;
  }
  int cpu = d["out_q"].isNull() ? (int)wec::forward(wec::MODEL_FORECAST, xq) : d["out_q"].as<int>();
  FpgaResult r = fpgaInfer(wec::MODEL_FORECAST, xq);
  if (!r.ok) { Serial.println("FPGA tidak menjawab dengan paket valid"); return; }
  nJawab++; if (r.out == cpu) nCocok++;
  JsonDocument o;
  o["t"] = t; o["out_q_fpga"] = r.out; o["out_q_cpu"] = cpu; o["cocok"] = r.out == cpu;
  o["cycles"] = r.cycles; o["us"] = r.us; o["watt"] = round(r.out * wec::wattPerLsb(wec::MODEL_FORECAST) * 100) / 100;
  o["sumber"] = "tang-nano-4k"; o["port"] = "ESP32-S3 UART1";
  char buf[320];
  serializeJson(o, buf, sizeof buf);
  mqtt.publish("WEC/fpga", buf, true);
  Serial.printf("chip %d (cpu %d) %s | %u siklus | %u us | %lu/%lu cocok\n", r.out, cpu, r.out == cpu ? "SAMA" : "BEDA",
                r.cycles, r.us, (unsigned long)nCocok, (unsigned long)nJawab);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  fpgaBegin();
  wifiMulai();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(1024);
  mqtt.setCallback(onMessage);
  Serial.printf("\nJembatan Wind Edge Chip: WiFi -> MQTT %s -> FPGA %d bps\n", MQTT_HOST, FPGA_BAUD);
}

void loop() {
  wifiJaga();
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastTry > 5000) { lastTry = millis(); Serial.printf("menunggu WiFi (status %d)\n", WiFi.status()); }
  } else if (!mqtt.connected()) {
    if (millis() - lastTry > 5000) {
      lastTry = millis();
      char id[40];
      snprintf(id, sizeof id, "wec-esp32-bridge-%06lx", (unsigned long)(ESP.getEfuseMac() & 0xffffff));
      if (mqtt.connect(id, MQTT_USER, MQTT_PASS)) {
        mqtt.subscribe("WEC/prediksi");
        mqtt.subscribe("WEC/benchmark/request");
        Serial.printf("MQTT tersambung lewat %s (IP %s), menunggu WEC/prediksi\n", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str());
      } else Serial.printf("MQTT gagal (%d)\n", mqtt.state());
    }
  } else mqtt.loop();
}
