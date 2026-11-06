#include "ina219_reading.h"
#include <cassert>
#include <cstring>

int main() {
  const uint16_t bus = (1275 << 3) | 2;  // 5.100 V, ready
  auto r = decodeIna219(bus, 5000, 5000, 1275); // 50 mV, 0.5 A, 2.55 W
  assert(!*r.error && std::fabs(r.voltage - 5.1f) < 0.001f);
  assert(std::fabs(r.current - 0.5f) < 0.0001f);
  assert(!std::strcmp(decodeIna219(bus | 1, 5000, 5000, 1275).error, "math_overflow"));
  assert(!std::strcmp(decodeIna219(bus & ~2, 5000, 5000, 1275).error, "conversion_not_ready"));
  assert(!std::strcmp(decodeIna219((250 << 3) | 2, 5000, 5000, 1275).error, "voltage_outside_5v_rail"));
  assert(!std::strcmp(decodeIna219(bus, -5000, -5000, 1275).error, "reverse_current"));
  assert(!std::strcmp(decodeIna219(bus, 5000, 5000, 25).error, "power_mismatch"));
  assert(!std::strcmp(decodeIna219(bus, 1000, 5000, 1275).error, "current_shunt_mismatch"));
  assert(!*decodeIna219(bus, 0, 0, 0).error);
}
