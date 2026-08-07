`timescale 1ns/1ps

module vnu_tb;

    localparam int NUM_TESTS = 344;
    localparam int IN_W      = 36;
    localparam int OUT_W     = 24;

    logic        clk;
    logic        rst_n;
    logic        init;
    logic        new_leg;
    logic [3:0]  lambda_0;
    logic [9:0]  mu_in [3];

    logic [4:0]  nu_out [3];
    logic [4:0]  marginal;
    logic        e_hat;

    logic [IN_W-1:0]  input_mem  [0:NUM_TESTS-1];
    logic [OUT_W-1:0] output_mem [0:NUM_TESTS-1];

    vnu dut (
        .clk(clk),
        .rst_n(rst_n),
        .init(init),
        .new_leg(new_leg),
        .lambda_0(lambda_0),
        .mu_in(mu_in),
        .nu_out(nu_out),
        .marginal(marginal),
        .e_hat(e_hat)
    );

    always #5 clk = ~clk;

    initial begin : main
        logic        exp_e_hat;
        logic [4:0]  exp_marginal;
        logic [4:0]  exp_nu_out [3];
        bit          test_failed;
        int          pass_count;
        int          fail_count;
        int          nu_mm;
        int          marg_mm;
        int          ehat_mm;

        clk       = 0;
        rst_n     = 0;
        init      = 0;
        new_leg   = 0;
        lambda_0  = 4'd0;
        mu_in[0]  = 10'd0;
        mu_in[1]  = 10'd0;
        mu_in[2]  = 10'd0;
        pass_count = 0;
        fail_count = 0;
        nu_mm      = 0;
        marg_mm    = 0;
        ehat_mm    = 0;

        $readmemh("vnu_test_vectors_int4_input.hex",  input_mem);
        $readmemh("vnu_test_vectors_int4_output.hex", output_mem);
        if (^input_mem[0] === 1'bx) begin
            $display("ERROR: input hex file failed to load. Aborting.");
            $finish;
        end
        if (^output_mem[0] === 1'bx) begin
            $display("ERROR: output hex file failed to load. Aborting.");
            $finish;
        end
        
        $display("input_mem[0]  = %h (expect 000000000)", input_mem[0]);
        $display("output_mem[0] = %h (expect 100000)",    output_mem[0]);

        #20;
        rst_n = 1;
        #10;

        for (int i = 0; i < NUM_TESTS; i++) begin
            lambda_0 = input_mem[i][33:30];
            mu_in[0] = input_mem[i][9:0];
            mu_in[1] = input_mem[i][19:10];
            mu_in[2] = input_mem[i][29:20];

            exp_e_hat     = output_mem[i][20];
            exp_marginal  = output_mem[i][19:15];
            exp_nu_out[2] = output_mem[i][14:10];
            exp_nu_out[1] = output_mem[i][9:5];
            exp_nu_out[0] = output_mem[i][4:0];

            #10;

            test_failed = 0;

            if (e_hat !== exp_e_hat) begin
                $display("[%0d] e_hat: expected %b, got %b",
                         i, exp_e_hat, e_hat);
                ehat_mm++;
                test_failed = 1;
            end

            if (marginal !== exp_marginal) begin
                $display("[%0d] marginal: expected %b (%0d), got %b (%0d)",
                         i, exp_marginal, $signed({exp_marginal[4], {3'b0, exp_marginal[3:0]}}),
                         marginal, $signed({marginal[4], {3'b0, marginal[3:0]}}));
                marg_mm++;
                test_failed = 1;
            end

            for (int g = 0; g < 3; g++) begin
                if (nu_out[g] !== exp_nu_out[g]) begin
                    $display("[%0d] nu_out[%0d]: expected %b, got %b",
                             i, g, exp_nu_out[g], nu_out[g]);
                    nu_mm++;
                    test_failed = 1;
                end
            end

            if (test_failed) fail_count++;
            else             pass_count++;
        end

        $display("");
        $display("=========================================");
        $display("VNU Verification Summary");
        $display("=========================================");
        $display("Total tests:           %0d", NUM_TESTS);
        $display("Passed:                %0d", pass_count);
        $display("Failed:                %0d", fail_count);
        $display("  e_hat mismatches:    %0d", ehat_mm);
        $display("  marginal mismatches: %0d", marg_mm);
        $display("  nu_out mismatches:   %0d", nu_mm);
        $display("=========================================");

        if (fail_count == 0)
            $display("*** ALL %0d TESTS PASSED ***", NUM_TESTS);
        else
            $display("*** %0d OF %0d TESTS FAILED ***", fail_count, NUM_TESTS);

        $finish;
    end

endmodule