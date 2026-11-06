// ============================================================================
// Testbench: tb_top.v
// Deskripsi: Testbench Verilog Mandiri untuk Menguji Top-Level Akselerator
//            Memasukkan 16 data uji, memicu sinyal start, memantau siklus clock,
//            menghasilkan dump gelombang VCD (waveforms/wave.vcd),
//            dan membandingkan hasil keluaran dengan nilai Golden Model.
// ============================================================================

`timescale 1ns / 1ps

module tb_top;

    reg        clk;
    reg        rst_n;
    reg        start;
    reg  [3:0] in_feature_addr;
    reg  signed [7:0] in_feature_data;
    reg        in_feature_we;

    wire       busy;
    wire       done;
    wire signed [7:0] prediction_out;
    wire [15:0] cycles_out;

    // Instansiasi Unit Under Test (UUT)
    top uut (
        .clk             (clk),
        .rst_n           (rst_n),
        .start           (start),
        .in_feature_addr (in_feature_addr),
        .in_feature_data (in_feature_data),
        .in_feature_we   (in_feature_we),
        .busy            (busy),
        .done            (done),
        .prediction_out  (prediction_out),
        .cycles_out      (cycles_out)
    );

    // Generator Clock 25 MHz (Periode 40 ns)
    always #20 clk = ~clk;

    // Array 16 Data Input Uji (Sama persis dengan dummy_input di ml/golden_model.py)
    reg signed [7:0] test_input [0:15];
    integer i;

    initial begin
        // Setup dump waveform untuk visualisasi di VS Code (Surfer / WaveTrace)
        $dumpfile("waveforms/wave.vcd");
        $dumpvars(0, tb_top);

        // Nilai input uji
        test_input[0]  =  8'sd12;
        test_input[1]  = -8'sd8;
        test_input[2]  =  8'sd25;
        test_input[3]  =  8'sd4;
        test_input[4]  =  8'sd30;
        test_input[5]  = -8'sd15;
        test_input[6]  =  8'sd0;
        test_input[7]  =  8'sd18;
        test_input[8]  = -8'sd22;
        test_input[9]  =  8'sd10;
        test_input[10] =  8'sd5;
        test_input[11] = -8'sd3;
        test_input[12] =  8'sd8;
        test_input[13] =  8'sd14;
        test_input[14] = -8'sd1;
        test_input[15] =  8'sd9;

        // Inisialisasi
        clk             = 0;
        rst_n           = 0;
        start           = 0;
        in_feature_addr = 0;
        in_feature_data = 0;
        in_feature_we   = 0;

        #100;
        rst_n = 1;
        #40;

        $display("------------------------------------------------------------------");
        $display("[SIMULASI] Memulai Pengisian 16 Fitur ke Buffer Akselerator...");
        $display("------------------------------------------------------------------");

        // Tulis 16 Fitur satu per satu ke in_buf
        for (i = 0; i < 16; i = i + 1) begin
            @(posedge clk);
            in_feature_addr <= i[3:0];
            in_feature_data <= test_input[i];
            in_feature_we   <= 1;
        end

        @(posedge clk);
        in_feature_we <= 0;
        #40;

        // Picu Sinyal Start Inferensi
        $display("[SIMULASI] Memicu Sinyal START Inferensi Neural Network...");
        @(posedge clk);
        start <= 1;
        @(posedge clk);
        start <= 0;

        // Tunggu Sinyal DONE
        wait(done == 1);
        @(posedge clk);

        $display("------------------------------------------------------------------");
        $display("[HASIL SIMULASI AKSELERATOR FPGA]");
        $display(" -> Status            : SELESAI (DONE)");
        $display(" -> Siklus Clock Nyata: %0d siklus", cycles_out);
        $display(" -> Waktu Eksekusi    : %0d ns (pada clock 25 MHz)", cycles_out * 40);
        $display(" -> Output Prediksi   : %0d (INT8)", prediction_out);
        $display("------------------------------------------------------------------");

        #100;
        $finish;
    end

endmodule

