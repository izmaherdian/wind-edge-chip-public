// ============================================================================
// Module: uart_rx.v
// Deskripsi: Penerima Serial UART (8-N-1)
//            Menerima stream serial bit demi bit pada baudrate yang ditentukan,
//            melakukan oversampling pada tengah-tengah bit, dan mengeluarkan
//            pulsa byte_valid saat 1 byte data utuh diterima.
// ============================================================================

`timescale 1ns / 1ps

module uart_rx #(
    parameter CLK_FREQ = 25_000_000,
    parameter BAUDRATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_pin,
    output reg  [7:0] rx_byte,
    output reg        byte_valid
);

    localparam CLKS_PER_BIT = CLK_FREQ / BAUDRATE;

    localparam S_IDLE  = 3'd0;
    localparam S_START = 3'd1;
    localparam S_DATA  = 3'd2;
    localparam S_STOP  = 3'd3;

    reg [2:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;

    // Sinkronisasi ganda untuk mencegah metastabilitas input asinkron RX
    reg rx_sync1, rx_sync2;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync1 <= 1'b1;
            rx_sync2 <= 1'b1;
        end else begin
            rx_sync1 <= rx_pin;
            rx_sync2 <= rx_sync1;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            clk_cnt    <= 16'd0;
            bit_idx    <= 3'd0;
            rx_byte    <= 8'd0;
            byte_valid <= 1'b0;
        end else begin
            byte_valid <= 1'b0; // Default pulsa 1 siklus

            case (state)
                S_IDLE: begin
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    if (rx_sync2 == 1'b0) begin // Deteksi falling edge start bit
                        state <= S_START;
                    end
                end

                S_START: begin
                    // Sampel di tengah start bit (CLKS_PER_BIT / 2)
                    if (clk_cnt == (CLKS_PER_BIT / 2)) begin
                        if (rx_sync2 == 1'b0) begin
                            clk_cnt <= 16'd0;
                            state   <= S_DATA;
                        end else begin
                            state <= S_IDLE; // False alarm glitch
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end

                S_DATA: begin
                    if (clk_cnt == (CLKS_PER_BIT - 1)) begin
                        clk_cnt <= 16'd0;
                        rx_byte[bit_idx] <= rx_sync2;
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
                    if (clk_cnt == (CLKS_PER_BIT - 1)) begin
                        clk_cnt    <= 16'd0;
                        byte_valid <= 1'b1; // Byte lengkap diterima
                        state      <= S_IDLE;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule

