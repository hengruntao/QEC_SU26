`timescale 1ns/1ps
module window_effects_tb;
    parameter integer E = 8640, M = 72, K = 12, COUNT = 8706;
    parameter DIR = ".";
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0, req_valid = 0, req_ready, rsp_valid, rsp_ready = 0;
    logic [E-1:0] committed_errors = '0;
    logic [M-1:0] carry;
    logic [K-1:0] frame_delta;
    logic [E-1:0] vectors [0:COUNT-1];
    logic [M-1:0] expected_carry [0:COUNT-1];
    logic [K-1:0] expected_frame [0:COUNT-1];
    integer checks = 0;
    window_effects #(.N_ERRORS(E), .M(M), .K(K),
        .CARRY_FILE({DIR,"/carry.mem"}), .FRAME_FILE({DIR,"/frame.mem"})) dut (.*);
    task automatic check(input logic condition, input string message);
        if (condition !== 1'b1) $fatal(1, "%s", message);
        checks = checks + 1;
    endtask
    initial begin
        $readmemh({DIR,"/unit_errors.mem"}, vectors);
        $readmemh({DIR,"/unit_carry.mem"}, expected_carry);
        $readmemh({DIR,"/unit_frame.mem"}, expected_frame);
        repeat (2) @(negedge clk);
        rst_n = 1;
        for (integer i = 0; i < COUNT; i = i + 1) begin
            @(negedge clk);
            check(req_ready, "effects request ready");
            committed_errors = vectors[i];
            req_valid = 1;
            @(negedge clk);
            req_valid = 0;
            check(rsp_valid && carry === expected_carry[i] && frame_delta === expected_frame[i],
                  "effects result matches independent sparse reference");
            if (i % 509 == 0) begin
                req_valid = 1;
                committed_errors = ~vectors[i];
                repeat (3) begin
                    @(negedge clk);
                    check(!req_ready && rsp_valid && carry === expected_carry[i] && frame_delta === expected_frame[i],
                          "stalled response stable; new input not accepted");
                end
                req_valid = 0;
            end
            rsp_ready = 1;
            @(negedge clk);
            rsp_ready = 0;
            check(!rsp_valid, "one response per request");
        end
        // Consume one result and accept its successor on the same clock edge.
        req_valid = 1;
        rsp_ready = 1;
        committed_errors = vectors[0];
        @(negedge clk);
        check(rsp_valid && carry === expected_carry[0] && frame_delta === expected_frame[0], "back-to-back first");
        committed_errors = vectors[1];
        @(negedge clk);
        check(rsp_valid && carry === expected_carry[1] && frame_delta === expected_frame[1], "back-to-back second");
        req_valid = 0;
        rsp_ready = 0;
        rst_n = 0;
        @(negedge clk);
        check(!rsp_valid && !req_ready && carry == 0 && frame_delta == 0, "reset cancels held result");
        rst_n = 1;
        @(negedge clk);
        check(req_ready && !rsp_valid, "reset recovery");
        $display("PASS effects: %0d vectors, %0d checks", COUNT, checks);
        $finish;
    end
    initial begin
        #2000000;
        $fatal(1, "effects test timeout");
    end
endmodule
