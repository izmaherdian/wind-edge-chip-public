// Native INT8 inference using the exact exported FPGA model.
// Input: execute(0/1) x0..x15. Output: out_q(-1 for baseline) core_ns.
#include <chrono>
#include <iostream>
#include "mlp_int8.h"

int main() {
  int execute;
  while (std::cin >> execute) {
    int8_t x[16];
    for (int k = 0; k < 16; k++) {
      int v;
      if (!(std::cin >> v) || v < -128 || v > 127) return 2;
      x[k] = int8_t(v);
    }
    if (execute != 0 && execute != 1) return 2;
    int out = -1;
    const auto start = std::chrono::steady_clock::now();
    if (execute) out = mlp_predict(x);
    const auto end = std::chrono::steady_clock::now();
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    std::cout << out << ' ' << (execute ? ns : 0) << std::endl;
  }
}
