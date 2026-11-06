// Compile using the same ArduinoJson headers as env esp32s3_bridge.
#include <ArduinoJson.h>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
  const int64_t first = 1792573380000LL;
  unsigned rounded = 0;
  for (int n = 0; n < 1440; n++) {
    const int64_t timestamp = first + int64_t(n) * 60000;
    JsonDocument before, after, decoded;
    before["t"] = double(timestamp);
    after["t"] = timestamp;
    char packet[100];
    serializeJson(before, packet, sizeof packet);
    assert(!deserializeJson(decoded, packet));
    rounded += decoded["t"].as<int64_t>() != timestamp;
    serializeJson(after, packet, sizeof packet);
    assert(!deserializeJson(decoded, packet));
    assert(decoded["t"].as<int64_t>() == timestamp);
  }
  assert(rounded > 0); // reproduce the original failure before checking the fix
  std::cout << "Legacy rounded " << rounded << "/1440; int64 exact 1440/1440.\n";
}
