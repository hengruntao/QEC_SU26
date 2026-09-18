`timescale 1ns/1ps

module dmembp_top_tb;

    // Clock and reset
    logic clk;
    logic rst_n;
    
    // DUT ports
    logic [71:0]  syndrome;
    logic [3:0]   lambda_0;
    logic [143:0] e_hat;
    logic         converged;
    logic         done;
    logic [5:0]   iter_count;
    
    // Expected outputs
    logic [143:0] expected_ehat;
    logic         expected_converged;
    logic [6:0]   expected_meta;
    
    // Clock generation: 10ns period
    initial clk = 0;
    always #5 clk = ~clk;
    
    // DUT instantiation
    dmembp_top #(.MAX_ITER(60)) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .syndrome   (syndrome),
        .lambda_0   (lambda_0),
        .e_hat      (e_hat),
        .converged  (converged),
        .done       (done),
        .iter_count (iter_count)
    );
    
    // Load hex files
    logic [71:0]  syndrome_mem  [0:0];
    logic [143:0] ehat_mem      [0:0];
    logic [7:0]   meta_mem      [0:0];
    
    initial begin
        $readmemh("dmem_syndrome.hex", syndrome_mem);
        $readmemh("dmem_ehat.hex",     ehat_mem);
        $readmemh("dmem_meta.hex",     meta_mem);
    end
    
    // Expected values
    logic [6:0] expected_iter;
    
    initial begin
        expected_ehat      = ehat_mem[0];
        expected_converged = meta_mem[0][0];
        expected_iter      = meta_mem[0][7:1];
    end
    
    // Main test
    initial begin
        // lambda_0 = 4 (matches p=0.1, int4 scaling factor 2: round(ln(9)*2) = 4)
        lambda_0 = 4'd4;
        syndrome = syndrome_mem[0];
        
        // Reset
        rst_n = 0;
        repeat(2) @(posedge clk);
        rst_n = 1;
        
        // Wait for done
        wait(done);
        @(posedge clk); // one extra cycle for output to settle
        
        // Check results
        $display("=== DMem-BP Integration Test ===");
        $display("iter_count : %0d  (expected %0d)", iter_count, expected_iter);
        $display("converged  : %0b  (expected %0b)", converged,  expected_converged);
        
        if (e_hat === expected_ehat)
            $display("PASS: e_hat matches");
        else begin
            $display("FAIL: e_hat mismatch");
            $display("  got:      %036h", e_hat);
            $display("  expected: %036h", expected_ehat);
        end
        
        if (converged === expected_converged)
            $display("PASS: converged matches");
        else
            $display("FAIL: converged mismatch");
            
        if (iter_count == expected_iter[5:0])
            $display("PASS: iter_count matches");
        else
            $display("FAIL: iter_count mismatch (got %0d, expected %0d)", iter_count, expected_iter);
        
        $finish;
    end
    
    // Timeout watchdog
    initial begin
        #100000;
        $display("TIMEOUT: simulation exceeded 100us");
        $finish;
    end

endmodule