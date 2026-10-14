create_clock -period 12.000 -name ap_clk [get_ports ap_clk]
set_input_delay  -clock ap_clk 0 [get_ports -filter {DIRECTION == IN && NAME != ap_clk}]
set_output_delay -clock ap_clk 0 [get_ports -filter {DIRECTION == OUT}]