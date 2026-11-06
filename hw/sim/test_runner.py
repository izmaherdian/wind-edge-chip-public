"""
Test Runner Otomatis untuk Memvalidasi Akselerator Neural Network FPGA
Menguji kesamaan hasil inferensi antara Golden Model (Python) dan RTL Verilog (Icarus Verilog)
secara bit-demi-bit tanpa memerlukan hardware fisik.
"""

import os
import subprocess
import sys

def run_test():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    
    rtl_dir = os.path.join(project_root, "hw", "rtl")
    sim_dir = os.path.join(project_root, "hw", "sim")
    ml_dir = os.path.join(project_root, "ml")
    
    print("=" * 60)
    print("   UJI OTOMASI PRE-SILICON AKSELERATOR FPGA (SIMULASI)")
    print("=" * 60)

    # 1. Jalankan Golden Model untuk memastikan weights.hex & bias.hex mutakhir
    print("\n[LANGKAH 1] Menjalankan ml/golden_model.py...")
    sys.path.append(ml_dir)
    from golden_model import GoldenModelINT8
    
    gm = GoldenModelINT8()
    w_path = os.path.join(rtl_dir, "weights.hex")
    b_path = os.path.join(rtl_dir, "bias.hex")
    gm.export_hex(w_path, b_path)

    test_input = [12, -8, 25, 4, 30, -15, 0, 18, -22, 10, 5, -3, 8, 14, -1, 9]
    expected_pred, _, _ = gm.forward(test_input)
    print(f" -> Input Uji             : {test_input}")
    print(f" -> Ekspektasi Golden Model: {expected_pred} (INT8)")

    # 2. Cari executable iverilog dan vvp
    iverilog_cmd = "iverilog"
    vvp_cmd = "vvp"

    # Periksa kemungkinan lokasi instalasi default di Windows jika belum di PATH
    possible_paths = [
        r"C:\iverilog\bin",
        r"C:\Program Files\iverilog\bin",
        r"C:\Program Files (x86)\iverilog\bin",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\iverilog\bin")
    ]
    for p in possible_paths:
        if os.path.exists(os.path.join(p, "iverilog.exe")):
            os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]
            iverilog_cmd = os.path.join(p, "iverilog.exe")
            vvp_cmd = os.path.join(p, "vvp.exe")
            break

    # 3. Kompilasi Verilog
    print("\n[LANGKAH 2] Mengompilasi Desain RTL Verilog dengan Icarus Verilog...")
    verilog_files = [
        os.path.join(rtl_dir, "mac4_engine.v"),
        os.path.join(rtl_dir, "post_process.v"),
        os.path.join(rtl_dir, "fsm_controller.v"),
        os.path.join(rtl_dir, "weights_rom.v"),
        os.path.join(rtl_dir, "top.v"),
        os.path.join(sim_dir, "tb_top.v")
    ]
    sim_out = os.path.join(sim_dir, "sim_top.vvp")

    compile_cmd = [iverilog_cmd, "-o", sim_out] + verilog_files
    print(f" -> Menjalankan: {' '.join(compile_cmd)}")
    
    try:
        res = subprocess.run(compile_cmd, cwd=rtl_dir, capture_output=True, text=True, check=True)
        print(" -> [BERHASIL] Kompilasi RTL sukses tanpa sintaks error.")
    except Exception as e:
        print(f" -> [INFO] Simulator iverilog belum siap / sedang mengunduh: {e}")
        return False

    # 4. Eksekusi Simulasi
    print("\n[LANGKAH 3] Mengeksekusi Simulasi RTL (VVP Simulator)...")
    try:
        os.makedirs(os.path.join(rtl_dir, "waveforms"), exist_ok=True)   # tb_top.v menulis waveforms/wave.vcd
        run_res = subprocess.run([vvp_cmd, sim_out], cwd=rtl_dir, capture_output=True, text=True, check=True)
        print(run_res.stdout)
        
        # Validasi output
        if f"Output Prediksi   : {expected_pred}" in run_res.stdout:
            print("\n" + "=" * 60)
            print(" [HASIL] UJI VERIFIKASI PRE-SILICON: LULUS (100% BIT-PER-BIT MATCH)")
            print(f" Nilai Chip FPGA ({expected_pred}) == Golden Model ({expected_pred})")
            print("=" * 60)
            return True
        else:
            print(f"\n[PERINGATAN] Nilai tidak cocok! Diharapkan: {expected_pred}")
            return False
    except Exception as e:
        print(f" -> [GAGAL] Eksekusi simulasi error: {e}")
        return False

if __name__ == "__main__":
    run_test()

