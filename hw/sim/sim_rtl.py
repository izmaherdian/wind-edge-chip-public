"""
Cycle-Accurate & Bit-Accurate RTL Simulator for MAC4 Pipeline Accelerator (Pure Python)
Menyimulasikan perilaku register clock, Finite State Machine (FSM), pipeline MAC4,
dan memori on-chip persis sama dengan kode Verilog di hw/rtl/*.v.
Juga menghasilkan file rekaman gelombang VCD (waveforms/wave.vcd).
"""

import os
import sys

try:
    from vcd import VCDWriter as _PyVCDWriter
except ImportError:
    _PyVCDWriter = None

# Konversi integer ke format signed 8-bit, 16-bit, dan 32-bit biner
def to_int8(v):
    v = v & 0xFF
    return v - 256 if v >= 128 else v

def to_int16(v):
    v = v & 0xFFFF
    return v - 65536 if v >= 32768 else v

def to_int32(v):
    v = v & 0xFFFFFFFF
    return v - 4294967296 if v >= 2147483648 else v


class StandardVCDWriter:
    """Perekam file waveform Value Change Dump (.vcd) standar IEEE 1364 (mendukung pyvcd maupun fallback murni Python)."""
    def __init__(self, filepath):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        self.f = open(filepath, "w")
        self.vars = {}
        self.time = 0
        self._header_written = False
        if _PyVCDWriter is not None:
            self.writer = _PyVCDWriter(self.f, timescale='1 ns', date='Oct 19, 2026')
        else:
            self.writer = None

    def register_var(self, name, width=1):
        vtype = 'wire' if width == 1 else 'reg'
        if self.writer is not None:
            var = self.writer.register_var('top', name, vtype, size=width)
            self.vars[name] = var
            return var
        else:
            sym = chr(33 + len(self.vars))
            self.vars[name] = (sym, width, vtype)
            return sym

    def end_definitions(self):
        if self.writer is None and not self._header_written:
            self.f.write("$date\n   Oct 19, 2026\n$end\n")
            self.f.write("$timescale 1 ns $end\n")
            self.f.write("$scope module top $end\n")
            for name, (sym, width, vtype) in self.vars.items():
                self.f.write(f"$var {vtype} {width} {sym} {name} $end\n")
            self.f.write("$upscope $end\n$enddefinitions $end\n#0\n")
            self._header_written = True
            self._last_time = 0

    def log(self, name, val):
        if self.writer is not None:
            var = self.vars[name]
            self.writer.change(var, self.time, int(val))
        else:
            if not self._header_written:
                self.end_definitions()
            if self.time != self._last_time:
                self.f.write(f"#{self.time}\n")
                self._last_time = self.time
            sym, width, _ = self.vars[name]
            ival = int(val) & ((1 << width) - 1)
            if width == 1:
                self.f.write(f"{ival}{sym}\n")
            else:
                self.f.write(f"b{ival:0{width}b} {sym}\n")

    def advance_time(self, step_ns=20):
        self.time += step_ns

    def close(self):
        if self.writer is not None:
            self.writer.close()
        self.f.close()


class RTLSimulator:
    def __init__(self, rtl_dir, vcd_path=None):
        self.rtl_dir = rtl_dir
        self.vcd_path = vcd_path
        
        # Load weights and bias from .hex
        self.weights_mem = [0] * 1040
        self.bias_mem = [0] * 49
        self._load_hex()

        # Buffers
        self.in_buf = [0] * 16
        self.h1_buf = [0] * 32
        self.h2_buf = [0] * 16

        # Registers
        self.prediction_out = 0
        self.cycle_count = 0
        self.acc_out = 0
        self.state = 0
        self.neuron_cnt = 0
        self.step_cnt = 0
        self.weight_addr = 0
        self.bias_addr = 0
        self.busy = False
        self.done = False

    def _load_hex(self):
        w_file = os.path.join(self.rtl_dir, "weights.hex")
        b_file = os.path.join(self.rtl_dir, "bias.hex")
        with open(w_file, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
            for idx, l in enumerate(lines[:1040]):
                self.weights_mem[idx] = to_int8(int(l, 16))
        with open(b_file, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
            for idx, l in enumerate(lines[:49]):
                self.bias_mem[idx] = to_int32(int(l, 16))

    def set_input_features(self, features):
        assert len(features) == 16
        for i in range(16):
            self.in_buf[i] = to_int8(features[i])

    def run(self):
        S_IDLE    = 0
        S_L1_STEP = 1
        S_L1_POST = 2
        S_L2_STEP = 3
        S_L2_POST = 4
        S_L3_STEP = 5
        S_L3_POST = 6
        S_DONE    = 7

        vcd = None
        if self.vcd_path:
            vcd = StandardVCDWriter(self.vcd_path)
            vcd.register_var("clk", 1)
            vcd.register_var("rst_n", 1)
            vcd.register_var("start", 1)
            vcd.register_var("busy", 1)
            vcd.register_var("done", 1)
            vcd.register_var("state", 3)
            vcd.register_var("cycle_count", 16)
            vcd.register_var("acc_out", 32)
            vcd.register_var("prediction_out", 8)
            vcd.end_definitions()

        if vcd:
            vcd.log("clk", 0)
            vcd.log("rst_n", 0)
            vcd.log("start", 0)
            vcd.log("busy", 0)
            vcd.log("done", 0)
            vcd.log("state", 0)
            vcd.log("cycle_count", 0)
            vcd.log("acc_out", 0)
            vcd.log("prediction_out", 0)
            vcd.advance_time(20)
            vcd.log("clk", 1)
            vcd.advance_time(20)

            vcd.log("clk", 0)
            vcd.log("rst_n", 1)
            vcd.advance_time(20)
            vcd.log("clk", 1)
            vcd.advance_time(20)

            vcd.log("clk", 0)
            vcd.log("start", 1)
            vcd.advance_time(20)
            vcd.log("clk", 1)
            vcd.advance_time(20)

        self.state = S_L1_STEP
        self.busy = True
        self.done = False
        self.cycle_count = 0
        self.neuron_cnt = 0
        self.step_cnt = 0
        self.weight_addr = 0
        self.bias_addr = 0
        self.acc_out = 0

        while self.busy:
            self.cycle_count += 1
            
            if self.state in [S_L1_STEP, S_L2_STEP, S_L3_STEP]:
                if self.state == S_L1_STEP:
                    in_base = self.step_cnt * 4
                    in0, in1, in2, in3 = self.in_buf[in_base:in_base+4]
                elif self.state == S_L2_STEP:
                    in_base = self.step_cnt * 4
                    in0, in1, in2, in3 = self.h1_buf[in_base:in_base+4]
                else:
                    in_base = self.step_cnt * 4
                    in0, in1, in2, in3 = self.h2_buf[in_base:in_base+4]

                w0 = self.weights_mem[self.weight_addr + 0]
                w1 = self.weights_mem[self.weight_addr + 1]
                w2 = self.weights_mem[self.weight_addr + 2]
                w3 = self.weights_mem[self.weight_addr + 3]

                prod0 = to_int16(in0 * w0)
                prod1 = to_int16(in1 * w1)
                prod2 = to_int16(in2 * w2)
                prod3 = to_int16(in3 * w3)
                sum_step = prod0 + prod1 + prod2 + prod3

                if self.step_cnt == 0:
                    self.acc_out = to_int32(sum_step)
                else:
                    self.acc_out = to_int32(self.acc_out + sum_step)

                self.weight_addr += 4

                if self.state == S_L1_STEP:
                    if self.step_cnt == 3:
                        self.step_cnt = 0
                        self.state = S_L1_POST
                    else:
                        self.step_cnt += 1
                elif self.state == S_L2_STEP:
                    if self.step_cnt == 7:
                        self.step_cnt = 0
                        self.state = S_L2_POST
                    else:
                        self.step_cnt += 1
                elif self.state == S_L3_STEP:
                    if self.step_cnt == 3:
                        self.step_cnt = 0
                        self.state = S_L3_POST
                    else:
                        self.step_cnt += 1

            elif self.state in [S_L1_POST, S_L2_POST, S_L3_POST]:
                cur_bias = self.bias_mem[self.bias_addr]
                biased = self.acc_out + cur_bias
                scaled = (biased * 32) >> 8
                act_out = 0 if scaled < 0 else min(scaled, 127)

                if self.state == S_L1_POST:
                    self.h1_buf[self.neuron_cnt] = act_out
                    self.bias_addr += 1
                    if self.neuron_cnt == 31:
                        self.neuron_cnt = 0
                        self.state = S_L2_STEP
                    else:
                        self.neuron_cnt += 1
                        self.state = S_L1_STEP

                elif self.state == S_L2_POST:
                    self.h2_buf[self.neuron_cnt] = act_out
                    self.bias_addr += 1
                    if self.neuron_cnt == 15:
                        self.neuron_cnt = 0
                        self.state = S_L3_STEP
                    else:
                        self.neuron_cnt += 1
                        self.state = S_L2_STEP

                elif self.state == S_L3_POST:
                    self.prediction_out = act_out
                    self.bias_addr += 1
                    self.state = S_DONE

            elif self.state == S_DONE:
                self.done = True
                self.busy = False

            if vcd:
                vcd.log("clk", 1)
                vcd.log("rst_n", 1)
                vcd.log("start", 0)
                vcd.log("busy", self.busy)
                vcd.log("done", self.done)
                vcd.log("state", self.state)
                vcd.log("cycle_count", self.cycle_count)
                vcd.log("acc_out", self.acc_out)
                vcd.log("prediction_out", self.prediction_out)
                vcd.advance_time(20)
                vcd.log("clk", 0)
                vcd.advance_time(20)

        if vcd:
            vcd.close()

        return self.prediction_out, self.cycle_count


def run_full_pre_silicon_test():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    rtl_dir = os.path.join(project_root, "hw", "rtl")
    sim_dir = os.path.join(project_root, "hw", "sim")
    ml_dir = os.path.join(project_root, "ml")
    vcd_file = os.path.join(sim_dir, "waveforms", "wave.vcd")

    print("=" * 65)
    print("  SIMULASI PRE-SILICON AKSELERATOR NEURAL NETWORK FPGA (RTL)")
    print("=" * 65)

    sys.path.append(ml_dir)
    from golden_model import GoldenModelINT8
    gm = GoldenModelINT8()
    
    w_path = os.path.join(rtl_dir, "weights.hex")
    b_path = os.path.join(rtl_dir, "bias.hex")
    gm.export_hex(w_path, b_path)

    test_samples = [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, -1, 0, 3, -2, 1, 0, -1, 2, 1, 0, -1, 1, 0, 2],
        [12, -8, 25, 4, 30, -15, 0, 18, -22, 10, 5, -3, 8, 14, -1, 9]
    ]

    all_passed = True
    for idx, sample in enumerate(test_samples):
        expected_pred, exp_h1, exp_h2 = gm.forward(sample)
        
        sim = RTLSimulator(rtl_dir, vcd_path=vcd_file if idx == 0 else None)
        sim.set_input_features(sample)
        actual_pred, cycles = sim.run()

        match = (expected_pred == actual_pred)
        status = "[LULUS / MATCH]" if match else "[GAGAL / MISMATCH]"
        if not match:
            all_passed = False

        print(f"\n--- Pengujian Sampel #{idx+1} ---")
        print(f" Masukan Sensor (16 Fitur) : {sample}")
        print(f" Target Golden Model (INT8): {expected_pred}")
        print(f" Keluaran Akselerator FPGA : {actual_pred}")
        print(f" Latensi Komputasi         : {cycles} siklus clock ({cycles * 1000 / 27:.1f} ns @ 27 MHz)")
        print(f" Status Verifikasi         : {status}")

    print("\n" + "=" * 65)
    if all_passed:
        print("  KESIMPULAN: 100% IDENTIK BIT-PER-BIT DENGAN GOLDEN MODEL!")
        print(f"  File waveform tersimpan di: {vcd_file}")
        print("=" * 65)
    else:
        print("  KESIMPULAN: TERDAPAT KETIDAKSESUAIAN!")
        print("=" * 65)

    return all_passed

if __name__ == "__main__":
    success = run_full_pre_silicon_test()
    sys.exit(0 if success else 1)
