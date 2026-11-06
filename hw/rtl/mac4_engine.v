// ============================================================================
// Module: mac4_engine.v
// Deskripsi: Unit Komputasi Paralel MAC4 (4 Multiplier + Adder Tree + Accumulator)
//            Mengeksekusi 4 operasi perkalian bertanda 8-bit secara simultan dan
//            menambahkannya ke akumulator bertanda 32-bit.
// ============================================================================

`timescale 1ns / 1ps

module mac4_engine (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clr_acc,     // Membersihkan akumulator (reset ke 0 untuk neuron baru)
    input  wire        en_acc,      // Mengaktifkan penambahan parsial ke akumulator
    
    // 4 Pasang Data Masukan (INT8 Signed)
    input  wire signed [7:0] in0,
    input  wire signed [7:0] in1,
    input  wire signed [7:0] in2,
    input  wire signed [7:0] in3,
    
    // 4 Pasang Bobot Model (INT8 Signed)
    input  wire signed [7:0] w0,
    input  wire signed [7:0] w1,
    input  wire signed [7:0] w2,
    input  wire signed [7:0] w3,
    
    // Output Akumulasi 32-bit Bertanda
    output reg  signed [31:0] acc_out
);

    // --- Tahap 1: 4 Unit Perkalian Simultan (INT8 * INT8 = INT16) ---
    wire signed [15:0] prod0 = in0 * w0;
    wire signed [15:0] prod1 = in1 * w1;
    wire signed [15:0] prod2 = in2 * w2;
    wire signed [15:0] prod3 = in3 * w3;

    // --- Tahap 2: Adder Tree 4:1 (Penjumlahan Parsial 4 Jalur) ---
    wire signed [16:0] sum_pair0 = prod0 + prod1;
    wire signed [16:0] sum_pair1 = prod2 + prod3;
    wire signed [17:0] sum_step  = sum_pair0 + sum_pair1;

    // --- Tahap 3: Akumulasi Parsial ke Register 32-bit ---
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_out <= 32'sd0;
        end else if (clr_acc) begin
            // Jika ada akumulasi sekaligus clear (langkah pertama neuron baru)
            if (en_acc)
                acc_out <= {{14{sum_step[17]}}, sum_step};
            else
                acc_out <= 32'sd0;
        end else if (en_acc) begin
            acc_out <= acc_out + {{14{sum_step[17]}}, sum_step};
        end
    end

endmodule

