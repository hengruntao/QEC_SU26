// vnu.sv
// Variable Node Unit, weight 3, for the X decoder of the [[144,12,12]] gross code.

module vnu #(
    parameter int          DEG       = 3,
    parameter int          MAG_W     = 4,
    parameter int          MJ_W      = 8,
    parameter int          M_LOG2    = 3,
    parameter logic [7:0]  LFSR_SEED = 8'hA5
) (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         init,
    input  logic         new_leg,
    input  logic [3:0]   lambda_0,
    input  logic [9:0]   mu_in [DEG],
    output logic [3:0]   nu_out [DEG],
    output logic         e_hat
);

    logic                    mu_sign [DEG];
    logic                    mu_c    [DEG];
    logic [3:0]              mu_min1 [DEG];
    logic [3:0]              mu_min2 [DEG];
    logic [3:0]              mu_mag  [DEG];
    logic signed [MJ_W-1:0]  mu_s    [DEG];

    generate
        for (genvar g = 0; g < DEG; g++) begin : g_unpack
            assign mu_sign[g] = mu_in[g][9];
            assign mu_c[g]    = mu_in[g][8];
            assign mu_min1[g] = mu_in[g][7:4];
            assign mu_min2[g] = mu_in[g][3:0];
            assign mu_mag[g]  = mu_c[g] ? mu_min2[g] : mu_min1[g];
            assign mu_s[g]    = mu_sign[g]
                ? -$signed({{(MJ_W-MAG_W){1'b0}}, mu_mag[g]})
                :  $signed({{(MJ_W-MAG_W){1'b0}}, mu_mag[g]});
        end
    endgenerate

    logic [7:0] lfsr;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) lfsr <= LFSR_SEED;
        else        lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3]};
    end

    logic [3:0] beta_int;
    always_ff @(posedge clk or negedge rst_n) begin
        if      (!rst_n)   beta_int <= 4'd8;
        else if (new_leg)  beta_int <= 4'd3 + {1'b0, lfsr[2:0]};
    end

    logic signed [4:0] gamma_int;
    assign gamma_int = $signed({1'b0, 4'd8}) - $signed({1'b0, beta_int});

    logic signed [MJ_W-1:0] M_j;
    logic signed [MJ_W-1:0] M_j_next;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) M_j <= '0;
        else        M_j <= M_j_next;
    end

    logic signed [MJ_W+4:0] beta_lambda;
    logic signed [MJ_W+4:0] gamma_M;
    logic signed [MJ_W+4:0] bias_raw;
    logic signed [MJ_W-1:0] lambda_t;
    logic signed [MJ_W-1:0] lambda_eff;

    assign beta_lambda = $signed({1'b0, beta_int}) * $signed({1'b0, lambda_0});
    assign gamma_M     = gamma_int * M_j;
    assign bias_raw    = beta_lambda + gamma_M + (1 <<< (M_LOG2-1));
    assign lambda_t    = bias_raw >>> M_LOG2;

    assign lambda_eff  = init
        ? $signed({{(MJ_W-MAG_W){1'b0}}, lambda_0})
        : lambda_t;

    logic signed [MJ_W+1:0] sigma_sum;
    assign sigma_sum = $signed({{2{lambda_eff[MJ_W-1]}}, lambda_eff})
                     + $signed({{2{mu_s[0][MJ_W-1]}},    mu_s[0]})
                     + $signed({{2{mu_s[1][MJ_W-1]}},    mu_s[1]})
                     + $signed({{2{mu_s[2][MJ_W-1]}},    mu_s[2]});

    localparam int signed MJ_MAX = (1 <<< (MJ_W-1)) - 1;
    localparam int signed MJ_MIN = -(1 <<< (MJ_W-1));

    always_comb begin
        if      (sigma_sum > MJ_MAX) M_j_next = MJ_MAX[MJ_W-1:0];
        else if (sigma_sum < MJ_MIN) M_j_next = MJ_MIN[MJ_W-1:0];
        else                         M_j_next = sigma_sum[MJ_W-1:0];
    end

    assign e_hat = M_j_next[MJ_W-1];

    logic signed [MJ_W+1:0] nu_raw  [DEG];
    logic signed [3:0]      nu_sat  [DEG];
    logic        [2:0]      nu_abs  [DEG];

    generate
        for (genvar g = 0; g < DEG; g++) begin : g_nu
            assign nu_raw[g] = $signed({{2{M_j_next[MJ_W-1]}}, M_j_next})
                             - $signed({{2{mu_s[g][MJ_W-1]}},   mu_s[g]});

            always_comb begin
                if      (nu_raw[g] >   4'sd7) nu_sat[g] =  4'sd7;
                else if (nu_raw[g] <  -4'sd7) nu_sat[g] = -4'sd7;
                else                          nu_sat[g] =  nu_raw[g][3:0];
            end

            assign nu_abs[g] = (nu_sat[g] < 0) ? (-nu_sat[g]) : nu_sat[g][2:0];

            always_comb begin
                if (init)
                    nu_out[g] = {1'b0, lambda_0[2:0]};
                else
                    nu_out[g] = {nu_sat[g][3], nu_abs[g]};
            end
        end
    endgenerate

endmodule