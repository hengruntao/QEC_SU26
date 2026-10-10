`timescale 1ns/1ps
// tb_relay_bp.sv
// Self-checking testbench for relay_bp_top.
// Reads test vectors produced by relay_bp_model.py and compares every output
// against the bit-exact model's prediction.

    module tb_relay_bp;
    localparam int MAX_VEC = 1024;          // upper bound on vectors per run
    localparam int TIMEOUT_MARGIN = 1000;   // extra cycles allowed past the expected count

    // ---------------- DUT signals ----------------
    logic         clk = 1'b0;
    logic         rst_n;
    logic [71:0]  syndrome;
    logic [3:0]   lambda_0 [0:143];
    logic [143:0] e_hat;
    logic         converged;
    logic         done;
    logic [6:0]   iter_count;
    logic [9:0]   leg_count;

    always #5 clk = ~clk;                   // 100 MHz, period is irrelevant to correctness

    relay_bp_top dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .syndrome   (syndrome),
        .lambda_0   (lambda_0),
        .e_hat      (e_hat),
        .converged  (converged),
        .done       (done),
        .iter_count (iter_count),
        .leg_count  (leg_count)
    );

    // ---------------- vector storage ----------------
    logic [31:0]  nvec_mem   [0:0];
    logic [71:0]  syn_mem    [0:MAX_VEC-1];
    logic [575:0] lam_mem    [0:MAX_VEC-1];  // lambda_0[j] = word[4j +: 4]
    logic [143:0] ehat_mem   [0:MAX_VEC-1];
    logic [0:0]   conv_mem   [0:MAX_VEC-1];
    logic [6:0]   iter_mem   [0:MAX_VEC-1];
    logic [9:0]   leg_mem    [0:MAX_VEC-1];
    logic [31:0]  cyc_mem    [0:MAX_VEC-1];

    int n_vec, n_pass, n_fail, cycles;
    bit ok;

    initial begin
        $readmemh("nvec.mem",       nvec_mem);
        $readmemh("syndrome.mem",   syn_mem);
        $readmemh("lambda.mem",     lam_mem);
        $readmemh("exp_ehat.mem",   ehat_mem);
        $readmemh("exp_conv.mem",   conv_mem);
        $readmemh("exp_iter.mem",   iter_mem);
        $readmemh("exp_leg.mem",    leg_mem);
        $readmemh("exp_cycles.mem", cyc_mem);
        n_vec = int'(nvec_mem[0]);
        n_pass = 0;
        n_fail = 0;
        $display("Running %0d vectors", n_vec);

        for (int v = 0; v < n_vec; v++) begin
            // apply inputs while in reset
            rst_n    = 1'b0;
            syndrome = syn_mem[v];
            for (int j = 0; j < 144; j++)
                lambda_0[j] = lam_mem[v][4*j +: 4];
            repeat (2) @(posedge clk);
            @(negedge clk);
            rst_n = 1'b1;

            // count rising edges until done
            cycles = 0;
            while (!done && cycles < cyc_mem[v] + TIMEOUT_MARGIN) begin
                @(posedge clk);
                cycles++;
                @(negedge clk);
            end

            ok = 1'b1;
            if (!done) begin
                $display("FAIL vec %0d: timeout after %0d cycles (expected %0d)", v, cycles, cyc_mem[v]);
                ok = 1'b0;
            end else begin
                if (converged !== conv_mem[v][0]) begin
                    $display("FAIL vec %0d: converged=%0b expected %0b", v, converged, conv_mem[v][0]);
                    ok = 1'b0;
                end
                if (e_hat !== ehat_mem[v]) begin
                    $display("FAIL vec %0d: e_hat mismatch", v);
                    $display("       got      %036h", e_hat);
                    $display("       expected %036h", ehat_mem[v]);
                    ok = 1'b0;
                end
                if (iter_count !== iter_mem[v]) begin
                    $display("FAIL vec %0d: iter_count=%0d expected %0d", v, iter_count, iter_mem[v]);
                    ok = 1'b0;
                end
                if (leg_count !== leg_mem[v]) begin
                    $display("FAIL vec %0d: leg_count=%0d expected %0d", v, leg_count, leg_mem[v]);
                    ok = 1'b0;
                end
                if (cycles != cyc_mem[v]) begin
                    $display("FAIL vec %0d: took %0d cycles, expected %0d", v, cycles, cyc_mem[v]);
                    ok = 1'b0;
                end
            end

            if (ok) begin
                n_pass++;
                $display("pass vec %0d  legs=%0d iter=%0d cycles=%0d", v, leg_count, iter_count, cycles);
            end else begin
                n_fail++;
            end
        end

        $display("--------------------------------------------");
        $display("%0d / %0d vectors passed, %0d failed", n_pass, n_vec, n_fail);
        $display("--------------------------------------------");
        $finish;
    end

endmodule
