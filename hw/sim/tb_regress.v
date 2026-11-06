// ============================================================================
// Testbench: tb_regress.v
// Deskripsi: Uji regresi acak untuk core akselerator (top.v).
//            - Membaca N vektor uji dari file hex (dibuat oleh run_regression.py)
//            - Format per vektor (65 byte):
//                [0..15]  16 fitur input (INT8)
//                [16..47] 32 aktivasi Hidden-1 yang diharapkan
//                [48..63] 16 aktivasi Hidden-2 yang diharapkan
//                [64]     prediksi output yang diharapkan
//            - Membandingkan SETIAP neuron hidden (bukan hanya output akhir),
//              sehingga bug di layer awal tidak tersembunyi oleh saturasi output.
//            - Inferensi dijalankan berturut-turut tanpa reset untuk menguji
//              bahwa FSM kembali ke kondisi awal dengan benar.
//
// Plusargs:
//   +VEC=<file>   file vektor (wajib)
//   +N=<jumlah>   jumlah vektor (wajib)
//   +CYC=<nilai>  jumlah siklus yang diharapkan (opsional, 0 = tidak dicek)
//   +VCD=<file>   simpan waveform (opsional)
// ============================================================================

`timescale 1ns / 1ps

module tb_regress;

    localparam VEC_BYTES = 65;
    localparam MAX_N     = 4096;

    reg        clk = 1'b0;
    reg        rst_n = 1'b0;
    reg        start = 1'b0;
    reg  [3:0] in_feature_addr = 4'd0;
    reg  signed [7:0] in_feature_data = 8'sd0;
    reg        in_feature_we = 1'b0;

    wire       busy;
    wire       done;
    wire signed [7:0] prediction_out;
    wire [15:0] cycles_out;

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

    // Clock 27 MHz (sama dengan kristal Tang Nano 4K) -> periode ~37 ns
    always #18.5 clk = ~clk;

    reg [7:0] vec [0:VEC_BYTES*MAX_N-1];

    integer n_vec, exp_cyc, v, k, base;
    integer errors, vec_errors, timeout;
    reg [1023:0] vec_file, vcd_file;

    initial begin
        if (!$value$plusargs("VEC=%s", vec_file)) begin
            $display("RESULT FAIL: plusarg +VEC tidak diberikan");
            $finish;
        end
        if (!$value$plusargs("N=%d", n_vec)) begin
            $display("RESULT FAIL: plusarg +N tidak diberikan");
            $finish;
        end
        if (n_vec > MAX_N) begin
            $display("RESULT FAIL: N=%0d melebihi MAX_N=%0d", n_vec, MAX_N);
            $finish;
        end
        if (!$value$plusargs("CYC=%d", exp_cyc)) exp_cyc = 0;
        if ($value$plusargs("VCD=%s", vcd_file)) begin
            $dumpfile(vcd_file);
            $dumpvars(0, tb_regress);
        end

        $readmemh(vec_file, vec);

        errors = 0;
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (2) @(posedge clk);

        for (v = 0; v < n_vec; v = v + 1) begin
            base = v * VEC_BYTES;
            vec_errors = 0;

            // 1. Tulis 16 fitur
            for (k = 0; k < 16; k = k + 1) begin
                @(posedge clk);
                in_feature_addr <= k[3:0];
                in_feature_data <= vec[base + k];
                in_feature_we   <= 1'b1;
            end
            @(posedge clk);
            in_feature_we <= 1'b0;

            // 2. Pulsa start
            start <= 1'b1;
            @(posedge clk);
            start <= 1'b0;

            // 3. Tunggu done (dengan timeout).
            //    Sampel 1 ns setelah edge agar nilai register (NBA) sudah ter-update;
            //    tanpa ini 'done' terdeteksi 1 siklus terlambat.
            timeout = 0;
            #1;
            while (!done && timeout < 10000) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
            end
            if (!done) begin
                $display("[V%0d] TIMEOUT: sinyal done tidak pernah aktif", v);
                $display("RESULT FAIL errors=%0d", errors + 1);
                $finish;
            end

            // 4. Bandingkan Hidden-1
            for (k = 0; k < 32; k = k + 1) begin
                if (uut.h1_buf[k] !== vec[base + 16 + k]) begin
                    if (vec_errors < 4)
                        $display("[V%0d] H1[%0d] chip=%0d golden=%0d", v, k,
                                 uut.h1_buf[k], $signed(vec[base + 16 + k]));
                    vec_errors = vec_errors + 1;
                end
            end
            // 5. Bandingkan Hidden-2
            for (k = 0; k < 16; k = k + 1) begin
                if (uut.h2_buf[k] !== vec[base + 48 + k]) begin
                    if (vec_errors < 4)
                        $display("[V%0d] H2[%0d] chip=%0d golden=%0d", v, k,
                                 uut.h2_buf[k], $signed(vec[base + 48 + k]));
                    vec_errors = vec_errors + 1;
                end
            end
            // 6. Bandingkan output
            if (prediction_out !== $signed(vec[base + 64])) begin
                $display("[V%0d] OUT chip=%0d golden=%0d", v,
                         prediction_out, $signed(vec[base + 64]));
                vec_errors = vec_errors + 1;
            end
            // 7. Bandingkan jumlah siklus
            if (exp_cyc != 0 && cycles_out != exp_cyc) begin
                $display("[V%0d] CYCLES chip=%0d expected=%0d", v, cycles_out, exp_cyc);
                vec_errors = vec_errors + 1;
            end

            if (vec_errors != 0) errors = errors + 1;

            // Tunggu kembali idle sebelum vektor berikutnya (tanpa reset)
            while (busy) @(posedge clk);
        end

        if (errors == 0)
            $display("RESULT PASS vectors=%0d", n_vec);
        else
            $display("RESULT FAIL failed_vectors=%0d of %0d", errors, n_vec);
        $finish;
    end

endmodule
