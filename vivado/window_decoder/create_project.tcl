# Run from the QEC_SU26 root; all paths derive from this script's location.
set package_dir [file dirname [file normalize [info script]]]
array set opt {--sector x_checks --action sim --bench window --part xc7s50csga324-1 --clock-period-ns 10.0 --out {}}
if {![info exists argv]} {set argv {}}
if {$argv eq {--help}} {
    puts "Options: --sector x_checks|z_checks --action create|sim|synth --bench window|beta --part PART --clock-period-ns NS --out DIRECTORY"
    return
}
if {[llength $argv] % 2} {error "Options require name/value pairs; use --help"}
foreach {key value} $argv {
    if {![info exists opt($key)]} {error "Unknown option: $key"}
    set opt($key) $value
}
if {$opt(--sector) ni {x_checks z_checks}} {error "Invalid sector"}
if {$opt(--action) ni {create sim synth}} {error "Invalid action"}
if {$opt(--bench) ni {window beta}} {error "Invalid bench"}
if {![string is double -strict $opt(--clock-period-ns)] || $opt(--clock-period-ns)<=0} {error "Clock period must be positive"}
if {$opt(--action) eq "synth" && $opt(--bench) eq "beta"} {error "Use window bench selection for synthesis"}
if {$opt(--out) eq ""} {set opt(--out) [file join $package_dir build $opt(--sector)_$opt(--bench)]}
set project_dir [file normalize $opt(--out)]
if {[file exists $project_dir]} {error "Output already exists: $project_dir. Open its .xpr, or choose another --out."}
set rom_dir [file join $package_dir rom $opt(--sector)]
set ref_dir [file join $package_dir sim data $opt(--sector)]
set beta_dir [file join $package_dir sim beta]
set rtl_names {cnu_pkg.sv cnu.sv vnu.sv relay_bp_top.sv relay_window_adapter.sv window_decoder_ctrl.sv window_effects.sv window_decoder_top.sv window_relay_top.sv window_decoder_vivado_top.sv}
set rom_names {cnu_to_vnu_idx.mem cnu_to_vnu_port.mem startup_prior.mem bulk_prior.mem carry_rows.mem frame_rows.mem commit_mask.mem convergence_mask.mem startup_active_mask.mem bulk_active_mask.mem}
set sources {}
foreach name $rtl_names {
    set path [file join $package_dir rtl $name]
    if {![file isfile $path]} {error "Missing RTL: $path"}
    lappend sources $path
}
foreach name $rom_names {if {![file isfile [file join $rom_dir $name]]} {error "Missing ROM: $name"}}
set bench_top [expr {$opt(--bench) eq "window" ? "window_relay_tb" : "beta_resampling_tb"}]
set bench_file [file join $package_dir sim $bench_top.sv]
if {![file isfile $bench_file]} {error "Missing testbench: $bench_file"}

create_project window_decoder $project_dir -part $opt(--part)
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set generated [file join $project_dir generated]
file mkdir $generated
set fd [open [file join $generated qec_paths.svh] w]
foreach {macro path} [list QEC_ROM_DIR $rom_dir QEC_REF_DIR $ref_dir QEC_BETA_DIR $beta_dir] {
    set escaped [string map [list "\\" "/" "\"" "\\\""] $path]
    puts $fd "`define $macro \"$escaped\""
}
puts $fd "`define QEC_CLOCK_PERIOD_NS $opt(--clock-period-ns)"
close $fd
add_files -norecurse $sources
foreach name $rom_names {add_files -norecurse [file join $rom_dir $name]}
add_files -fileset sim_1 -norecurse $bench_file
set include_paths [list $generated [file join $package_dir config]]
set_property include_dirs $include_paths [get_filesets sources_1]
set_property include_dirs $include_paths [get_filesets sim_1]
set_property top window_decoder_vivado_top [get_filesets sources_1]
set_property top $bench_top [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
set fd [open [file join $generated clock.xdc] w]
puts $fd "create_clock -name clk -period $opt(--clock-period-ns) \[get_ports clk\]"
close $fd
add_files -fileset constrs_1 -norecurse [file join $generated clock.xdc]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "Project: $project_dir/window_decoder.xpr"
puts "Sector: $opt(--sector); part: $opt(--part); clock: $opt(--clock-period-ns) ns"
if {$opt(--action) eq "sim"} {
    launch_simulation -mode behavioral
} elseif {$opt(--action) eq "synth"} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis did not complete"}
    open_run synth_1
    set reports [file join $project_dir reports]
    file mkdir $reports
    report_utilization -file [file join $reports utilization.rpt]
    report_timing_summary -report_unconstrained -file [file join $reports timing_summary.rpt]
    write_checkpoint -force [file join $reports synthesized.dcp]
}
