`timescale 1ns/1ps

// Window controller plus actual effects arithmetic. Decoder remains external.
module window_decoder_top #(
    parameter integer W = 12,
    parameter integer C = 8,
    parameter integer M = 72,
    parameter integer N_ERRORS = 8640,
    parameter integer K = 12,
    parameter CARRY_FILE = "",
    parameter FRAME_FILE = "",
    parameter COMMIT_FILE = "",
    parameter CONVERGENCE_FILE = "",
    parameter STARTUP_ACTIVE_FILE = "",
    parameter BULK_ACTIVE_FILE = ""
) (
    input logic clk, rst_n,
    input logic detector_valid,
    output logic detector_ready,
    input logic [M-1:0] detector_data,
    output logic decode_req_valid,
    input logic decode_req_ready,
    output logic [W*M-1:0] decode_detectors,
    output logic [W*M-1:0] decode_convergence_mask,
    output logic [N_ERRORS-1:0] decode_active_mask,
    output logic startup_profile,
    input logic decode_rsp_valid,
    output logic decode_rsp_ready,
    input logic decode_success,
    input logic [N_ERRORS-1:0] decode_errors,
    output logic commit_valid,
    input logic commit_ready,
    output logic commit_success,
    output logic [K-1:0] commit_frame,
    output logic [K-1:0] logical_frame,
    output logic [31:0] window_start,
    output logic busy, failed
);
    logic [N_ERRORS-1:0] commit_mask_rom [0:0];
    logic [N_ERRORS-1:0] startup_active_rom [0:0];
    logic [N_ERRORS-1:0] bulk_active_rom [0:0];
    logic [W*M-1:0] convergence_rom [0:0];
    logic effects_req_valid, effects_req_ready, effects_rsp_valid, effects_rsp_ready;
    logic [N_ERRORS-1:0] committed_errors;
    logic [M-1:0] effects_carry;
    logic [K-1:0] effects_frame_delta;
    logic decoder_result_ok;

    initial begin
        if (COMMIT_FILE == "" || CONVERGENCE_FILE == "" ||
            STARTUP_ACTIVE_FILE == "" || BULK_ACTIVE_FILE == "")
            $fatal(1, "window_decoder_top requires mask files");
        $readmemh(COMMIT_FILE, commit_mask_rom);
        $readmemh(CONVERGENCE_FILE, convergence_rom);
        $readmemh(STARTUP_ACTIVE_FILE, startup_active_rom);
        $readmemh(BULK_ACTIVE_FILE, bulk_active_rom);
    end
    assign decode_active_mask = startup_profile ? startup_active_rom[0] : bulk_active_rom[0];
    // A decoder must not invent a fault absent from the selected profile.
    assign decoder_result_ok = decode_success && ((decode_errors & ~decode_active_mask) == '0);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) startup_profile <= 1'b1;
        else if (commit_valid && commit_ready && commit_success) startup_profile <= 1'b0;
    end

    window_decoder_ctrl #(.W(W), .C(C), .M(M), .N_ERRORS(N_ERRORS), .K(K)) controller (
        .cfg_commit_mask(commit_mask_rom[0] & decode_active_mask),
        .cfg_convergence_mask(convergence_rom[0]), .decode_success(decoder_result_ok), .*
    );
    window_effects #(.N_ERRORS(N_ERRORS), .M(M), .K(K),
                     .CARRY_FILE(CARRY_FILE), .FRAME_FILE(FRAME_FILE)) effects (
        .clk, .rst_n, .req_valid(effects_req_valid), .req_ready(effects_req_ready),
        .committed_errors, .rsp_valid(effects_rsp_valid), .rsp_ready(effects_rsp_ready),
        .carry(effects_carry), .frame_delta(effects_frame_delta)
    );
endmodule
