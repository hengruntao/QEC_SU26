`timescale 1ns/1ps
module window_relay_top #(
    parameter integer W=12,C=8,M=72,N_ERRORS=8640,K=12,DC=35,DV=6,
    parameter integer T0=80,TR=60,MAX_LEGS=600,NUM_SOL=5,
    parameter CARRY_FILE="",FRAME_FILE="",COMMIT_FILE="",CONVERGENCE_FILE="",
    parameter STARTUP_ACTIVE_FILE="",BULK_ACTIVE_FILE="",
    parameter IDX_FILE="",PORT_FILE="",START_PRIOR_FILE="",BULK_PRIOR_FILE=""
) (
    input logic clk,rst_n,detector_valid,
    output logic detector_ready,
    input logic [M-1:0] detector_data,
    output logic commit_valid,
    input logic commit_ready,
    output logic commit_success,
    output logic [K-1:0] commit_frame,logical_frame,
    output logic [31:0] window_start,
    output logic busy,failed,
    output logic [6:0] iter_count,
    output logic [9:0] leg_count
);
    logic decode_req_valid,decode_req_ready,decode_rsp_valid,decode_rsp_ready,decode_success;
    logic [W*M-1:0] decode_detectors,decode_convergence_mask;
    logic [N_ERRORS-1:0] decode_active_mask,decode_errors;
    logic startup_profile;
    window_decoder_top #(.W(W),.C(C),.M(M),.N_ERRORS(N_ERRORS),.K(K),
        .CARRY_FILE(CARRY_FILE),.FRAME_FILE(FRAME_FILE),.COMMIT_FILE(COMMIT_FILE),
        .CONVERGENCE_FILE(CONVERGENCE_FILE),.STARTUP_ACTIVE_FILE(STARTUP_ACTIVE_FILE),
        .BULK_ACTIVE_FILE(BULK_ACTIVE_FILE)) window_unit (.*);
    relay_window_adapter #(.D(W*M),.V(N_ERRORS),.DC(DC),.DV(DV),.T0(T0),.TR(TR),
        .MAX_LEGS(MAX_LEGS),.NUM_SOL(NUM_SOL),.IDX_FILE(IDX_FILE),.PORT_FILE(PORT_FILE),
        .START_PRIOR_FILE(START_PRIOR_FILE),.BULK_PRIOR_FILE(BULK_PRIOR_FILE)) decoder (
        .clk,.rst_n,.req_valid(decode_req_valid),.req_ready(decode_req_ready),
        .detectors(decode_detectors),.convergence_mask(decode_convergence_mask),
        .active_mask(decode_active_mask),.startup_profile,.rsp_valid(decode_rsp_valid),
        .rsp_ready(decode_rsp_ready),.success(decode_success),.errors(decode_errors),
        .iter_count,.leg_count
    );
endmodule
