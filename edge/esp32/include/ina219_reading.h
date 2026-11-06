#pragma once
#include <cmath>
#include <cstdint>

// INA219, Rshunt = 0.1 ohm (R100), calibration = 4096:
// bus LSB 4 mV; shunt LSB 10 uV; current LSB 100 uA; power LSB 2 mW.
struct Ina219Reading {
  float voltage, shuntMv, current, power;
  const char *error;
};

inline Ina219Reading decodeIna219(uint16_t bus, int16_t shunt,
                                 int16_t current, uint16_t power) {
  Ina219Reading r{(bus >> 3) * 0.004f, shunt * 0.01f,
                 current * 0.0001f, power * 0.002f, ""};
  if (!(bus & 2)) r.error = "conversion_not_ready";
  else if (bus & 1) r.error = "math_overflow";
  // Screening for these two USB 5 V rails, not a Pi voltage specification.
  else if (r.voltage < 4.0f || r.voltage > 6.0f) r.error = "voltage_outside_5v_rail";
  else if (r.current < -0.01f) r.error = "reverse_current";
  else if (std::fabs(r.shuntMv) >= 320 || r.current >= 3.2f) r.error = "shunt_range";
  else if (std::fabs(r.current - r.shuntMv / 100.0f) > 0.002f) r.error = "current_shunt_mismatch";
  else if (std::fabs(r.power - r.voltage * r.current) > 0.03f)
    r.error = "power_mismatch";
  return r;
}
