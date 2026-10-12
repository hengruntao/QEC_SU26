import cnu_pkg::*;

module cnu #( parameter int DEGREE=6)(
    input logic clk,
    input logic rst_n,
    input logic [4:0] nu_in[DEGREE],
    input logic syndrome_bit,
    input logic [3:0] t,
    output cnu_msg_t mu_out[DEGREE],
    input logic valid_in,
    output logic ready_out,
    output logic valid_out
);

logic sign_bits[DEGREE];
logic [3:0] mag_bits[DEGREE];
logic parity_xor;
logic [3:0] min1_val, min2_val;

logic [3:0] min1_val_scaled, min2_val_scaled;

genvar g;

generate
    for(g=0;g<DEGREE;g++) 
        begin:split_sign_mag
            assign sign_bits[g]=nu_in[g][4];
            assign mag_bits[g]=nu_in[g][3:0];
        end
endgenerate


always_comb begin
    parity_xor=syndrome_bit;
    for(int i=0;i<DEGREE;i++)
        parity_xor ^= sign_bits[i];
end

// Two-min finder as a balanced tree (log2(DEGREE) merge levels instead of a DEGREE-long chain).
// Each leaf is (mag, 15); padding leaves are (15, 15). A merge of (a1,a2) and (b1,b2) keeps the
// two smallest of the four: min1 = min(a1,b1), min2 = a1<=b1 ? min(a2,b1) : min(a1,b2).
// Same min1/min2 as the old sequential loop for every input, ties included.
localparam int LEV  = (DEGREE > 1) ? $clog2(DEGREE) : 1;
localparam int NPAD = 1 << LEV;

logic [3:0] tm1 [0:LEV][0:NPAD-1];
logic [3:0] tm2 [0:LEV][0:NPAD-1];

generate
    for (g = 0; g < NPAD; g++) begin: tm_leaf
        if (g < DEGREE) begin: g_in
            assign tm1[0][g] = mag_bits[g];
        end else begin: g_pad
            assign tm1[0][g] = 4'hF;
        end
        assign tm2[0][g] = 4'hF;
    end
    for (genvar l = 1; l <= LEV; l++) begin: tm_level
        for (genvar k = 0; k < (NPAD >> l); k++) begin: tm_node
            logic [3:0] a1, a2, b1, b2;
            assign a1 = tm1[l-1][2*k];
            assign a2 = tm2[l-1][2*k];
            assign b1 = tm1[l-1][2*k+1];
            assign b2 = tm2[l-1][2*k+1];
            assign tm1[l][k] = (a1 <= b1) ? a1 : b1;
            assign tm2[l][k] = (a1 <= b1) ? ((a2 < b1) ? a2 : b1)
                                          : ((a1 < b2) ? a1 : b2);
        end
    end
endgenerate

assign min1_val = tm1[LEV][0];
assign min2_val = tm2[LEV][0];

assign min1_val_scaled=min1_val-(min1_val>>t);
assign min2_val_scaled=min2_val-(min2_val>>t);


generate
    for(g=0;g<DEGREE;g++) begin : attach_block
        assign mu_out[g].sign=parity_xor^sign_bits[g];
        assign mu_out[g].c=(mag_bits[g]==min1_val);
        assign mu_out[g].min1={min1_val_scaled};
        assign mu_out[g].min2={min2_val_scaled};
    end
endgenerate

assign valid_out=valid_in & rst_n;
assign ready_out= rst_n;

endmodule