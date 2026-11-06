// ============================================================================
// Module: uart_tx.v
// Deskripsi: Pemancar Serial UART (8-N-1)
//            Mengirimkan data 8-bit secara serial melalui pin tx_pin
//            dilengkapi sinyal handshaking tx_start dan tx_busy.
// ============================================================================

`timescale 1ns / 1ps

module uart_tx #(
    parameter CLK_FREQ = 25_000_000,
    parameter BAUDRATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_byte,
    output reg        tx_pin,
    output reg        tx_busy
);

    localparam CLKS_PER_BIT = CLK_FREQ / BAUDRATE;

    localparam S_IDLE  = 3'd0;
    localparam S_START = 3'd1;
    localparam S_DATA  = 3'd2;
    localparam S_STOP  = 3'd3;

    reg [2:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  data_buf;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            clk_cnt  <= 16'd0;
            bit_idx  <= 3'd0;
            tx_pin   <= 1'b1; // Jalur serial idle HIGH
            tx_busy  <= 1'b0;
            data_buf <= 8'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    tx_pin  <= 1'b1;
                    if (tx_start) begin
                        data_buf <= tx_byte;
                        tx_busy  <= 1'b1;
                        state    <= S_START;
                    end else begin
                        tx_busy  <= 1'b0;
                    end
                end

                S_START: begin
                    tx_pin <= 1'b0; // Start bit selalu LOW
                    if (clk_cnt == (CLKS_PER_BIT - 1)) begin
                        clk_cnt <= 16'd0;
                        state   <= S_DATA;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end

                S_DATA: begin
                    tx_pin <= data_buf[bit_idx];
                    if (clk_cnt == (CLKS_PER_BIT - 1)) begin
                        clk_cnt <= 16'd0;
                        if (bit_idx == 3'd7) begin
                            bit_idx <= 3'd0;
                            state   <= S_STOP;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end

                S_STOP: begin
                    tx_pin <= 1'b1; // Stop bit selalu HIGH
                    if (clk_cnt == (CLKS_PER_BIT - 1)) begin
                        clk_cnt <= 16'd0;
                        tx_busy <= 1'b0;
                        state   <= S_IDLE;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule

