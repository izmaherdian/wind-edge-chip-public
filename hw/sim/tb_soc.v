// ============================================================================
// Testbench: tb_soc.v
// Deskripsi: Uji end-to-end tingkat SoC (top_soc.v) melalui pin UART fisik
//            dengan protokol berbingkai paket (0xAA 0x55) & verifikasi CRC-8.
//
// Alur Uji:
// - Host mengirim frame 19-byte: [0xAA, 0x55, 16 Byte Fitur INT8, 1 Byte CRC-8]
// - FPGA membalas frame 7-byte:  [0x55, 0xAA, STATUS, PREDIKSI, CYC_MSB, CYC_LSB, CRC-8]
// - Verifikasi nilai prediksi terhadap golden model INT8 dan integritas CRC-8.
// ============================================================================

`timescale 1ns / 1ps

module tb_soc;

    localparam CLK_FREQ  = 27_000_000;
    localparam BAUDRATE  = 921600;
    localparam VEC_BYTES = 65;
    localparam MAX_N     = 256;

    localparam CLKS_PER_BIT = CLK_FREQ / BAUDRATE;
    localparam real CLK_PERIOD = 1.0e9 / CLK_FREQ;
    localparam real BIT_NS = CLKS_PER_BIT * CLK_PERIOD;

    reg  clk = 1'b0;
    reg  rst_n = 1'b0;
    reg  rx_pin = 1'b1;
    wire tx_pin;
    wire led_busy, led_done;

    top_soc #(
        .CLK_FREQ (CLK_FREQ),
        .BAUDRATE (BAUDRATE)
    ) dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .rx_pin   (rx_pin),
        .tx_pin   (tx_pin),
        .led_busy (led_busy),
        .led_done (led_done)
    );

    always #(CLK_PERIOD/2.0) clk = ~clk;

    // --- Fungsi Helper CRC-8 CCITT (0x07) di Sisi Testbench ---
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

    // --- Pengirim UART (sisi host / ESP32) ---
    task uart_send(input [7:0] b);
        integer i;
        begin
            rx_pin = 1'b0;            // start bit
            #(BIT_NS);
            for (i = 0; i < 8; i = i + 1) begin
                rx_pin = b[i];        // LSB dulu
                #(BIT_NS);
            end
            rx_pin = 1'b1;            // stop bit
            #(BIT_NS);
        end
    endtask

    // --- Penerima UART (sisi host / ESP32) ---
    task uart_recv(output [7:0] b, output reg ok);
        integer i, t;
        begin
            ok = 1'b0;
            b  = 8'h00;
            t  = 0;
            // tunggu start bit (timeout ~ 5 ms)
            while (tx_pin == 1'b1 && t < 5_000_000) begin
                #10; t = t + 10;
            end
            if (tx_pin == 1'b0) begin
                #(BIT_NS * 1.5);      // ke tengah bit data 0
                for (i = 0; i < 8; i = i + 1) begin
                    b[i] = tx_pin;
                    #(BIT_NS);
                end
                ok = (tx_pin == 1'b1);
                #(BIT_NS * 0.5);
            end
        end
    endtask

    reg [7:0] vec [0:VEC_BYTES*MAX_N-1];
    reg [1023:0] vec_file;
    integer n_vec, exp_cyc, v, k, base, errors;
    reg [7:0] tx_crc;
    reg [7:0] r_sync1, r_sync2, r_status, r_pred, r_cyc_h, r_cyc_l, r_crc;
    reg ok_sync1, ok_sync2, ok_status, ok_pred, ok_cyc_h, ok_cyc_l, ok_crc;
    reg [7:0] calc_resp_crc;

    initial begin
        if (!$value$plusargs("VEC=%s", vec_file) || !$value$plusargs("N=%d", n_vec)) begin
            $display("RESULT FAIL: plusarg +VEC/+N tidak diberikan");
            $finish;
        end
        if (n_vec > MAX_N) n_vec = MAX_N;
        if (!$value$plusargs("CYC=%d", exp_cyc)) exp_cyc = 0;
        $readmemh(vec_file, vec);

        errors = 0;
        #(CLK_PERIOD * 10);
        rst_n = 1'b1;
        #(CLK_PERIOD * 10);

        for (v = 0; v < n_vec; v = v + 1) begin
            base = v * VEC_BYTES;
            
            // Hitung CRC payload 16 byte
            tx_crc = 8'h00;
            for (k = 0; k < 16; k = k + 1)
                tx_crc = crc8_byte(tx_crc, vec[base + k]);

            fork
                begin
                    // Kirim Frame 19-Byte: [0xAA, 0x55, 16B payload, CRC8]
                    uart_send(8'hAA);
                    uart_send(8'h55);
                    for (k = 0; k < 16; k = k + 1)
                        uart_send(vec[base + k]);
                    uart_send(tx_crc);
                end
                begin
                    // Terima Frame Balasan 7-Byte
                    uart_recv(r_sync1,  ok_sync1);
                    uart_recv(r_sync2,  ok_sync2);
                    uart_recv(r_status, ok_status);
                    uart_recv(r_pred,   ok_pred);
                    uart_recv(r_cyc_h,  ok_cyc_h);
                    uart_recv(r_cyc_l,  ok_cyc_l);
                    uart_recv(r_crc,    ok_crc);
                end
            join

            calc_resp_crc = crc8_byte(crc8_byte(crc8_byte(crc8_byte(8'h00, r_status), r_pred), r_cyc_h), r_cyc_l);

            if (!(ok_sync1 && ok_sync2 && ok_status && ok_pred && ok_cyc_h && ok_cyc_l && ok_crc)) begin
                $display("[V%0d] UART: balasan tidak lengkap / framing error", v);
                errors = errors + 1;
            end else if (r_sync1 !== 8'h55 || r_sync2 !== 8'hAA) begin
                $display("[V%0d] UART: Header sync salah [0x%02x, 0x%02x]", v, r_sync1, r_sync2);
                errors = errors + 1;
            end else if (r_status !== 8'h00) begin
                $display("[V%0d] UART: Status error 0x%02x dari FPGA", v, r_status);
                errors = errors + 1;
            end else if (r_crc !== calc_resp_crc) begin
                $display("[V%0d] UART: CRC balasan korup (recv=0x%02x calc=0x%02x)", v, r_crc, calc_resp_crc);
                errors = errors + 1;
            end else if (r_pred !== vec[base + 64] ||
                         (exp_cyc != 0 && {r_cyc_h, r_cyc_l} != exp_cyc)) begin
                $display("[V%0d] chip pred=%0d cyc=%0d | golden pred=%0d cyc=%0d", v,
                         $signed(r_pred), {r_cyc_h, r_cyc_l}, $signed(vec[base + 64]), exp_cyc);
                errors = errors + 1;
            end
        end

        if (errors == 0)
            $display("RESULT PASS vectors=%0d (Framing 0xAA 0x55 & CRC-8 Verified)", n_vec);
        else
            $display("RESULT FAIL failed_vectors=%0d of %0d", errors, n_vec);
        $finish;
    end

endmodule
