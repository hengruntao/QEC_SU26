`timescale 1ns/1ps
// Protocol/profile wrapper only. All BP arithmetic runs in the established core.
module relay_window_adapter #(
    parameter integer D=864,V=8640,DC=35,DV=6,
    parameter integer T0=80,TR=60,MAX_LEGS=600,NUM_SOL=5,
    parameter IDX_FILE="",PORT_FILE="",START_PRIOR_FILE="",BULK_PRIOR_FILE=""
) (
    input logic clk,rst_n,req_valid,
    output logic req_ready,
    input logic [D-1:0] detectors,convergence_mask,
    input logic [V-1:0] active_mask,
    input logic startup_profile,
    output logic rsp_valid,
    input logic rsp_ready,
    output logic success,
    output logic [V-1:0] errors,
    output logic [6:0] iter_count,
    output logic [9:0] leg_count
);
    typedef enum logic [1:0] {IDLE,START,RUN,RESPONSE} state_t;
    state_t state;
    logic [D-1:0] syndrome_q,mask_q;
    logic [V-1:0] active_q,core_errors;
    logic [3:0] startup_prior[0:V-1],bulk_prior[0:V-1],prior_q[0:V-1];
    logic core_rst_n,core_done,core_success;
    logic [6:0] core_iter;
    logic [9:0] core_leg;
    initial begin
        if (IDX_FILE=="" || PORT_FILE=="" || START_PRIOR_FILE=="" || BULK_PRIOR_FILE=="")
            $fatal(1,"Adapter requires connectivity and externally quantized prior ROMs");
        $readmemh(START_PRIOR_FILE,startup_prior);
        $readmemh(BULK_PRIOR_FILE,bulk_prior);
    end
    assign req_ready = rst_n && state==IDLE;
    assign rsp_valid = rst_n && state==RESPONSE;
    // Restart exactly as a fresh standalone run, including original LFSR seeds.
    assign core_rst_n = rst_n && state==RUN;
    relay_bp_top #(.T0(T0),.Tr(TR),.MAX_LEGS(MAX_LEGS),.NUM_SOL(NUM_SOL),
        .N_CHECKS(D),.N_VARS(V),.CN_DEG(DC),.VN_DEG(DV),.WINDOW_MODE(1),
        .IDX_FILE(IDX_FILE),.PORT_FILE(PORT_FILE)) core (
        .clk,.rst_n(core_rst_n),.syndrome(syndrome_q),.lambda_0(prior_q),
        .convergence_mask(mask_q),.active_mask(active_q),.e_hat(core_errors),
        .converged(core_success),.done(core_done),.iter_count(core_iter),.leg_count(core_leg)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; syndrome_q<='0; mask_q<='0; active_q<='0;
            success<=0; errors<='0; iter_count<='0; leg_count<='0;
        end else case(state)
            IDLE: if(req_valid) begin
                syndrome_q<=detectors; mask_q<=convergence_mask; active_q<=active_mask;
                for(int j=0;j<V;j++) prior_q[j]<=startup_profile ? startup_prior[j] : bulk_prior[j];
                state<=START;
            end
            START: state<=RUN;
            RUN: if(core_done) begin
                success<=core_success; errors<=core_errors;
                iter_count<=core_iter; leg_count<=core_leg; state<=RESPONSE;
            end
            RESPONSE: if(rsp_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
