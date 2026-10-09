`timescale 1ns/1ps

// Phase-1 control shell. Defaults describe a toy graph, not the gross code.
module window_decoder_ctrl #(
    parameter integer W = 3,
    parameter integer C = 1,
    parameter integer M = 2,
    parameter integer N_ERRORS = 4,
    parameter integer K = 2
) (
    input  logic clk,
    input  logic rst_n,
    input  logic detector_valid,
    output logic detector_ready,
    input  logic [M-1:0] detector_data,
    input  logic [N_ERRORS-1:0] cfg_commit_mask,
    input  logic [W*M-1:0] cfg_convergence_mask,

    output logic decode_req_valid,
    input  logic decode_req_ready,
    output logic [W*M-1:0] decode_detectors,
    output logic [W*M-1:0] decode_convergence_mask,
    input  logic decode_rsp_valid,
    output logic decode_rsp_ready,
    input  logic decode_success,
    input  logic [N_ERRORS-1:0] decode_errors,

    output logic effects_req_valid,
    input  logic effects_req_ready,
    output logic [N_ERRORS-1:0] committed_errors,
    input  logic effects_rsp_valid,
    output logic effects_rsp_ready,
    input  logic [M-1:0] effects_carry,
    input  logic [K-1:0] effects_frame_delta,

    output logic commit_valid,
    input  logic commit_ready,
    output logic commit_success,
    output logic [K-1:0] commit_frame,
    output logic [K-1:0] logical_frame,
    output logic [31:0] window_start,
    output logic busy,
    output logic failed
);
    localparam integer COUNT_BITS = $clog2(W+1);
    typedef enum logic [2:0] {
        FILL, DECODE_REQ, DECODE_WAIT, EFFECTS_REQ,
        EFFECTS_WAIT, REPORT, HALTED
    } state_t;
    state_t state;
    logic [W*M-1:0] history;
    logic [COUNT_BITS-1:0] filled;
    logic [M-1:0] carry, next_carry;
    logic [K-1:0] frame_delta;
    logic [N_ERRORS-1:0] commit_mask;

    initial begin
        if (W < 2 || C < 1 || C >= W || M < 1 || N_ERRORS < 1 || K < 1)
            $fatal(1, "Invalid window decoder parameters");
    end

    assign detector_ready = rst_n && state == FILL;
    assign decode_req_valid = rst_n && state == DECODE_REQ;
    assign decode_rsp_ready = rst_n && state == DECODE_WAIT;
    assign effects_req_valid = rst_n && state == EFFECTS_REQ;
    assign effects_rsp_ready = rst_n && state == EFFECTS_WAIT;
    assign commit_valid = rst_n && state == REPORT;
    assign commit_success = !failed;
    assign commit_frame = logical_frame ^ frame_delta;
    assign busy = rst_n && state != FILL && state != HALTED;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= FILL;
            history <= '0;
            filled <= '0;
            carry <= '0;
            next_carry <= '0;
            frame_delta <= '0;
            commit_mask <= '0;
            decode_detectors <= '0;
            decode_convergence_mask <= '0;
            committed_errors <= '0;
            logical_frame <= '0;
            window_start <= '0;
            failed <= 1'b0;
        end else begin
            case (state)
                FILL: if (detector_valid && detector_ready) begin
                    history[filled*M +: M] <= detector_data;
                    filled <= filled + 1'b1;
                    if (filled == COUNT_BITS'(W-1)) begin
                        // Keep raw history intact: carry affects this request only.
                        decode_detectors <= history;
                        decode_detectors[(W-1)*M +: M] <= detector_data;
                        decode_detectors[0 +: M] <= history[0 +: M] ^ carry;
                        decode_convergence_mask <= cfg_convergence_mask;
                        commit_mask <= cfg_commit_mask;
                        state <= DECODE_REQ;
                    end
                end
                DECODE_REQ: if (decode_req_ready) state <= DECODE_WAIT;
                DECODE_WAIT: if (decode_rsp_valid) begin
                    if (decode_success) begin
                        committed_errors <= decode_errors & commit_mask;
                        state <= EFFECTS_REQ;
                    end else begin
                        committed_errors <= '0;
                        frame_delta <= '0;
                        failed <= 1'b1;
                        state <= REPORT;
                    end
                end
                EFFECTS_REQ: if (effects_req_ready) state <= EFFECTS_WAIT;
                EFFECTS_WAIT: if (effects_rsp_valid) begin
                    next_carry <= effects_carry;
                    frame_delta <= effects_frame_delta;
                    state <= REPORT;
                end
                REPORT: if (commit_ready) begin
                    if (failed) state <= HALTED;
                    else begin
                        logical_frame <= commit_frame;
                        carry <= next_carry;
                        history <= history >> (C*M);
                        filled <= COUNT_BITS'(W-C);
                        window_start <= window_start + 32'(C);
                        frame_delta <= '0;
                        state <= FILL;
                    end
                end
                HALTED: state <= HALTED;
                default: state <= HALTED;
            endcase
        end
    end
endmodule
