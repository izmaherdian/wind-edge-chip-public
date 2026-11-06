// ============================================================================
// Module: top.v
// Deskripsi: Top-Level Module Akselerator Inferensi Neural Network INT8
//            Mengintegrasikan:
//            - ROM Bobot (1.040 Byte) & Bias (49 DWORD)
//            - Buffer Aktivasi Input & Ping-Pong RAM (Hidden 1 & 2)
//            - FSM Controller Sequencer
//            - Unit Aritmatika Paralel MAC4
//            - Unit Pasca-Proses Re-kuantisasi & ReLU
// ============================================================================

`timescale 1ns / 1ps

module top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,              // Pulsa trigger mulai prediksi
    
    // Antarmuka Buffer Input 16 Fitur (INT8 Signed)
    input  wire [3:0]  in_feature_addr,    // 0 s.d 15
    input  wire signed [7:0] in_feature_data,
    input  wire        in_feature_we,      // Tulis byte fitur ke buffer input
    
    // Status & Hasil Prediksi
    output wire        busy,
    output wire        done,
    output reg  signed [7:0] prediction_out, // Prediksi daya akhir (INT8)
    output wire [15:0] cycles_out          // Jumlah siklus clock eksekusi
);

    // --- 1. Memori On-Chip Bobot (Gowin Hardware Block RAM SPX9) & Bias ---
    wire [31:0]       weights_q;
    reg signed [31:0] bias_mem [0:48];

    initial begin
        $readmemh("bias.hex", bias_mem);
    end

    // --- 2. Buffer Aktivasi (Input, Hidden 1, Hidden 2) ---
    reg signed [7:0] in_buf [0:15];
    reg signed [7:0] h1_buf [0:31];
    reg signed [7:0] h2_buf [0:15];

    // Penulisan fitur awal dari luar (ESP32/Host)
    always @(posedge clk) begin
        if (in_feature_we) begin
            in_buf[in_feature_addr] <= in_feature_data;
        end
    end

    // --- 3. Sinyal Interkoneksi FSM ---
    wire [10:0] weight_addr;
    wire [5:0]  bias_addr;
    wire        mac_clr;
    wire        mac_en;
    wire        write_act_en;
    wire [5:0]  write_act_addr;
    wire [1:0]  layer_sel;
    wire [4:0]  in_idx_base;

    fsm_controller u_fsm (
        .clk            (clk),
        .rst_n          (rst_n),
        .start          (start),
        .weight_addr    (weight_addr),
        .bias_addr      (bias_addr),
        .mac_clr        (mac_clr),
        .mac_en         (mac_en),
        .write_act_en   (write_act_en),
        .write_act_addr (write_act_addr),
        .layer_sel      (layer_sel),
        .in_idx_base    (in_idx_base),
        .busy           (busy),
        .done           (done),
        .cycle_count    (cycles_out)
    );

    // Alamat prefetch BRAM (260 word, tiap word memuat 4 bobot INT8 paralel)
    reg [8:0] step_addr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            step_addr <= 9'd0;
        end else if (!busy) begin
            if (start) step_addr <= 9'd1;
            else       step_addr <= 9'd0;
        end else if (mac_en) begin
            if (step_addr == 9'd259)
                step_addr <= 9'd0;
            else
                step_addr <= step_addr + 9'd1;
        end
    end

    weights_rom u_weights_rom (
        .clk  (clk),
        .ce   (mac_en || !busy),
        .addr (step_addr),
        .dout (weights_q)
    );

    // --- 4. Multiplexer Data Input ke MAC4 ---
    reg signed [7:0] mac_in0, mac_in1, mac_in2, mac_in3;

    always @(*) begin
        case (layer_sel)
            2'd0: begin // Layer 1: membaca dari in_buf [0..15]
                mac_in0 = in_buf[in_idx_base + 0];
                mac_in1 = in_buf[in_idx_base + 1];
                mac_in2 = in_buf[in_idx_base + 2];
                mac_in3 = in_buf[in_idx_base + 3];
            end
            2'd1: begin // Layer 2: membaca dari h1_buf [0..31]
                mac_in0 = h1_buf[in_idx_base + 0];
                mac_in1 = h1_buf[in_idx_base + 1];
                mac_in2 = h1_buf[in_idx_base + 2];
                mac_in3 = h1_buf[in_idx_base + 3];
            end
            2'd2: begin // Layer 3: membaca dari h2_buf [0..15]
                mac_in0 = h2_buf[in_idx_base + 0];
                mac_in1 = h2_buf[in_idx_base + 1];
                mac_in2 = h2_buf[in_idx_base + 2];
                mac_in3 = h2_buf[in_idx_base + 3];
            end
            default: begin
                mac_in0 = 8'sd0; mac_in1 = 8'sd0; mac_in2 = 8'sd0; mac_in3 = 8'sd0;
            end
        endcase
    end

    // Pembacaan 4 Bobot Sekaligus dari register BRAM 32-bit (Little-Endian: w0 di bit [7:0])
    wire signed [7:0] w0 = weights_q[7:0];
    wire signed [7:0] w1 = weights_q[15:8];
    wire signed [7:0] w2 = weights_q[23:16];
    wire signed [7:0] w3 = weights_q[31:24];

    // --- 5. Unit Komputasi Paralel MAC4 ---
    wire signed [31:0] mac_acc_out;

    mac4_engine u_mac4 (
        .clk     (clk),
        .rst_n   (rst_n),
        .clr_acc (mac_clr),
        .en_acc  (mac_en),
        .in0     (mac_in0), .in1 (mac_in1), .in2 (mac_in2), .in3 (mac_in3),
        .w0      (w0),      .w1  (w1),      .w2  (w2),      .w3  (w3),
        .acc_out (mac_acc_out)
    );

    // --- 6. Unit Pasca-Proses Re-kuantisasi & ReLU ---
    wire signed [31:0] cur_bias = bias_mem[bias_addr];
    wire signed [7:0]  act_post_out;

    post_process u_post (
        .acc_in      (mac_acc_out),
        .bias_in     (cur_bias),
        .mult_scale  (16'd32),   // Multiplier faktor skala sinkron dengan golden model
        .shift_scale (5'd8),     // Shift skala (dibagi 256)
        .act_out     (act_post_out)
    );

    // --- 7. Penyimpanan Hasil Aktivasi Neuron Antarlapisan ---
    always @(posedge clk) begin
        if (write_act_en) begin
            case (layer_sel)
                2'd0: h1_buf[write_act_addr] <= act_post_out;
                2'd1: h2_buf[write_act_addr] <= act_post_out;
                2'd2: prediction_out         <= act_post_out;
            endcase
        end
    end

endmodule

