`timescale 1ns/1ps

module window_effects #(
    parameter int N_FAULTS = 8785,
    parameter int M = 72,
    parameter int K = 12
)(
    input  logic                clk,
    input  logic                rst_n,
    input  logic [N_FAULTS-1:0] e_hat,
    input  logic                converged,
    input  logic                in_valid,
    output logic                in_ready,
    output logic [M-1:0]        carry,
    output logic [K-1:0]        frame,
    output logic                out_success,
    output logic                out_valid,
    input  logic                out_ready
);

    typedef enum logic [1:0]{
        IDLE,
        CALCULATE,
        RESPOND
    } state_t;

state_t state;

logic [N_FAULTS-1:0] e_hat_q;
logic converged_q;
logic accept_input;
logic [K-1:0] delta_frame;
logic [M-1:0] carry_effect;
logic effects_ready;
logic [N_FAULTS-1:0] e_com;

assign in_ready = rst_n && (state == IDLE);
assign accept_input = in_valid && in_ready;

always_ff @( posedge clk or negedge rst_n ) begin
    if(!rst_n) begin
        e_hat_q <= '0;
        converged_q <= 1'b0;
    end else if(accept_input) begin
        e_hat_q <= e_hat;
        converged_q <= converged;
    end
end

logic calculation_done;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state<=IDLE;
    end else begin
        case(state)
            IDLE: begin
                if(accept_input)
                    state <= CALCULATE;
            end

            CALCULATE: begin
                if(calculation_done)
                    state<= RESPOND;
            end

            RESPOND: begin
                if (out_ready)
                    state<= IDLE;
            end

            default: state<= IDLE;
        endcase
    end
end

assign out_valid = rst_n && (state == RESPOND);
assign calculation_done = (state == CALCULATE) && (!converged_q || effects_ready);

always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        frame <= '0;
        carry <= '0;
        out_success <= 1'b0;
    end 
    else if (calculation_done) begin
        out_success <= converged_q;

        if(converged_q) begin
            frame <= frame ^ delta_frame;
            carry <= carry_effect;
        end else begin 
            carry <= '0;
        end
    end
end

// Mathematical ops start e_com = e_hat AND commit_mask
assign e_com = e_hat_q & window_effects_pkg::COMMIT_MASK;

function automatic logic gf2_parity(
    input logic [N_FAULTS-1:0] faults,
    input logic [N_FAULTS-1:0] matrix_row
);
    gf2_parity = ^(faults & matrix_row);

endfunction

assign delta_frame[0] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_0);
assign delta_frame[1] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_1);
assign delta_frame[2] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_2);
assign delta_frame[3] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_3);
assign delta_frame[4] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_4);
assign delta_frame[5] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_5);
assign delta_frame[6] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_6);
assign delta_frame[7] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_7);
assign delta_frame[8] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_8);
assign delta_frame[9] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_9);
assign delta_frame[10] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_10);
assign delta_frame[11] =
    gf2_parity(e_com, window_effects_pkg::FRAME_ROW_11);


//loop does 72 parallel parity calcs
generate
    for (genvar r = 0; r<M; r++) begin: gen_carry
        assign carry_effect[r] = gf2_parity( 
            e_com,
            window_effects_pkg::CARRY_ROWS[r]
        );
    end
endgenerate

assign effects_ready = (state == CALCULATE) && converged_q;

endmodule
