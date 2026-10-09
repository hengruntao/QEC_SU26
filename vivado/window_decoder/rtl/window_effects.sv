`timescale 1ns/1ps

// Fixed GF(2) matrix products. Registered result with one elastic response slot.
module window_effects #(
    parameter integer N_ERRORS = 4,
    parameter integer M = 2,
    parameter integer K = 2,
    parameter CARRY_FILE = "",
    parameter FRAME_FILE = ""
) (
    input logic clk, rst_n,
    input logic req_valid,
    output logic req_ready,
    input logic [N_ERRORS-1:0] committed_errors,
    output logic rsp_valid,
    input logic rsp_ready,
    output logic [M-1:0] carry,
    output logic [K-1:0] frame_delta
);
    logic [N_ERRORS-1:0] carry_rows [0:M-1];
    logic [N_ERRORS-1:0] frame_rows [0:K-1];
    initial begin
        if (N_ERRORS < 1 || M < 1 || K < 1 || CARRY_FILE == "" || FRAME_FILE == "")
            $fatal(1, "window_effects requires positive dimensions and matrix files");
        $readmemh(CARRY_FILE, carry_rows);
        $readmemh(FRAME_FILE, frame_rows);
    end
    assign req_ready = rst_n && (!rsp_valid || rsp_ready);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rsp_valid <= 1'b0;
            carry <= '0;
            frame_delta <= '0;
        end else if (req_ready) begin
            rsp_valid <= req_valid;
            if (req_valid) begin
                for (integer i = 0; i < M; i = i + 1)
                    carry[i] <= ^(committed_errors & carry_rows[i]);
                for (integer i = 0; i < K; i = i + 1)
                    frame_delta[i] <= ^(committed_errors & frame_rows[i]);
            end
        end
    end
endmodule
