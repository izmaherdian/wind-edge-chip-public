// Catat keluaran RTL, cek seluruh hidden neuron, dan tolak X/Z.
// Jalankan lewat ml/results/export_rtl_predictions.py agar file memori tersedia.
`timescale 1ns / 1ps
module tb_predictions;
    reg clk = 0, rst_n = 0, start = 0, in_feature_we = 0;
    reg [3:0] in_feature_addr = 0;
    reg signed [7:0] in_feature_data = 0;
    wire busy, done;
    wire signed [7:0] prediction_out;
    wire [15:0] cycles_out;
    top uut (.clk(clk), .rst_n(rst_n), .start(start),
        .in_feature_addr(in_feature_addr), .in_feature_data(in_feature_data),
        .in_feature_we(in_feature_we), .busy(busy), .done(done),
        .prediction_out(prediction_out), .cycles_out(cycles_out));
    always #18.5 clk = ~clk;
    reg [7:0] vec [0:65*4096-1];
    integer n, v, k, base, ticks;
    initial begin
        if (!$value$plusargs("N=%d", n) || n < 1 || n > 4096)
            $fatal(1, "Jumlah vektor tidak valid");
        // Nama relatif pendek: tidak ada path yang terpotong oleh packed reg.
        $readmemh("vectors.hex", vec, 0, n*65-1);
        for (k = 0; k < n*65; k = k+1)
            if ((^vec[k]) === 1'bx) $fatal(1, "Vektor kosong/X pada byte %0d", k);
        repeat (4) @(posedge clk);
        rst_n <= 1;
        repeat (2) @(posedge clk);
        for (v = 0; v < n; v = v+1) begin
            base = v*65;
            for (k = 0; k < 16; k = k+1) begin
                @(posedge clk);
                in_feature_addr <= k;
                in_feature_data <= vec[base+k];
                in_feature_we <= 1;
            end
            @(posedge clk);
            in_feature_we <= 0;
            start <= 1;
            @(posedge clk);
            start <= 0;
            ticks = 0;
            #1;
            while (done !== 1'b1 && ticks < 10000) begin
                @(posedge clk); #1;
                ticks = ticks+1;
            end
            if (done !== 1'b1) $fatal(1, "Timeout vektor %0d", v);
            for (k = 0; k < 32; k = k+1)
                if (uut.h1_buf[k] !== vec[base+16+k])
                    $fatal(1, "H1 beda/X: vektor %0d neuron %0d", v, k);
            for (k = 0; k < 16; k = k+1)
                if (uut.h2_buf[k] !== vec[base+48+k])
                    $fatal(1, "H2 beda/X: vektor %0d neuron %0d", v, k);
            if (prediction_out !== vec[base+64])
                $fatal(1, "Output beda/X: vektor %0d", v);
            if (cycles_out !== 16'd309)
                $fatal(1, "Siklus beda/X: vektor %0d", v);
            $display("OUTLOG %0d %0d %0d", v, prediction_out, cycles_out);
            while (busy === 1'b1) @(posedge clk);
        end
        $display("RESULT PASS vectors=%0d", n);
        $finish;
    end
endmodule
