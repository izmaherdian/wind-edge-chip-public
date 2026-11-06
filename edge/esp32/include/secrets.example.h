// Salin ke include/secrets.h lalu isi. secrets.h tidak masuk git.
#pragma once
// WiFi biasa (WPA2-Personal), juga cadangan bila eduroam gagal
#define WIFI_SSID "nama-wifi"
#define WIFI_PASS "kata-sandi-wifi"
// Opsional: eduroam (WPA2-Enterprise, PEAP + MSCHAPv2) dengan akun kampus sendiri
// #define WIFI_EAP_SSID "eduroam"
// #define WIFI_EAP_USER "nama@itb.ac.id"
// #define WIFI_EAP_PASS "sandi-akun"
// Kredensial broker MQTT
#define MQTT_PASS "sandi-mqtt"
