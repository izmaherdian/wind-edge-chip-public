// Konfigurasi edge node. Pin untuk ESP32-S3-DevKitC-1 (papan tim) dan ESP32 DevKit klasik.
// WiFi ada di include/secrets.h (tidak masuk git; salin dari secrets.example.h).
#pragma once
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"   // klon baru: tetap bisa dikompilasi, WiFi belum terisi
#endif

// ---------- MQTT (broker yang sama dengan Raspi Genis) ----------
#define MQTT_HOST "citaitb.com"
#define MQTT_PORT 1883
#ifndef MQTT_USER
#define MQTT_USER "cita"
#endif
#ifndef MQTT_PASS
#define MQTT_PASS ""   // isi di include/secrets.h
#endif
// Data sensor mentah, format sama dengan Raspi (TurbinAngin/voltage, ..., ML_Status di akhir batch).
// Selama Raspi masih jalan, pakai awalan lain supaya tidak tercampur; ganti ke "TurbinAngin" saat ESP32 menggantikan Raspi.
#define TOPIC_DATA "TurbinAnginESP"
// Hasil ML per menit: <TOPIC_WEC>/prediksi|status|baterai|menit|fpga (JSON, skema sama dengan mesin Node-RED)
#define TOPIC_WEC "WEC/esp32"

// ---------- waktu ----------
#define NTP_1 "pool.ntp.org"
#define NTP_2 "time.google.com"
#define SAMPLE_MS 3000          // interval baca sensor (sama dengan Raspi)

// Pin: ESP32-S3 N16R8 tidak boleh memakai GPIO26-37 (flash + PSRAM oktal) dan 19/20 (USB).
#if defined(CONFIG_IDF_TARGET_ESP32S3)
// ---------- RS-485 (PZEM-017 + stasiun cuaca, satu bus, UART2) ----------
#define RS485_RX 16
#define RS485_TX 17
#define RS485_DE 4              // DE+RE modul MAX485; -1 bila modul otomatis
#define PZEM_ADDR 0x01          // 9600 8N2, input register 0..5
#define STATION_ADDR 0x02       // 4800 8N1, holding register 0x01F4..
// ---------- anemometer optik (pengganti Arduino; 18 celah, r = 0,08 m, faktor 2,3) ----------
#define ANEMO_PIN 15
#define ANEMO_SLOTS 18
#define ANEMO_RADIUS_M 0.08f
#define ANEMO_CALIB 2.3f

// ---------- FPGA Tang Nano 4K (UART1, 115200 8N1) ----------
#define FPGA_RX 5               // <- pin 46 FPGA (tx_pin)
#define FPGA_TX 6               // -> pin 44 FPGA (rx_pin)
#define FPGA_RST 7              // -> pin 14 FPGA (rst_n, aktif rendah); -1 bila tidak disambung
#define FPGA_BAUD 921600        // top_soc.v BAUDRATE (feature/fpga 21 Okt)
#define FPGA_TIMEOUT_MS 20      // 19+7 byte = 0,28 ms di 921600; hitung 309 siklus = 11 us
#define FPGA_DUAL_MODEL 0       // 1 setelah RTL dua model (docs/usulan-rtl-dua-model.md) diterapkan

// ---------- relai (fitur 3) ----------
#define RELAY_PLN 11            // HIGH = beban dipindah ke PLN
#define RELAY_DUMP 12           // HIGH = beban buang (dump load) aktif
#define RELAY_ACTIVE_HIGH 1
#define LED_PIN -1              // DevKitC-1 memakai LED RGB WS2812 (GPIO48), tidak dipakai

#else  // ESP32 klasik (esp32dev)
// ---------- RS-485 (PZEM-017 + stasiun cuaca, satu bus, UART2) ----------
#define RS485_RX 16
#define RS485_TX 17
#define RS485_DE 4              // DE+RE modul MAX485; -1 bila modul otomatis
#define PZEM_ADDR 0x01          // 9600 8N2, input register 0..5
#define STATION_ADDR 0x02       // 4800 8N1, holding register 0x01F4..
// ---------- anemometer optik (pengganti Arduino; 18 celah, r = 0,08 m, faktor 2,3) ----------
#define ANEMO_PIN 33
#define ANEMO_SLOTS 18
#define ANEMO_RADIUS_M 0.08f
#define ANEMO_CALIB 2.3f

// ---------- FPGA Tang Nano 4K (UART1, 115200 8N1) ----------
#define FPGA_RX 26              // <- pin 46 FPGA (tx_pin)
#define FPGA_TX 27              // -> pin 44 FPGA (rx_pin)
#define FPGA_RST 25             // -> pin 14 FPGA (rst_n, aktif rendah); -1 bila tidak disambung
#define FPGA_BAUD 921600        // top_soc.v BAUDRATE (feature/fpga 21 Okt)
#define FPGA_TIMEOUT_MS 20      // 19+7 byte = 0,28 ms di 921600; hitung 309 siklus = 11 us
#define FPGA_DUAL_MODEL 0       // 1 setelah RTL dua model (docs/usulan-rtl-dua-model.md) diterapkan

// ---------- relai (fitur 3) ----------
#define RELAY_PLN 18            // HIGH = beban dipindah ke PLN
#define RELAY_DUMP 19           // HIGH = beban buang (dump load) aktif
#define RELAY_ACTIVE_HIGH 1
#define LED_PIN 2

#endif

// ---------- Open-Meteo (koordinat sama dengan training, ml/common/fetch_openmeteo.py) ----------
#define OM_URL "http://api.open-meteo.com/v1/forecast?latitude=-6.891&longitude=107.610" \
  "&hourly=wind_speed_10m,surface_pressure&wind_speed_unit=ms&timezone=GMT&timeformat=unixtime&past_days=1&forecast_days=3"
#define OM_EVERY_MS (30UL * 60 * 1000)

// ---------- antrean offline (LittleFS) ----------
#define QUEUE_FILE "/antre.txt"
#define QUEUE_MAX_BYTES (600UL * 1024)   // ±2 hari ringkasan per menit
