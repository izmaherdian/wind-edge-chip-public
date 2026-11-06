// ============================================================================
// Module: fsm_controller.v
// Deskripsi: Finite State Machine (FSM) Sequencer & Memory Controller
//            Mengatur pembacaan aktivasi & bobot secara berurutan,
//            mengontrol eksekusi 3 layer MLP:
//            - Layer 1: 16 Input -> 32 Hidden (32 neuron * 4 langkah MAC4 = 128 langkah)
//            - Layer 2: 32 Hidden -> 16 Hidden (16 neuron * 8 langkah MAC4 = 128 langkah)
//            - Layer 3: 16 Hidden -> 1 Output (1 neuron * 4 langkah MAC4 = 4 langkah)
//            Total langkah MAC4: 260 langkah komputasi.
// ============================================================================

`timescale 1ns / 1ps

module fsm_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,           // Trigger mulai inferensi saat 16 fitur siap
    
    // Antarmuka Memori Bobot & Bias
    output reg  [10:0] weight_addr,     // 0 s.d 1039 (alamat 4 byte sekaligus / iterasi)
    output reg  [5:0]  bias_addr,       // 0 s.d 48
    
    // Kontrol Komputasi
    output reg         mac_clr,         // Bersihkan akumulator
    output reg         mac_en,          // Jalankan penjumlahan parsial
    output reg         write_act_en,    // Simpan aktivasi ke ping-pong RAM
    output reg  [5:0]  write_act_addr,  // Alamat penulisan neuron
    output reg  [1:0]  layer_sel,       // 0: L1, 1: L2, 2: L3
    output reg  [4:0]  in_idx_base,     // Indeks dasar input (kelipatan 4)
    
    // Status
    output reg         busy,
    output reg         done,
    output reg  [15:0] cycle_count      // Menghitung jumlah siklus clock eksekusi nyata
);

    // Definisi State
    localparam S_IDLE       = 3'd0;
    localparam S_L1_STEP    = 3'd1;
    localparam S_L1_POST    = 3'd2;
    localparam S_L2_STEP    = 3'd3;
    localparam S_L2_POST    = 3'd4;
    localparam S_L3_STEP    = 3'd5;
    localparam S_L3_POST    = 3'd6;
    localparam S_DONE       = 3'd7;

    reg [2:0] state, next_state;
    
    // Counters
    reg [5:0] neuron_cnt; // Hitung neuron yang sedang diproses
    reg [3:0] step_cnt;   // Hitung langkah MAC4 dalam 1 neuron

    // Pelacak Siklus Clock
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cycle_count <= 16'd0;
        end else if (state == S_IDLE) begin
            if (start) cycle_count <= 16'd0;
        end else if (busy) begin
            cycle_count <= cycle_count + 16'd1;
        end
    end

    // Transisi State FSM
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            neuron_cnt  <= 6'd0;
            step_cnt    <= 4'd0;
            weight_addr <= 11'd0;
            bias_addr   <= 6'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    neuron_cnt  <= 6'd0;
                    step_cnt    <= 4'd0;
                    weight_addr <= 11'd0;
                    bias_addr   <= 6'd0;
                    // Proteksi interlock: Hanya terima trigger jika sedang tidak sibuk
                    if (start && !busy) begin
                        state <= S_L1_STEP;
                    end
                end

                // --- LAYER 1: 32 Neuron, masing-masing butuh 4 langkah (16 input / 4) ---
                S_L1_STEP: begin
                    weight_addr <= weight_addr + 11'd4;
                    if (step_cnt == 4'd3) begin
                        step_cnt <= 4'd0;
                        state    <= S_L1_POST;
                    end else begin
                        step_cnt <= step_cnt + 4'd1;
                    end
                end

                S_L1_POST: begin
                    bias_addr <= bias_addr + 6'd1;
                    if (neuron_cnt == 6'd31) begin
                        neuron_cnt <= 6'd0;
                        state      <= S_L2_STEP;
                    end else begin
                        neuron_cnt <= neuron_cnt + 6'd1;
                        state      <= S_L1_STEP;
                    end
                end

                // --- LAYER 2: 16 Neuron, masing-masing butuh 8 langkah (32 input / 4) ---
                S_L2_STEP: begin
                    weight_addr <= weight_addr + 11'd4;
                    if (step_cnt == 4'd7) begin
                        step_cnt <= 4'd0;
                        state    <= S_L2_POST;
                    end else begin
                        step_cnt <= step_cnt + 4'd1;
                    end
                end

                S_L2_POST: begin
                    bias_addr <= bias_addr + 6'd1;
                    if (neuron_cnt == 6'd15) begin
                        neuron_cnt <= 6'd0;
                        state      <= S_L3_STEP;
                    end else begin
                        neuron_cnt <= neuron_cnt + 6'd1;
                        state      <= S_L2_STEP;
                    end
                end

                // --- LAYER 3: 1 Neuron Output, butuh 4 langkah (16 input / 4) ---
                S_L3_STEP: begin
                    weight_addr <= weight_addr + 11'd4;
                    if (step_cnt == 4'd3) begin
                        step_cnt <= 4'd0;
                        state    <= S_L3_POST;
                    end else begin
                        step_cnt <= step_cnt + 4'd1;
                    end
                end

                S_L3_POST: begin
                    bias_addr <= bias_addr + 6'd1;
                    state     <= S_DONE;
                end

                S_DONE: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

    // Logika Sinyal Output Kontrol
    always @(*) begin
        busy           = (state != S_IDLE);
        done           = (state == S_DONE);
        mac_clr        = (step_cnt == 4'd0 && (state == S_L1_STEP || state == S_L2_STEP || state == S_L3_STEP));
        mac_en         = (state == S_L1_STEP || state == S_L2_STEP || state == S_L3_STEP);
        write_act_en   = (state == S_L1_POST || state == S_L2_POST || state == S_L3_POST);
        write_act_addr = neuron_cnt;
        in_idx_base    = step_cnt * 4;

        case (state)
            S_L1_STEP, S_L1_POST: layer_sel = 2'd0;
            S_L2_STEP, S_L2_POST: layer_sel = 2'd1;
            S_L3_STEP, S_L3_POST: layer_sel = 2'd2;
            default:              layer_sel = 2'd0;
        endcase
    end

endmodule

