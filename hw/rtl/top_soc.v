// ============================================================================
// Module: top_soc.v
// Deskripsi: Top-Level System-on-Chip (SoC) Akselerator dengan Antarmuka UART
//            Berbingkai Paket (Framed) & Pemeriksa Integritas Hardware CRC-8.
//
// Fitur Utama:
// 1. Protokol Bingkai Paket (Packet Framing):
//    - Host -> FPGA (19 Byte):
//      [0xAA (SYNC1), 0x55 (SYNC2), 16 Byte Fitur INT8, 1 Byte CRC8 Payload]
//    - FPGA -> Host (7 Byte):
//      [0x55 (SYNC1), 0xAA (SYNC2), 1 Byte Status (0x00=OK, 0xE1=CRC_ERR, 0xE2=TIMEOUT),
//       1 Byte Prediksi INT8, 1 Byte Cycle MSB, 1 Byte Cycle LSB, 1 Byte CRC8]
//
// 2. Hardware CRC-8 Engine:
//    - Polinomial: x^8 + x^2 + x + 1 (0x07, CRC-8 CCITT/ITU), Inisialisasi: 0x00.
//    - Mencegah eksekusi data yang korup akibat derau elektromagnetik.
//
// 3. Watchdog FSM Timeout:
//    - Mencegah FSM terkunci jika transmisi terputus di tengah frame.
//    - Otomatis mereset FSM penerima kembali ke WAIT_SYNC1.
//
// 4. Bandwidth Tinggi (Anti-Bottleneck):
//    - Default BAUDRATE = 921600 bps (8x lebih cepat dibanding 115200 bps).
//    - Waktu transmisi terpangkas dari ~1,65 ms menjadi ~206 us.
// ============================================================================

`timescale 1ns / 1ps

module top_soc #(
    parameter CLK_FREQ       = 27_000_000,
    parameter BAUDRATE       = 921600,
    parameter TIMEOUT_CYCLES = 270_000      // ~10 ms @ 27 MHz
)(
    input  wire clk,
    input  wire rst_n,
    input  wire rx_pin,
    output wire tx_pin,
    output wire led_busy,
    output wire led_done
);

    // --- Fungsi Hardware CRC-8 (Polinomial 0x07, Inisialisasi 0x00) ---
    function [7:0] crc8_byte;
        input [7:0] crc_in;
        input [7:0] data_in;
        reg   [7:0] c;
        integer i;
        begin
            c = crc_in ^ data_in;
            for (i = 0; i < 8; i = i + 1) begin
                if (c[7])
                    c = (c << 1) ^ 8'h07;
                else
                    c = (c << 1);
            end
            crc8_byte = c;
        end
    endfunction

    // --- Sinyal Akselerator Core ---
    reg               core_start;
    reg  [3:0]        in_feature_addr;
    reg  signed [7:0] in_feature_data;
    reg               in_feature_we;
    wire              core_busy;
    wire              core_done;
    wire signed [7:0] core_prediction;
    wire [15:0]       core_cycles;

    // Pulse stretcher (~0.2 detik @ 27 MHz) untuk LED onboard Pin 10 (Active-Low)
    reg [22:0] led_hold_cnt;
    reg        trigger_error;
    reg [7:0]  error_code;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            led_hold_cnt <= 23'd0;
        end else if (core_busy || core_done || trigger_error) begin
            led_hold_cnt <= 23'd5_400_000;
        end else if (led_hold_cnt != 23'd0) begin
            led_hold_cnt <= led_hold_cnt - 23'd1;
        end
    end

    assign led_busy = (led_hold_cnt != 23'd0) ? 1'b0 : 1'b1;

    // LED Done toggle register
    reg led_done_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            led_done_reg <= 1'b0;
        else if (core_done)
            led_done_reg <= ~led_done_reg;
    end
    assign led_done = led_done_reg;

    top u_accelerator_core (
        .clk             (clk),
        .rst_n           (rst_n),
        .start           (core_start),
        .in_feature_addr (in_feature_addr),
        .in_feature_data (in_feature_data),
        .in_feature_we   (in_feature_we),
        .busy            (core_busy),
        .done            (core_done),
        .prediction_out  (core_prediction),
        .cycles_out      (core_cycles)
    );

    // --- UART Transceiver Physical Layer ---
    wire [7:0] rx_byte;
    wire       rx_valid;
    reg        tx_start;
    reg  [7:0] tx_byte;
    wire       tx_busy;

    uart_rx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUDRATE (BAUDRATE)
    ) u_uart_rx (
        .clk        (clk),
        .rst_n      (rst_n),
        .rx_pin     (rx_pin),
        .rx_byte    (rx_byte),
        .byte_valid (rx_valid)
    );

    uart_tx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUDRATE (BAUDRATE)
    ) u_uart_tx (
        .clk      (clk),
        .rst_n    (rst_n),
        .tx_start (tx_start),
        .tx_byte  (tx_byte),
        .tx_pin   (tx_pin),
        .tx_busy  (tx_busy)
    );

    // --- FSM Penerima Paket Berbingkai (Framed RX FSM) ---
    localparam [2:0]
        RX_WAIT_SYNC1 = 3'd0,  // Menunggu 0xAA
        RX_WAIT_SYNC2 = 3'd1,  // Menunggu 0x55
        RX_PAYLOAD    = 3'd2,  // Menampung 16 Byte Fitur (0..15)
        RX_CHECK_CRC  = 3'd3;  // Memverifikasi 1 Byte CRC8

    reg [2:0]  rx_state;
    reg [3:0]  rx_count;
    reg [7:0]  rx_crc_calc;
    reg [23:0] rx_timeout_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_state        <= RX_WAIT_SYNC1;
            rx_count        <= 4'd0;
            rx_crc_calc     <= 8'h00;
            rx_timeout_cnt  <= 24'd0;
            in_feature_addr <= 4'd0;
            in_feature_data <= 8'sd0;
            in_feature_we   <= 1'b0;
            core_start      <= 1'b0;
            trigger_error   <= 1'b0;
            error_code      <= 8'h00;
        end else begin
            in_feature_we <= 1'b0;
            core_start    <= 1'b0;
            trigger_error <= 1'b0;

            // Watchdog Timeout: reset ke WAIT_SYNC1 jika frame menggantung
            if (rx_state != RX_WAIT_SYNC1) begin
                if (rx_timeout_cnt >= TIMEOUT_CYCLES) begin
                    rx_state       <= RX_WAIT_SYNC1;
                    rx_timeout_cnt <= 24'd0;
                    trigger_error  <= 1'b1;
                    error_code     <= 8'hE2; // TIMEOUT_ERROR
                end else begin
                    rx_timeout_cnt <= rx_timeout_cnt + 24'd1;
                end
            end else begin
                rx_timeout_cnt <= 24'd0;
            end

            case (rx_state)
                RX_WAIT_SYNC1: begin
                    if (rx_valid) begin
                        if (rx_byte == 8'hAA) begin
                            rx_state       <= RX_WAIT_SYNC2;
                            rx_timeout_cnt <= 24'd0;
                        end
                    end
                end

                RX_WAIT_SYNC2: begin
                    if (rx_valid) begin
                        rx_timeout_cnt <= 24'd0;
                        if (rx_byte == 8'h55) begin
                            rx_state    <= RX_PAYLOAD;
                            rx_count    <= 4'd0;
                            rx_crc_calc <= 8'h00;
                        end else if (rx_byte == 8'hAA) begin
                            rx_state <= RX_WAIT_SYNC2; // Tetap di SYNC2 jika ada double 0xAA
                        end else begin
                            rx_state <= RX_WAIT_SYNC1;
                        end
                    end
                end

                RX_PAYLOAD: begin
                    if (rx_valid && !core_busy) begin
                        rx_timeout_cnt  <= 24'd0;
                        in_feature_addr <= rx_count;
                        in_feature_data <= rx_byte;
                        in_feature_we   <= 1'b1;
                        rx_crc_calc     <= crc8_byte(rx_crc_calc, rx_byte);

                        if (rx_count == 4'd15) begin
                            rx_state <= RX_CHECK_CRC;
                        end else begin
                            rx_count <= rx_count + 4'd1;
                        end
                    end
                end

                RX_CHECK_CRC: begin
                    if (rx_valid) begin
                        rx_timeout_cnt <= 24'd0;
                        rx_state       <= RX_WAIT_SYNC1;
                        if (rx_byte == rx_crc_calc) begin
                            // CRC VALID -> Picu Akselerator Hardware!
                            core_start <= 1'b1;
                        end else begin
                            // CRC INVALID -> Batalkan & Kirim Kode Status E1
                            trigger_error <= 1'b1;
                            error_code    <= 8'hE1; // CRC_ERROR
                        end
                    end
                end

                default: rx_state <= RX_WAIT_SYNC1;
            endcase
        end
    end

    // --- FSM Pengirim Paket Balasan Berbingkai (Framed TX FSM) ---
    // Paket balasan 7 Byte: [0x55, 0xAA, STATUS, PRED, CYC_H, CYC_L, CRC8]
    localparam [2:0]
        TX_IDLE   = 3'd0,
        TX_SYNC1  = 3'd1, // 0x55
        TX_SYNC2  = 3'd2, // 0xAA
        TX_STATUS = 3'd3, // status
        TX_PRED   = 3'd4, // pred
        TX_CYC_H  = 3'd5, // cyc_h
        TX_CYC_L  = 3'd6, // cyc_l
        TX_CRC    = 3'd7; // crc8

    reg [2:0]        tx_state;
    reg [7:0]        saved_status;
    reg signed [7:0] saved_pred;
    reg [15:0]       saved_cycles;
    reg [7:0]        saved_tx_crc;

    // Kalkulasi CRC-8 atas 4 Byte respons: [status, pred, cyc_h, cyc_l]
    wire [7:0] crc_step0 = crc8_byte(8'h00,      saved_status);
    wire [7:0] crc_step1 = crc8_byte(crc_step0,  saved_pred);
    wire [7:0] crc_step2 = crc8_byte(crc_step1,  saved_cycles[15:8]);
    wire [7:0] crc_resp  = crc8_byte(crc_step2,  saved_cycles[7:0]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_state     <= TX_IDLE;
            tx_start     <= 1'b0;
            tx_byte      <= 8'd0;
            saved_status <= 8'd0;
            saved_pred   <= 8'sd0;
            saved_cycles <= 16'd0;
            saved_tx_crc <= 8'd0;
        end else begin
            tx_start <= 1'b0;

            case (tx_state)
                TX_IDLE: begin
                    if (core_done) begin
                        saved_status <= 8'h00; // 0x00 = OK
                        saved_pred   <= core_prediction;
                        saved_cycles <= core_cycles;
                        saved_tx_crc <= crc_resp;
                        tx_byte      <= 8'h55; // Header Balasan 1
                        tx_start     <= 1'b1;
                        tx_state     <= TX_SYNC1;
                    end else if (trigger_error) begin
                        saved_status <= error_code; // 0xE1 (CRC) / 0xE2 (TIMEOUT)
                        saved_pred   <= 8'sd0;
                        saved_cycles <= 16'd0;
                        saved_tx_crc <= crc_resp;
                        tx_byte      <= 8'h55; // Header Balasan 1
                        tx_start     <= 1'b1;
                        tx_state     <= TX_SYNC1;
                    end
                end

                TX_SYNC1: begin
                    if (!tx_busy && !tx_start) begin
                        tx_byte  <= 8'hAA; // Header Balasan 2
                        tx_start <= 1'b1;
                        tx_state <= TX_SYNC2;
                    end
                end

                TX_SYNC2: begin
                    if (!tx_busy && !tx_start) begin
                        tx_byte  <= saved_status; // Byte 2: STATUS
                        tx_start <= 1'b1;
                        tx_state <= TX_STATUS;
                    end
                end

                TX_STATUS: begin
                    if (!tx_busy && !tx_start) begin
                        tx_byte  <= saved_pred;   // Byte 3: PREDIKSI INT8
                        tx_start <= 1'b1;
                        tx_state <= TX_PRED;
                    end
                end

                TX_PRED: begin
                    if (!tx_busy && !tx_start) begin
                        tx_byte  <= saved_cycles[15:8]; // Byte 4: SIKLUS MSB
                        tx_start <= 1'b1;
                        tx_state <= TX_CYC_H;
                    end
                end

                TX_CYC_H: begin
                    if (!tx_busy && !tx_start) begin
                        tx_byte  <= saved_cycles[7:0];  // Byte 5: SIKLUS LSB
                        tx_start <= 1'b1;
                        tx_state <= TX_CYC_L;
                    end
                end

                TX_CYC_L: begin
                    if (!tx_busy && !tx_start) begin
                        // Hitung CRC akhir atas payload
                        tx_byte  <= crc8_byte(crc8_byte(crc8_byte(crc8_byte(8'h00, saved_status), saved_pred), saved_cycles[15:8]), saved_cycles[7:0]);
                        tx_start <= 1'b1;
                        tx_state <= TX_CRC;
                    end
                end

                TX_CRC: begin
                    if (!tx_busy && !tx_start) begin
                        tx_state <= TX_IDLE; // Selesai transmisi frame 7-Byte
                    end
                end

                default: tx_state <= TX_IDLE;
            endcase
        end
    end

endmodule
