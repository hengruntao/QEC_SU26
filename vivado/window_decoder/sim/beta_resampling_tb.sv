`timescale 1ns/1ps
`include "qec_paths.svh"
module beta_resampling_tb;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=0,init=0,en=0,new_leg=0;
    logic [3:0] lambda_0=7;
    logic [9:0] mu[1];
    wire [4:0] nu[1],marginal;
    wire decision;
    vnu #(.DEG(1),.LFSR_SEED(8'hA5)) unit_vnu (
        .clk,.rst_n,.init,.en,.new_leg,.lambda_0,.mu_in(mu),
        .nu_out(nu),.marginal,.e_hat(decision)
    );

    logic core_rst_n=0;
    logic [1:0] syndrome=0;
    logic [3:0] priors[1];
    wire [0:0] errors;
    wire done,converged;
    wire [6:0] iter_count;
    wire [9:0] leg_count;
    relay_bp_top #(.T0(2),.Tr(3),.MAX_LEGS(2),.NUM_SOL(5),
        .N_CHECKS(2),.N_VARS(1),.CN_DEG(1),.VN_DEG(1),.WINDOW_MODE(1),
        .IDX_FILE({`QEC_BETA_DIR,"/cnu_to_vnu_idx.mem"}),
        .PORT_FILE({`QEC_BETA_DIR,"/cnu_to_vnu_port.mem"})) core (
        .clk,.rst_n(core_rst_n),.syndrome,.lambda_0(priors),
        .convergence_mask(2'b11),.active_mask(1'b1),.e_hat(errors),
        .converged,.done,.iter_count,.leg_count
    );

    task automatic check_retry_path(input logic [1:0] target,input logic expect_success);
        integer samples,changes;
        logic boundary,update;
        logic [3:0] before_beta,expected_beta;
        logic [7:0] before_rng,expected_rng;
        logic signed [7:0] before_memory;
        begin
            core_rst_n=0;
            repeat(2) @(negedge clk);
            syndrome=target; core_rst_n=1; samples=0; changes=0;
            while(!done) begin
                boundary=core.new_leg_pulse; update=core.vnu_en;
                before_beta=core.gen_vnu[0].u_vnu.beta_int;
                before_rng=core.gen_vnu[0].u_vnu.lfsr;
                before_memory=core.gen_vnu[0].u_vnu.M_j;
                expected_beta=boundary ? 4'd3+{1'b0,before_rng[2:0]} : before_beta;
                expected_rng=update ? {before_rng[6:0],before_rng[7]^before_rng[5]^before_rng[4]^before_rng[3]} : before_rng;
                if(boundary && update) $fatal(1,"test did not exercise separate NEW_LEG state");
                @(posedge clk); #1;
                if(core.gen_vnu[0].u_vnu.beta_int!==expected_beta) $fatal(1,"beta sampling/hold mismatch");
                if(core.gen_vnu[0].u_vnu.lfsr!==expected_rng) $fatal(1,"LFSR advance changed");
                if(boundary) begin
                    samples++;
                    if(expected_beta!=before_beta) changes++;
                    if(core.gen_vnu[0].u_vnu.M_j!==before_memory) $fatal(1,"memory changed at retry boundary");
                end
                @(negedge clk);
            end
            if(samples!=2 || changes==0 || converged!==expect_success || leg_count!=2)
                $fatal(1,"retry path coverage/result mismatch");
        end
    endtask

    initial begin
        mu[0]=0; priors[0]=7;
        repeat(2) @(negedge clk); rst_n=1; init=1;
        @(negedge clk); init=0; en=1; mu[0]=10'h255;
        @(negedge clk); en=0; mu[0]=0;
        if(unit_vnu.M_j!==8'sd2 || unit_vnu.lfsr!==8'h4A || unit_vnu.beta_int!==7)
            $fatal(1,"unexpected existing VNU setup behavior");
        new_leg=1;
        @(negedge clk); new_leg=0;
        if(unit_vnu.beta_int!==5 || unit_vnu.lfsr!==8'h4A || unit_vnu.M_j!==8'sd2)
            $fatal(1,"boundary-only beta sample failed");
        if(unit_vnu.lambda_t!==8'sd5) $fatal(1,"next iteration did not see resampled beta");
        en=1; @(negedge clk); en=0;
        if(unit_vnu.M_j!==8'sd5 || unit_vnu.lfsr!==8'h95 || unit_vnu.beta_int!==5)
            $fatal(1,"first VN update after sampling failed");
        repeat(3) @(negedge clk);
        if(unit_vnu.beta_int!==5 || unit_vnu.lfsr!==8'h95) $fatal(1,"idle state changed");
        rst_n=0; @(negedge clk);
        if(unit_vnu.beta_int!==7 || unit_vnu.lfsr!==8'hA5 || unit_vnu.M_j!==0)
            $fatal(1,"reset policy changed");

        check_retry_path(2'b00,1'b1); // NEW_LEG after successful weight scans.
        check_retry_path(2'b10,1'b0); // Impossible isolated check: iteration exhaustion.
        $display("PASS existing beta control: boundary sampling, first VN use, LFSR/memory hold, success/failure retry paths, reset");
        $finish;
    end
    initial begin #1000000; $fatal(1,"timeout"); end
endmodule
