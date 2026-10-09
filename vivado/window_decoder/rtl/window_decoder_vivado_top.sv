`timescale 1ns/1ps
`include "qec_paths.svh"
// Configuration/wiring only; arithmetic remains in the established RTL hierarchy.
module window_decoder_vivado_top #(
    parameter integer T0=80,TR=60,MAX_LEGS=600,NUM_SOL=5
) (
    input logic clk,rst_n,detector_valid,
    output logic detector_ready,
    input logic [71:0] detector_data,
    output logic commit_valid,
    input logic commit_ready,
    output logic commit_success,
    output logic [11:0] commit_frame,logical_frame,
    output logic [31:0] window_start,
    output logic busy,failed,
    output logic [6:0] iter_count,
    output logic [9:0] leg_count
);
    window_relay_top #(.T0(T0),.TR(TR),.MAX_LEGS(MAX_LEGS),.NUM_SOL(NUM_SOL),
        .IDX_FILE({`QEC_ROM_DIR,"/cnu_to_vnu_idx.mem"}),
        .PORT_FILE({`QEC_ROM_DIR,"/cnu_to_vnu_port.mem"}),
        .START_PRIOR_FILE({`QEC_ROM_DIR,"/startup_prior.mem"}),
        .BULK_PRIOR_FILE({`QEC_ROM_DIR,"/bulk_prior.mem"}),
        .CARRY_FILE({`QEC_ROM_DIR,"/carry_rows.mem"}),
        .FRAME_FILE({`QEC_ROM_DIR,"/frame_rows.mem"}),
        .COMMIT_FILE({`QEC_ROM_DIR,"/commit_mask.mem"}),
        .CONVERGENCE_FILE({`QEC_ROM_DIR,"/convergence_mask.mem"}),
        .STARTUP_ACTIVE_FILE({`QEC_ROM_DIR,"/startup_active_mask.mem"}),
        .BULK_ACTIVE_FILE({`QEC_ROM_DIR,"/bulk_active_mask.mem"})) impl (.*);
endmodule
