// ============================================================================
// Module: post_process.v
// Deskripsi: Unit Pasca-Proses Re-kuantisasi Fixed-Point & Aktivasi ReLU
//            - Menambahkan Bias 32-bit ke hasil akumulasi MAC.
//            - Mengalikan faktor skala integer M (multiplier).
//            - Melakukan pergeseran aritmatika bit ke kanan S (shift).
//            - Menerapkan fungsi aktivasi ReLU (nilai negatif dipaksa 0).
//            - Membatasi keluaran ke rentang INT8 positif [0, 127].
// ============================================================================

`timescale 1ns / 1ps

module post_process (
    input  wire signed [31:0] acc_in,       // Nilai akumulator dari MAC4
    input  wire signed [31:0] bias_in,      // Bias INT32 dari memori
    input  wire        [15:0] mult_scale,   // Faktor skala integer M (default: 180)
    input  wire        [4:0]  shift_scale,  // Pergeseran bit kanan S (default: 8)
    
    output reg  signed [7:0]  act_out       // Nilai aktivasi akhir INT8 [0, 127]
);

    // 1. Tambah Bias
    wire signed [32:0] biased = acc_in + bias_in;

    // 2. Skala Fixed-Point: (biased * M)
    wire signed [48:0] scaled_mult = biased * $signed({1'b0, mult_scale});

    // 3. Arithmetic Right Shift (>>>)
    wire signed [48:0] shifted = scaled_mult >>> shift_scale;

    // 4. ReLU & Clamping ke [0, 127]
    always @(*) begin
        if (shifted < 0) begin
            act_out = 8'sd0;           // ReLU: Nilai negatif dipaksa 0
        end else if (shifted > 127) begin
            act_out = 8'sd127;         // Saturation: Batas atas positif INT8
        end else begin
            act_out = shifted[7:0];    // Nilai valid
        end
    end

endmodule

