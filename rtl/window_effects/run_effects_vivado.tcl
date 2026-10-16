# Run: vivado -mode gui -source rtl/window_effects/run_effects_vivado.tcl
# Scaffold creation is allowed; sim/synth require completed SV and checked constants.
set root [file dirname [file normalize [info script]]]
array set opt {--action create --out {} --mask {} --commit-cycles {} --python python3}
if {![info exists argv]} {set argv {}}
if {[llength $argv] % 2} {error "Options require name/value pairs"}
foreach {key value} $argv {
    if {![info exists opt($key)]} {error "Unknown option: $key"}
    set opt($key) $value
}
if {$opt(--action) ni {create sim synth}} {error "Use create, sim or synth"}
if {$opt(--out) eq {}} {set opt(--out) [file join $root build $opt(--action)]}
set out [file normalize $opt(--out)]
if {[file exists $out]} {error "Output exists; reopen its project or select a fresh --out"}
set dut [file join $root window_effects.sv]
set bench [file join $root tb_window_effects.sv]
if {![file isfile $bench]} {
    set bench [file join $root reference tb_window_effects.sv]
}
if {![file isfile $bench]} {error "Missing handwritten and reference testbench"}
set package [file join $root generated window_effects_pkg.sv]
if {![file isfile $package]} {error "Generate constants first"}
if {$opt(--action) ne "create"} {
    foreach path [list $dut $bench] {
        if {$opt(--action) eq "synth" && $path eq $bench} {continue}
        set fd [open $path r]; set body [read $fd]; close $fd
        if {[string first IMPLEMENTATION_PENDING $body] >= 0} {
            error "RTL/testbench is still an interface-only skeleton: $path"
        }
    }
    set package [file join $root generated window_effects_pkg.sv]
    if {$opt(--mask) eq {} || $opt(--commit-cycles) eq {}} {
        error "Provide reviewed --mask and --commit-cycles; no mask is guessed"
    }
    if {![file isfile $package]} {error "Generate constants first"}
    puts [exec $opt(--python) [file join $root check_effects_constants.py] \
        --data [file join $root data ibm] --mask $opt(--mask) \
        --commit-cycles $opt(--commit-cycles) --package $package]
}
create_project window_effects $out -part xcvu19p-fsva3824-2-e
set_property target_language Verilog [current_project]
add_files -norecurse [list $package $dut]
add_files -fileset sim_1 -norecurse $bench
set_property top window_effects [get_filesets sources_1]
set_property top tb_window_effects [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
if {$opt(--action) eq "sim"} {
    if {![file isfile [file join $root vectors transactions.txt]]} {error "Generate vectors first"}
    file copy -force [file join $root vectors transactions.txt] [file join $out transactions.txt]
    # Absolute path macro for the future handwritten testbench's $fopen.
    set vector_path [string map [list "\\" "/"] [file join $root vectors transactions.txt]]
    set_property verilog_define [list "EFFECTS_VECTORS=\"$vector_path\""] [get_filesets sim_1]
    launch_simulation -mode behavioral
} elseif {$opt(--action) eq "synth"} {
    # OOC avoids treating 8785 internal core-result bits as physical package pins.
    synth_design -top window_effects -part xcvu19p-fsva3824-2-e -mode out_of_context
    create_clock -name clk -period 12.000 [get_ports clk]
    set reports [file join $out reports]; file mkdir $reports
    report_utilization -hierarchical -file [file join $reports utilization.rpt]
    report_timing_summary -delay_type min_max -report_unconstrained -file [file join $reports timing_summary.rpt]
    report_timing -delay_type max -max_paths 20 -path_type full_clock_expanded -input_pins \
        -file [file join $reports critical_paths.rpt]
    check_timing -verbose -file [file join $reports check_timing.rpt]
    write_checkpoint -force [file join $reports effects_synth.dcp]
    puts "Synthesis reports saved. Inspect constrained register-to-register paths; this is not routed timing."
} else {
    puts "Created learning scaffold ONLY. Empty SV bodies are not functional hardware."
}
