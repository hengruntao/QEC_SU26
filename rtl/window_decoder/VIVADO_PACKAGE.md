# Vivado package

Everything is inside `QEC_SU26/vivado/window_decoder`, including the X/Z
subfolders. See that directory's README for the full file list and commands.

From the QEC_SU26 root on a Vivado machine:

```sh
vivado -mode gui -source vivado/window_decoder/create_project.tcl -tclargs --sector x_checks --action sim
```

Use `--sector z_checks` for Z checks and `--bench beta` for the focused existing
beta-control test. Reopen an existing generated project or choose a fresh
`--out`; the script deliberately refuses to overwrite projects.

Included: nine exact canonical RTL snapshots, a configuration-only top, ten
runtime ROMs per sector, startup/bulk priors using the existing repository rule,
input/reference vectors, self-checking benches, clock constraints, manifest,
project Tcl and local validators. There is no replacement BP implementation.

The FPGA part is inherited from the existing IBM project. The 10 ns clock is a
starter target, not a measured result. Actual Vivado simulation, synthesis,
device fit and timing still require Vivado. Final-codeword handling, END flushing
and a continuous-input FIFO remain outside the implemented transaction path.

Regenerate after changing canonical RTL, using a fresh output directory:

```sh
python3 rtl/window_decoder/build_vivado_package.py --output vivado/window_decoder_next
```
