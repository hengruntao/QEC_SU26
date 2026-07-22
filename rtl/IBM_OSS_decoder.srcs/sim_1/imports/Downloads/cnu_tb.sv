import cnu_pkg::*;

module cnu_tb;

  // ---- Parameters ----
  localparam int DEGREE    = 6;
  localparam int NUM_TESTS = 348;

  // ---- DUT signals ----
  logic        clk;
  logic        rst_n;
  logic [3:0]  nu_in [DEGREE];
  logic        syndrome_bit;
  logic [3:0]  t;
  cnu_msg_t    mu_out [DEGREE];
  logic        valid_in;
  logic        ready_out;
  logic        valid_out;

  // ---- Test vector storage ----
  logic [31:0] inputs_mem   [NUM_TESTS];
  logic [19:0] expected_mem [NUM_TESTS];

  // ---- Counters ----
  int pass_count;
  int fail_count;

  // ---- Clock generation ----
  initial clk = 0;
  always #5 clk = ~clk;

  // ---- DUT instantiation ----
  cnu #(.DEGREE(DEGREE)) dut (
    .clk          (clk),
    .rst_n        (rst_n),
    .nu_in        (nu_in),
    .syndrome_bit (syndrome_bit),
    .t            (t),
    .mu_out       (mu_out),
    .valid_in     (valid_in),
    .ready_out    (ready_out),
    .valid_out    (valid_out)
  );

  // ---- Main test ----
  initial begin
    // Load hex files
    $readmemh("C:/Users/rimpl/vivado/QEC_SU26/rtl/IBM_OSS_decoder.srcs/sim_1/cnu_inputs.hex", inputs_mem);
    $readmemh("C:/Users/rimpl/vivado/QEC_SU26/rtl/IBM_OSS_decoder.srcs/sim_1/cnu_expected.hex", expected_mem);

    // Init
    rst_n    = 1;
    valid_in = 1;
    pass_count = 0;
    fail_count = 0;

    // Wait for reset settle
    #10;

    for (int tc = 0; tc < NUM_TESTS; tc++) begin
      // ---- Unpack inputs ----
      nu_in[0]     = inputs_mem[tc][31:28];
      nu_in[1]     = inputs_mem[tc][27:24];
      nu_in[2]     = inputs_mem[tc][23:20];
      nu_in[3]     = inputs_mem[tc][19:16];
      nu_in[4]     = inputs_mem[tc][15:12];
      nu_in[5]     = inputs_mem[tc][11:8];
      t            = inputs_mem[tc][7:4];
      syndrome_bit = inputs_mem[tc][0];

      // ---- Wait for combinational propagation ----
      #10;

      // ---- Unpack expected outputs ----
      // Bits 19:8 = {sign0, c0, sign1, c1, sign2, c2, sign3, c3, sign4, c4, sign5, c5}
      // Bits 7:4  = min1_scaled
      // Bits 3:0  = min2_scaled

      begin
        logic        exp_sign [DEGREE];
        logic        exp_c    [DEGREE];
        logic [3:0]  exp_min1;
        logic [3:0]  exp_min2;
        int          mismatch;

        for (int i = 0; i < DEGREE; i++) begin
          exp_sign[i] = expected_mem[tc][19 - 2*i];
          exp_c[i]    = expected_mem[tc][18 - 2*i];
        end
        exp_min1 = expected_mem[tc][7:4];
        exp_min2 = expected_mem[tc][3:0];

        // ---- Compare ----
        mismatch = 0;

        for (int i = 0; i < DEGREE; i++) begin
          if (mu_out[i].sign !== exp_sign[i]) begin
            $display("FAIL test %0d edge %0d: sign expected=%0b got=%0b",
                     tc, i, exp_sign[i], mu_out[i].sign);
            mismatch = 1;
          end
          if (mu_out[i].c !== exp_c[i]) begin
            $display("FAIL test %0d edge %0d: c expected=%0b got=%0b",
                     tc, i, exp_c[i], mu_out[i].c);
            mismatch = 1;
          end
          if (mu_out[i].min1 !== exp_min1) begin
            $display("FAIL test %0d edge %0d: min1 expected=%0d got=%0d",
                     tc, i, exp_min1, mu_out[i].min1);
            mismatch = 1;
          end
          if (mu_out[i].min2 !== exp_min2) begin
            $display("FAIL test %0d edge %0d: min2 expected=%0d got=%0d",
                     tc, i, exp_min2, mu_out[i].min2);
            mismatch = 1;
          end
        end

        if (mismatch)
          fail_count++;
        else
          pass_count++;
      end
    end

    // ---- Summary ----
    $display("");
    $display("========================================");
    $display("  CNU Testbench Results");
    $display("  PASSED: %0d / %0d", pass_count, NUM_TESTS);
    $display("  FAILED: %0d / %0d", fail_count, NUM_TESTS);
    $display("========================================");

    if (fail_count == 0)
      $display("  ALL TESTS PASSED");
    else
      $display("  *** FAILURES DETECTED ***");

    $display("");
    $finish;
  end

endmodule
