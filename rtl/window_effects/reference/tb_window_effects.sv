`timescale 1ns/1ps
`ifndef EFFECTS_VECTORS
`define EFFECTS_VECTORS "transactions.txt"
`endif

module tb_window_effects;
    localparam int N_FAULTS = 8785, M = 72, K = 12;
    localparam int MAX_WAIT = 200;
    logic clk = 0, rst_n = 0;
    logic [N_FAULTS-1:0] e_hat = '0;
    logic converged = 0, in_valid = 0, in_ready;
    logic [M-1:0] carry;
    logic [K-1:0] frame;
    logic out_success, out_valid, out_ready = 0;
    integer fd, fields, index = 0;
    integer reset_flag, valid_flag, conv_flag, expected_valid, expected_success;
    logic [N_FAULTS-1:0] vector_errors;
    logic [M-1:0] expected_carry;
    logic [K-1:0] expected_frame;
    integer successes = 0, failures = 0, invalids = 0, stalled_cycles = 0;
    integer frame_changes = 0;
    logic [K-1:0] previous_frame = '0;

    always #6 clk = ~clk;
    window_effects #(.N_FAULTS(N_FAULTS), .M(M), .K(K)) dut (
        .clk(clk), .rst_n(rst_n), .e_hat(e_hat), .converged(converged),
        .in_valid(in_valid), .in_ready(in_ready), .carry(carry), .frame(frame),
        .out_success(out_success), .out_valid(out_valid), .out_ready(out_ready)
    );

    task automatic reset_session;
        @(negedge clk);
        rst_n = 0;
        in_valid = 0;
        out_ready = 0;
        repeat (2) @(negedge clk);
        if (frame !== '0 || carry !== '0 || out_valid !== 1'b0 ||
            out_success !== 1'b0 || in_ready !== 1'b0)
            $fatal(1, "Reset outputs incorrect at vector %0d", index);
        rst_n = 1;
        @(negedge clk);
        if (in_ready !== 1'b1 || out_valid !== 1'b0)
            $fatal(1, "Not idle after reset");
        previous_frame = '0;
    endtask

    task automatic send_request(input logic [N_FAULTS-1:0] errors,
                                 input logic did_converge);
        integer cycles;
        @(negedge clk);
        e_hat = errors;
        converged = did_converge;
        in_valid = 1;
        cycles = 0;
        do begin
            @(posedge clk);
            cycles++;
            if (cycles > MAX_WAIT) $fatal(1, "Input handshake timeout");
        end while (in_ready !== 1'b1);
        @(negedge clk);
        in_valid = 0;
        // Live input changes must not corrupt the captured request.
        e_hat = ~errors;
        converged = ~did_converge;
    endtask

    task automatic check_response(input logic [M-1:0] want_carry,
                                   input logic [K-1:0] want_frame,
                                   input logic want_success);
        if (out_valid !== 1'b1 || carry !== want_carry ||
            frame !== want_frame || out_success !== want_success)
            $fatal(1, "Vector %0d mismatch: success=%b/%b carry=%h/%h frame=%h/%h",
                   index, out_success, want_success, carry, want_carry, frame, want_frame);
    endtask

    task automatic receive_response(input logic [M-1:0] want_carry,
                                     input logic [K-1:0] want_frame,
                                     input logic want_success,
                                     input integer stalls);
        integer cycles;
        cycles = 0;
        while (out_valid !== 1'b1) begin
            @(posedge clk);
            #1;
            cycles++;
            if (cycles > MAX_WAIT) $fatal(1, "Output timeout at vector %0d", index);
        end
        @(negedge clk);
        check_response(want_carry, want_frame, want_success);
        repeat (stalls) begin
            @(negedge clk);
            check_response(want_carry, want_frame, want_success);
            if (in_ready !== 1'b0) $fatal(1, "Accepted input while response stalled");
            stalled_cycles++;
        end
        out_ready = 1;
        @(negedge clk);
        out_ready = 0;
        if (out_valid !== 1'b0 || in_ready !== 1'b1 || frame !== want_frame)
            $fatal(1, "Response not retired exactly once at vector %0d", index);
    endtask

    initial begin
        reset_session();
        fd = $fopen(`EFFECTS_VECTORS, "r");
        if (fd == 0) $fatal(1, "Cannot open golden transaction file: %s", `EFFECTS_VECTORS);
        while (!$feof(fd)) begin
            fields = $fscanf(fd, "%d %d %d %h %d %d %h %h\n",
                             reset_flag, valid_flag, conv_flag, vector_errors,
                             expected_valid, expected_success, expected_carry, expected_frame);
            if (fields == 8) begin
                if ((reset_flag != 0 && reset_flag != 1) ||
                    (valid_flag != 0 && valid_flag != 1) ||
                    (conv_flag != 0 && conv_flag != 1) ||
                    expected_valid != valid_flag || expected_success != (valid_flag && conv_flag))
                    $fatal(1, "Malformed golden flags at vector %0d", index);
                if (reset_flag) reset_session();
                if (valid_flag) begin
                    send_request(vector_errors, conv_flag != 0);
                    receive_response(expected_carry, expected_frame, expected_success != 0, index % 5 + 1);
                    if (expected_success) successes++; else failures++;
                    if (frame !== previous_frame) frame_changes++;
                end else begin
                    @(negedge clk);
                    e_hat = vector_errors;
                    converged = conv_flag != 0;
                    in_valid = 0;
                    repeat (3) begin
                        @(negedge clk);
                        if (out_valid !== 1'b0 || in_ready !== 1'b1 || frame !== expected_frame)
                            $fatal(1, "Invalid input changed state/frame at vector %0d", index);
                    end
                    invalids++;
                end
                previous_frame = frame;
                index++;
            end else if (fields != -1) begin
                $fatal(1, "Malformed golden record after vector %0d: read %0d fields", index, fields);
            end
        end
        $fclose(fd);
        if (index == 0 || successes == 0 || failures == 0 || invalids == 0 || stalled_cycles == 0)
            $fatal(1, "Insufficient golden vector coverage");

        // Reset while a result is held: discard it, clear frame, then recover.
        send_request('1, 1'b0);
        while (out_valid !== 1'b1) @(negedge clk);
        reset_session();
        send_request('1, 1'b0);
        receive_response('0, '0, 1'b0, 2);

        // Reset immediately after input capture, before its result is committed.
        send_request('1, 1'b0);
        rst_n = 0;
        reset_session();
        send_request('1, 1'b0);
        receive_response('0, '0, 1'b0, 1);
        if (frame_changes == 0) $warning("Vectors did not exercise a nonzero frame update");
        $display("PASS effects: %0d golden vectors, %0d successes, %0d failures, %0d invalids, %0d stall cycles, reset recovery",
                 index, successes, failures, invalids, stalled_cycles);
        $finish;
    end

    initial begin
        #100000000;
        $fatal(1, "Global simulation timeout");
    end
endmodule
