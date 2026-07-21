import cnu_pkg::*;

module cnu #( parameter int DEGREE=6)(
    input logic clk,
    input logic rst_n,
    input logic [3:0] nu_in[DEGREE],
    input logic syndrome_bit,

    output cnu_msg_t mu_out[DEGREE],
    input logic valid_in,
    output logic ready_out,
    output logic valid_out
);

logic sign_bits[DEGREE];
logic [2:0] mag_bits[DEGREE];
logic parity_xor;
logic [2:0] min1_val, min2_val;

genvar g;

generate
    for(g=0;g<DEGREE;g++) 
        begin:split_sign_mag
            assign sign_bits[g]=nu_in[g][3];
            assign mag_bits[g]=nu_in[g][2:0];
        end
endgenerate


always_comb begin
    parity_xor=syndrome_bit;
    for(int i=0;i<DEGREE;i++)
        parity_xor ^= sign_bits[i];
end

always_comb begin
    min1_val=3'b111;
    min2_val=3'b111;
    for( int i=0; i<DEGREE; i++) begin
        if(mag_bits[i]<min1_val) begin
            min2_val=min1_val;
            min1_val=mag_bits[i];
        end
        else if( mag_bits[i]<min2_val) begin
            min2_val=mag_bits[i];
        end
    end
end

generate
    for(g=0;g<DEGREE;g++) begin : attach_block
        assign mu_out[g].sign=parity_xor^sign_bits[g];
        assign mu_out[g].c=(mag_bits[g]==min1_val);
        assign mu_out[g].min1={1'b0,min1_val};
        assign mu_out[g].min2={1'b0,min2_val};
    end
endgenerate

assign valid_out=valid_in & rst_n;
assign ready_out= rst_n;

endmodule