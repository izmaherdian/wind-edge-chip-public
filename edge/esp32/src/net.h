// WiFi, MQTT, NTP, prakiraan Open-Meteo, dan antrean offline (LittleFS).
// Kalau MQTT putus, ringkasan per menit disimpan ke flash lalu dikirim ulang saat tersambung
// (Raspi tidak punya penyangga lokal: data hilang setiap internet mati, edge/ta/raspi/README.md).
#pragma once
#include <stdint.h>

#include "wec_core.h"

void netBegin();
void netLoop();                       // panggil sesering mungkin
bool mqttUp();
bool timeValid();                     // jam sudah tersinkron NTP
// publish langsung; kalau gagal dan queueIfDown, simpan ke antrean
bool publish(const char *topic, const char *payload, bool retain = false, bool queueIfDown = false);
uint32_t queueBytes();
// Open-Meteo: ambil ulang tiap OM_EVERY_MS; true bila data baru masuk
bool omRefresh(wec::OmForecast &om);
