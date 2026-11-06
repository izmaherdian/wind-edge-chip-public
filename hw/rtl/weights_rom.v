// ============================================================================
// Module: weights_rom.v
// Deskripsi: Memori ROM Bobot Model (260 Word x 32-bit)
//            Setiap word memuat 4 bobot INT8 paralel:
//            - dout[7:0]   = w0
//            - dout[15:8]  = w1
//            - dout[23:16] = w2
//            - dout[31:24] = w3
//            Didesain agar otomatis dipetakan ke 1 blok Gowin Hardware BSRAM (SPX9)
//            pada Sipeed Tang Nano 4K (GW1NSR-LV4C).
// ============================================================================

`timescale 1ns / 1ps

module weights_rom (
    input  wire        clk,
    input  wire        ce,
    input  wire [8:0]  addr,
    output reg  [31:0] dout
);

    reg [31:0] mem [0:259];

    initial begin
        $readmemh("weights32.hex", mem);
    end

    always @(posedge clk) begin
        if (ce)
            dout <= mem[addr];
    end

endmodule
