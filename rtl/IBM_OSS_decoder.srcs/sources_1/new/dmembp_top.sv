// top level module for the dmembp iteration
// This module is going to contain 1 cycle of the CNU followed by 1 cycle of the VNU, completing a BP iteration.

import cnu_pkg::*;

module dmembp_top #(
    parameter int MAX_ITER=60
    )(
    input logic         clk,
    input logic         rst_n,
    input logic [71:0]  syndrome,
    input logic [3:0]   lambda_0,
    output logic [143:0]    e_hat,
    output logic        converged,
    output logic        done,
    output logic [5:0]  iter_count
    );
    
    // names for the different FSM states
    typedef enum logic[ 1:0] {
        S_INIT=2'd0,
        S_CNU_PHASE=2'd1,
        S_VNU_PHASE=2'd2,
        S_DONE=2'd3   
    }state_t;
    
    state_t state, state_next;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <=S_INIT;
        else        state <=state_next;
    end
        
        
    //iteration counter
    
    logic [5:0] iter_cnt;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) iter_cnt<=6'd0;
        else if (state ==S_INIT) iter_cnt<=6'd0;
        else if (state ==S_VNU_PHASE) iter_cnt<=iter_cnt+6'd1;
    end 
    
    assign iter_count=iter_cnt;
    
    logic [5:0] t_plus_one;
    logic [3:0] t_alpha;
    assign t_plus_one = iter_cnt + 6'd1;
    assign t_alpha = (t_plus_one > 6'd15)? 4'd15:t_plus_one[3:0]; 
    
    
    logic vnu_init;
    logic vnu_en;
    
    
    assign vnu_init = (state == S_INIT);
    assign vnu_en = (state == S_VNU_PHASE);
    
    
    logic [7:0] cnu_to_vnu_idx [0:71][0:5];
    logic [1:0] cnu_to_vnu_port [0:71][0:5];
    
    initial begin
        $readmemh("cnu_to_vnu_idx.mem", cnu_to_vnu_idx);
        $readmemh("cnu_to_vnu_port.mem", cnu_to_vnu_port);
    end 
    
    
    
    logic [4:0] nu_wire_reg [0:143][0:2];
    
    logic [4:0] nu_wire [0:143][0:2];
    
    logic [9:0] mu_wire [0:143][0:2];
    
    logic e_hat_bit [0:143];
    
    cnu_msg_t cnu_mu_out [0:71][0:5];
    
    logic [4:0] cnu_nu_in [0:71][0:5];
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for(int j=0;j<144; j++)
                for (int k=0; k<3; k++)
                    nu_wire_reg[j][k]<=5'd0;
        end 
        else if(state==S_INIT || state==S_VNU_PHASE) begin
            for(int j=0;j<144; j++)
                for (int k=0; k<3; k++)
                    nu_wire_reg[j][k]<=nu_wire[j][k];
        end
    end
    
    always_comb begin
        for(int i=0; i<72; i++) 
            for (int p=0; p<6; p++)
                cnu_nu_in[i][p]=nu_wire_reg[cnu_to_vnu_idx[i][p] ][cnu_to_vnu_port[i][p]]; 
    end 
    
    //CNU instantiation (72 instances)
    generate
        for (genvar i=0; i<72; i++) begin:gen_cnu
            cnu #(.DEGREE(6)) 
            u_cnu (
                .clk    (clk),
                .rst_n  (rst_n),
                .nu_in  (cnu_nu_in[i]),
                .syndrome_bit (syndrome[i]),
                .t      (t_alpha),
                .mu_out (cnu_mu_out[i]),
                .valid_in   (1'b1),
                .ready_out (),
                .valid_out ()
                );
             end 
        endgenerate
        
    always_comb begin
        for (int j = 0; j < 144; j++)
            for (int k = 0; k < 3; k++)
                mu_wire[j][k] = 10'd0;
                
        for (int i=0; i<72; i++)
            for (int p=0; p<6;p++)
                mu_wire[cnu_to_vnu_idx[i][p]][cnu_to_vnu_port[i][p]]={
                    cnu_mu_out[i][p].sign,
                    cnu_mu_out[i][p].c,
                    cnu_mu_out[i][p].min1,
                    cnu_mu_out[i][p].min2
                };
    end

    //VNU instantiation (144 instances)
    generate
        for (genvar j=0; j<144; j++) begin: gen_vnu 
            vnu #(
                .DEG(3),
                .MAG_W(4),
                .MJ_W(8),
                .M_LOG2(3),
                .LFSR_SEED(8'(j+1))
            )
            u_vnu(
                .clk    (clk) ,
                .rst_n  (rst_n),
                .init   (vnu_init),
                .new_leg    (1'b0),
                .en     (vnu_en),
                .lambda_0    (lambda_0),
                .mu_in  (mu_wire[j]),
                .nu_out (nu_wire[j]),
                .marginal(),
                .e_hat  (e_hat_bit[j])
            );
        end 
    endgenerate   
    
    
    // Convergence checker: H_X @ e_hat mod 2 == syndrome
    
    logic [71:0] recon_syndrome;
    logic   converged_comb;
    
    always_comb begin
        for(int i=0; i<72; i++) begin
            recon_syndrome [i] =1'b0;
            for (int p=0; p<6; p++)
                recon_syndrome[i] = recon_syndrome[i] ^ e_hat_bit[ cnu_to_vnu_idx[i][p]];
        end 
        converged_comb = (recon_syndrome == syndrome);
    end
    
    
    //FSM logic
    
    always_comb begin
        state_next=state;
        case (state) 
            S_INIT:     state_next = S_CNU_PHASE;
            S_CNU_PHASE : state_next = S_VNU_PHASE;
            S_VNU_PHASE: begin
                if(converged_comb||iter_cnt>=(MAX_ITER[5:0]-6'd1))
                    state_next=S_DONE;
                else 
                    state_next=S_CNU_PHASE;
            end
            S_DONE:     state_next=S_DONE;
            default:    state_next=S_INIT;
        endcase
    end
    
    //Output latching at done
    
    logic [143:0] e_hat_latched;
    logic           converged_latched;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            e_hat_latched <=144'd0;
            converged_latched<=1'b0;
        end
        else if (state==S_VNU_PHASE && state_next==S_DONE) begin
            for(int i=0; i<144; i++) 
                e_hat_latched[i]<=e_hat_bit[i];
            converged_latched<=converged_comb;
        end
    end 
    
    assign e_hat=e_hat_latched;
    assign converged=converged_latched;
    assign done=(state==S_DONE);
    
endmodule   
               
    
    
    
    
    
    
    
    
