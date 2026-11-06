// WiFi untuk firmware khusus: eduroam (WPA2-Enterprise PEAP) bila WIFI_EAP_USER ada di secrets.h,
// bergantian dengan WiFi biasa (WIFI_SSID) tiap 30 detik sampai salah satu tersambung.
// Pemakaian: wifiMulai() di setup(), wifiJaga() di loop().
#pragma once
#include <WiFi.h>

#include "config.h"

static uint32_t wifiSejak = 0;
static bool wifiCobaEap = true;

static void wifiSambung() {
  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
#ifdef WIFI_EAP_USER
  if (wifiCobaEap) {
    Serial.printf("WiFi: coba %s (WPA2-Enterprise PEAP)\n", WIFI_EAP_SSID);
    WiFi.begin(WIFI_EAP_SSID, WPA2_AUTH_PEAP, WIFI_EAP_USER, WIFI_EAP_USER, WIFI_EAP_PASS);
  } else
#endif
  {
    Serial.printf("WiFi: coba %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
  wifiSejak = millis();
}

static void wifiMulai() { WiFi.setAutoReconnect(true); wifiSambung(); }

static void wifiJaga() {
  if (WiFi.status() == WL_CONNECTED) { wifiSejak = millis(); return; }
  if (millis() - wifiSejak > 30000) {
#ifdef WIFI_EAP_USER
    wifiCobaEap = !wifiCobaEap;   // gagal 30 detik: ganti jaringan
#endif
    wifiSambung();
  }
}

