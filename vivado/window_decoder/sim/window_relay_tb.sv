`timescale 1ns/1ps
`include "qec_paths.svh"
module window_relay_tb;
    localparam W=12,C=8,M=72,V=8640,D=864,K=12,WINDOWS=3;
    logic clk=0;
    always #(`QEC_CLOCK_PERIOD_NS/2.0) clk=~clk;
    logic rst_n=0,detector_valid=0,detector_ready,commit_valid,commit_ready=0;
    logic commit_success,busy,failed;
    logic [M-1:0] detector_data=0,raw[W+(WINDOWS-1)*C],carry=0,next_carry;
    logic [K-1:0] commit_frame,logical_frame,frame=0,delta;
    logic [31:0] window_start,starts[WINDOWS];
    logic [6:0] iter_count;
    logic [9:0] leg_count;
    logic [V-1:0] h[D],a[K],carry_rows[M],committed,cm[1],held_errors;
    logic [D-1:0] expected_window,history[WINDOWS];
    logic [0:0] expected_success[WINDOWS];
    integer requests=0,nonzero=0,retried=0;

    // Two successful legs are possible within this deliberately short smoke run.
    // NUM_SOL=3 reflects the established core's inherited stop-count convention.
    window_decoder_vivado_top #(.T0(8),.TR(6),.MAX_LEGS(1),.NUM_SOL(3)) dut (.*);

    always @(posedge clk) if(rst_n && dut.impl.decode_req_valid && dut.impl.decode_req_ready) begin
        if(requests>=WINDOWS) $fatal(1,"unexpected extra request");
        expected_window=history[requests];
        expected_window[0+:M]^=carry;
        if(dut.impl.decode_detectors!==expected_window) $fatal(1,"window/carry request mismatch");
        if(dut.impl.startup_profile !== (requests==0)) $fatal(1,"startup/bulk transition mismatch");
        requests++;
    end

    initial begin
        $readmemh({`QEC_REF_DIR,"/detectors.mem"},raw);
        $readmemh({`QEC_REF_DIR,"/raw_windows.mem"},history);
        $readmemh({`QEC_REF_DIR,"/expected_success.mem"},expected_success);
        $readmemh({`QEC_REF_DIR,"/expected_window_start.mem"},starts);
        $readmemh({`QEC_REF_DIR,"/h_reference.mem"},h);
        $readmemh({`QEC_REF_DIR,"/a_reference.mem"},a);
        $readmemh({`QEC_REF_DIR,"/carry_reference.mem"},carry_rows);
        $readmemh({`QEC_REF_DIR,"/commit_reference.mem"},cm);
        repeat(2) @(negedge clk); rst_n=1;
        for(int win=0;win<WINDOWS;win++) begin
            for(int r=(win==0 ? 0 : W+(win-1)*C);r<W+win*C;r++) begin
                @(negedge clk); detector_data=raw[r]; detector_valid=1;
                while(!detector_ready) @(negedge clk);
                @(negedge clk); detector_valid=0;
            end
            wait(dut.impl.decode_rsp_valid); @(negedge clk);
            if(dut.impl.decode_success!==expected_success[win][0]) $fatal(1,"decode success mismatch win %d",win);
            if((dut.impl.decode_errors & ~dut.impl.decode_active_mask)!=0) $fatal(1,"inactive correction");
            for(int r=0;r<C*M;r++)
                if((^(h[r]&dut.impl.decode_errors))!==expected_window[r]) $fatal(1,"returned correction fails check %d",r);
            if(dut.impl.decode_errors!=0) nonzero++;
            if(leg_count>0) retried++;
            held_errors=dut.impl.decode_errors;
            committed=held_errors & cm[0] & dut.impl.decode_active_mask;
            delta=0; next_carry=0;
            for(int r=0;r<K;r++) delta[r]=^(a[r]&committed);
            for(int r=0;r<M;r++) next_carry[r]=^(carry_rows[r]&committed);
            frame^=delta;
            wait(commit_valid); @(negedge clk);
            repeat(4) begin
                if(!commit_valid || !commit_success || commit_frame!==frame) $fatal(1,"held commit mismatch");
                @(negedge clk);
            end
            commit_ready=1; @(negedge clk); commit_ready=0; carry=next_carry;
            if(window_start!==starts[win] || logical_frame!==frame || failed) $fatal(1,"accepted commit mismatch");
        end
        if(nonzero==0 || retried!=WINDOWS || requests!=WINDOWS) $fatal(1,"insufficient correction/retry coverage");
        rst_n=0; @(negedge clk);
        if(logical_frame!==0 || window_start!==0 || failed || commit_valid) $fatal(1,"session reset mismatch");
        $display("PASS packaged window decoder: 3 windows, nonzero corrections, retries, masks, frame/carry, commit stalls, reset");
        $finish;
    end
    initial begin #100000000; $fatal(1,"window test timeout"); end
endmodule
