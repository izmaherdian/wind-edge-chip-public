#include "net.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <time.h>

#include "config.h"

static WiFiClient wifiClient;
static PubSubClient mqtt(wifiClient);
static uint32_t lastTry = 0, lastOm = 0;
static bool omEver = false, fsOk = false;
static size_t replayPos = 0;

void netBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  configTime(0, 0, NTP_1, NTP_2);                     // UTC; jam WIB dihitung di wec_core
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(1024);
  mqtt.setKeepAlive(30);
  fsOk = LittleFS.begin(true);
}

bool mqttUp() { return mqtt.connected(); }
bool timeValid() { return time(nullptr) > 1700000000; }

uint32_t queueBytes() {
  if (!fsOk || !LittleFS.exists(QUEUE_FILE)) return 0;
  File f = LittleFS.open(QUEUE_FILE, "r");
  uint32_t n = f.size();
  f.close();
  return n;
}

static void enqueue(const char *topic, const char *payload) {
  if (!fsOk || queueBytes() > QUEUE_MAX_BYTES) return;   // penuh: data terbaru tidak disimpan
  File f = LittleFS.open(QUEUE_FILE, "a");
  f.printf("%s\t%s\n", topic, payload);
  f.close();
}

// kirim ulang antrean sedikit demi sedikit (maks 20 baris per panggilan) supaya loop sensor tidak tertahan
static void replay() {
  if (!fsOk || !LittleFS.exists(QUEUE_FILE)) return;
  File f = LittleFS.open(QUEUE_FILE, "r");
  f.seek(replayPos);
  for (int k = 0; k < 20 && f.available(); k++) {
    String line = f.readStringUntil('\n');
    int tab = line.indexOf('\t');
    if (tab > 0 && !mqtt.publish(line.substring(0, tab).c_str(), line.substring(tab + 1).c_str())) break;
    replayPos = f.position();
  }
  bool done = !f.available();
  f.close();
  if (done) { LittleFS.remove(QUEUE_FILE); replayPos = 0; }
}

void netLoop() {
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected() && millis() - lastTry > 5000) {
    lastTry = millis();
    char id[32];
    snprintf(id, sizeof id, "wec-esp32-%06lx", (unsigned long)(ESP.getEfuseMac() & 0xffffff));
    mqtt.connect(id, MQTT_USER, MQTT_PASS);
  }
  if (mqtt.connected()) { mqtt.loop(); replay(); }
}

bool publish(const char *topic, const char *payload, bool retain, bool queueIfDown) {
  if (mqtt.connected() && mqtt.publish(topic, payload, retain)) return true;
  if (queueIfDown) enqueue(topic, payload);
  return false;
}

bool omRefresh(wec::OmForecast &om) {
  if (WiFi.status() != WL_CONNECTED || (omEver && millis() - lastOm < OM_EVERY_MS) || (!omEver && millis() - lastOm < 60000 && lastOm)) return false;
  lastOm = millis();
  HTTPClient http;
  http.setTimeout(8000);
  if (!http.begin(wifiClient, OM_URL)) return false;
  int code = http.GET();
  if (code != 200) { http.end(); return false; }
  JsonDocument filter;
  filter["hourly"]["time"] = true;
  filter["hourly"]["wind_speed_10m"] = true;
  filter["hourly"]["surface_pressure"] = true;
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) return false;
  JsonArray t = doc["hourly"]["time"], w = doc["hourly"]["wind_speed_10m"], p = doc["hourly"]["surface_pressure"];
  int n = 0;
  for (size_t k = 0; k < t.size() && n < wec::OmForecast::CAP; k++) {
    om.t[n] = t[k].as<long long>();
    om.wind[n] = w[k].isNull() ? NAN : w[k].as<double>();
    om.pres[n] = p[k].isNull() ? NAN : p[k].as<double>();
    n++;
  }
  if (n < 2) return false;
  om.n = n;
  omEver = true;
  return true;
}
