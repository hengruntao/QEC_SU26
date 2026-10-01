import cnu_pkg::*;

module relay_bp_top #(
    parameter int T0        = 80,
    parameter int Tr        = 60,
    parameter int MAX_LEGS  = 600,
    parameter int NUM_SOL   = 5
)(
    input  logic         clk,
    input  logic         rst_n,
    input  logic [71:0]  syndrome,
    input  logic [3:0]   lambda_0 [0:143],
    output logic [143:0] e_hat,
    output logic         converged,
    output logic         done,
    output logic [6:0]   iter_count,
    output logic [9:0]   leg_count
);

typedef enum logic [2:0] {
    S_INIT       = 3'd0,
    S_CNU_PHASE  = 3'd1,
    S_VNU_PHASE  = 3'd2,
    S_WEIGHT     = 3'd3,
    S_NEW_LEG    = 3'd4,
    S_DONE       = 3'd5
} state_t;

state_t state, state_next;

//iteration counter (per leg)

logic [6:0] iter_cnt;
logic [6:0] max_iter;

//solution tracking

logic [2:0] sol_cnt;
logic [11:0] best_weight;
logic [143:0] best_e_hat;
logic[143:0] e_hat_internal;

//weight accumulator
logic [11:0] weight_acc;
logic [7:0] weight_idx;
logic       weight_done;


// Relay control signals
logic        new_leg_pulse;    // goes to every VNU, triggers LFSR resample of beta_int
logic        any_solution_found;

// Leg counter (internal - drives the leg_count output port)
logic [9:0]  leg_cnt;

// State register
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        state <= S_INIT;
    else
        state <= state_next;
end

always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        iter_cnt<='0;
        max_iter<= T0[6:0];
        leg_cnt<='0;
        sol_cnt<='0;
        best_weight<=12'hfff;
        best_e_hat<= '0;
        any_solution_found <=1'b0;
        //new_leg_pulse <=1'b0;
        weight_acc<='0;
        weight_idx<=0;
        weight_done<=1'b0;
    end else begin
        //new_leg_pulse<=1'b0;
        weight_done<=1'b0;
        
        case(state)
            S_INIT:begin
                iter_cnt<='0;
                max_iter<=T0[6:0];
                leg_cnt<='0;
                sol_cnt<='0;
                best_weight<=12'hFFF;
                best_e_hat<='0;
                any_solution_found<='0;
            end
            
            S_CNU_PHASE:  begin
            end
            
            S_VNU_PHASE: begin
                iter_cnt<=iter_cnt+1;
            end
            
            S_WEIGHT: begin
                if(!weight_done) begin
                    if (weight_idx<8'd144) begin
                        if(e_hat_internal[weight_idx])
                            weight_acc <= weight_acc + {8'b0, lambda_0[weight_idx]};
                        weight_idx<=weight_idx+1;
                    end 
                    else begin
                        weight_done <=1'b1;
                        if(weight_acc< best_weight) begin
                            best_weight <= weight_acc;
                            best_e_hat<= e_hat_internal;
                        end
                        
                        sol_cnt<=sol_cnt+1;
                        any_solution_found<=1'b1;
                        weight_acc<='0;
                        weight_idx<='0;
                    end
                end
            end
            
            S_NEW_LEG: begin
                //new_leg_pulse<=1'b1;
                iter_cnt<='0;
                leg_cnt<=leg_cnt+1;
                max_iter <= Tr[6:0];
            end
            
            
            S_DONE: begin
            end
            
        endcase
     end 
end   

assign e_hat     = best_e_hat;
assign converged = any_solution_found;
assign done      = (state == S_DONE);
assign iter_count = iter_cnt;
assign leg_count  = leg_cnt;
assign new_leg_pulse = (state == S_NEW_LEG);

logic [71:0] recon_syndrome;
logic        converged_comb;

always_comb begin
    state_next= state;
    case(state)
        S_INIT: begin
            state_next= S_CNU_PHASE;
        end
        
        S_CNU_PHASE: begin
            state_next=S_VNU_PHASE;
        end
        
        S_VNU_PHASE: begin
            if (converged_comb)
                state_next = S_WEIGHT;
            else if (iter_cnt >= (max_iter-7'd1) && leg_cnt < MAX_LEGS)
                state_next = S_NEW_LEG;
            else if (iter_cnt >= (max_iter-7'd1) && leg_cnt >= MAX_LEGS)
                state_next = S_DONE;
            else
                state_next = S_CNU_PHASE;
        end    
        
        
        S_WEIGHT: begin
            if(weight_done) begin
                if(sol_cnt>=(NUM_SOL-1))          
                    state_next = S_DONE;
                else if(leg_cnt< MAX_LEGS)
                    state_next=S_NEW_LEG;
                else
                    state_next=S_DONE;
            end
        end
        
        S_NEW_LEG: begin
            state_next=S_CNU_PHASE;
        end
        
        S_DONE: begin
            state_next= S_DONE;
        end
        default: state_next=S_INIT;
    endcase
end

logic [6:0] t_plus_one;
logic [3:0] t_alpha;
assign t_plus_one = iter_cnt + 7'd1;
assign t_alpha    = (t_plus_one > 7'd15) ? 4'd15 : t_plus_one[3:0];

logic vnu_init;
logic vnu_en;
assign vnu_init = (state == S_INIT);
assign vnu_en   = (state == S_VNU_PHASE);
     
     
logic [7:0] cnu_to_vnu_idx  [0:71][0:5];
logic [1:0] cnu_to_vnu_port [0:71][0:5];

initial begin
    $readmemh("cnu_to_vnu_idx.mem",  cnu_to_vnu_idx);
    $readmemh("cnu_to_vnu_port.mem", cnu_to_vnu_port);
end

logic [4:0] nu_wire_reg [0:143][0:2];
logic [4:0] nu_wire     [0:143][0:2];
logic [9:0] mu_wire     [0:143][0:2];

logic e_hat_bit [0:143];

cnu_msg_t   cnu_mu_out [0:71][0:5];
logic [4:0] cnu_nu_in  [0:71][0:5];

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        for (int j = 0; j < 144; j++)
            for (int k = 0; k < 3; k++)
                nu_wire_reg[j][k] <= 5'd0;
    end
    else if (state == S_NEW_LEG) begin
        for (int j = 0; j < 144; j++)
            for (int k = 0; k < 3; k++)
                nu_wire_reg[j][k] <= {1'b0, lambda_0[j]};
    end
    else if (state == S_INIT || state == S_VNU_PHASE) begin
        for (int j = 0; j < 144; j++)
            for (int k = 0; k < 3; k++)
                nu_wire_reg[j][k] <= nu_wire[j][k];
    end
end


always_comb begin
    for (int i = 0; i < 72; i++)
        for (int p = 0; p < 6; p++)
            cnu_nu_in[i][p] = nu_wire_reg[cnu_to_vnu_idx[i][p]][cnu_to_vnu_port[i][p]];
end

generate
    for (genvar i = 0; i < 72; i++) begin: gen_cnu
        cnu #(.DEGREE(6))
        u_cnu (
            .clk          (clk),
            .rst_n        (rst_n),
            .nu_in        (cnu_nu_in[i]),
            .syndrome_bit (syndrome[i]),
            .t            (t_alpha),
            .mu_out       (cnu_mu_out[i]),
            .valid_in     (1'b1),
            .ready_out    (),
            .valid_out    ()
        );
    end
endgenerate


always_comb begin
    for (int j = 0; j < 144; j++)
        for (int k = 0; k < 3; k++)
            mu_wire[j][k] = 10'd0;

    for (int i = 0; i < 72; i++)
        for (int p = 0; p < 6; p++)
            mu_wire[cnu_to_vnu_idx[i][p]][cnu_to_vnu_port[i][p]] = {
                cnu_mu_out[i][p].sign,
                cnu_mu_out[i][p].c,
                cnu_mu_out[i][p].min1,
                cnu_mu_out[i][p].min2
            };
end
generate
    for (genvar j = 0; j < 144; j++) begin: gen_vnu
        vnu #(
            .DEG       (3),
            .MAG_W     (4),
            .MJ_W      (8),
            .M_LOG2    (3),
            .LFSR_SEED (8'(j+1))
        )
        u_vnu (
            .clk      (clk),
            .rst_n    (rst_n),
            .init     (vnu_init),
            .new_leg  (new_leg_pulse),
            .en       (vnu_en),
            .lambda_0 (lambda_0[j]),
            .mu_in    (mu_wire[j]),
            .nu_out   (nu_wire[j]),
            .marginal (),
            .e_hat    (e_hat_bit[j])
        );
    end
endgenerate



always_comb begin
    for (int i = 0; i < 72; i++) begin
        recon_syndrome[i] = 1'b0;
        for (int p = 0; p < 6; p++)
            recon_syndrome[i] = recon_syndrome[i] ^ e_hat_bit[cnu_to_vnu_idx[i][p]];
    end
    converged_comb = (recon_syndrome == syndrome);
end

always_comb begin
    for (int i = 0; i < 144; i++)
        e_hat_internal[i] = e_hat_bit[i];
end

endmodule




        


                            


       
                
                
                
                
                
            