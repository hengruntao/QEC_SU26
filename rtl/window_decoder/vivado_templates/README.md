# Window decoder Vivado package

Everything required to load and simulate this package is inside
`QEC_SU26/vivado/window_decoder`. X/Z data are subfolders of this same package.
There are no symlinks or dependencies on /tmp, another checkout, or a local
Desktop path. Python/Verilator are only needed for the optional local checks;
Vivado consumes the included RTL, ROMs, benches and Tcl directly.

## First run

From the QEC_SU26 repository root on a Vivado machine:

```sh
vivado -mode gui -source vivado/window_decoder/create_project.tcl -tclargs --sector x_checks --action sim
```

For the Z sector, use `--sector z_checks`. For a focused beta-control simulation,
use `--bench beta`. In the Vivado GUI Tcl console, set argv before sourcing:

```tcl
set argv {--sector x_checks --action sim}
source vivado/window_decoder/create_project.tcl
```

The script creates a new project inside this package's build directory. If the
output already exists, open its window_decoder.xpr or choose a fresh `--out`.
It deliberately does not overwrite projects or modify the original IBM project.
Absolute ROM paths are generated inside the new project based on the package's
current location, so the same package can move to Windows/Linux and be recreated.
String parameter overrides are not required.

## Contents

| Folder/file | Purpose |
| --- | --- |
| rtl/ | Nine exact current RTL snapshots plus a configuration-only Vivado top |
| rom/x_checks, rom/z_checks | Ten runtime ROMs per sector, including real per-fault priors |
| sim/window_relay_tb.sv | Three overlapping windows through the established core |
| sim/beta_resampling_tb.sv | Existing LFSR/beta retry-control checks |
| sim/data/SECTOR | Detector inputs, sparse-derived parity references and expected status/positions |
| sim/beta | Separate tiny graph fixture for the beta bench |
| config/qec_paths.svh | Local test defaults; Vivado generates its own path header |
| constraints/clock.xdc | Documented 10 ns starter clock constraint |
| provenance/ | Source columns, probabilities and matrix metadata |
| manifest.json | File hashes, source identities, dimensions, budgets and prior statistics |
| verify_package.py, test_package.py | Package validation and optional local simulation |
| create_project.tcl | Project creation, simulation and optional synthesis reports |

The snapshots are generated from the canonical existing files in QEC_SU26,
not a separate BP implementation. Change canonical RTL first, then regenerate
the package into a fresh output directory. The verifier detects stale snapshots
when it can see the canonical repository files.

## Priors and configuration

Startup and bulk priors are generated per fault from the existing circuit-derived
profiles, using the repository's existing convention:

```text
min(round(2 * log((1-p)/p)), 15)
```

Python round behavior is retained. Inactive faults have a zero placeholder and
are disabled by the corresponding mask. This is the repo convention applied to
the reference graph, not an assertion of paper-author table equivalence.

Window dimensions are W=12, C=8, M=72, N_ERRORS=8640, K=12, CN_DEG=35, VN_DEG=6.
The X and Z sectors are selected independently. The RTL top's normal budgets
are T0=80, TR=60, MAX_LEGS=600 and NUM_SOL=5. The directed window bench uses
8/6 iterations, one retry and NUM_SOL=3 to exercise the existing retry path
without making this smoke test excessively long. Inherited solution-count and
seed-wrap/zero-seed behavior is recorded in manifest.json and remains unchanged.

The window bench verifies convergence of the returned correction on required
checks, masks, startup/bulk switching, retained history and carry, logical-frame
arithmetic, held commits, retry execution and reset. It does not require recovery
of the exact injected fault vector because different faults can share a syndrome.
It is a directed functional test, not a logical-error-rate benchmark.

## Synthesis and timing

The default part `xc7s50csga324-1` comes from the existing IBM_OSS_decoder.xpr.
The 10 ns period is a starter target; no existing board clock constraint was
found. Override both when the actual FPGA and clock are known:

```sh
vivado -mode batch -source vivado/window_decoder/create_project.tcl -tclargs --sector x_checks --action synth --part xc7s50csga324-1 --clock-period-ns 10 --out vivado/window_decoder/build/synth_x
```

After synthesis, reports/utilization.rpt, timing_summary.rpt and synthesized.dcp
are written inside the selected project directory. This does not run placement,
routing or bitstream generation. The selected part has not been proven to fit
this expanded hierarchy. Board pins and real input/output delay constraints are
not invented here; they belong to a later board wrapper. Inspect unconstrained
paths in the timing report before drawing hardware timing conclusions.

## Local checks and regeneration

From this package directory:

```sh
python3 verify_package.py
python3 test_package.py --mode beta
python3 test_package.py --mode window
python3 test_package.py --mode tcl
```

The full window compilation is large. It is cached and reused for both sectors.
Local test output stays under build/local. Verilator compilation uses disposable
temporary scratch space because GNU Make rejects build paths containing spaces;
the final executable and log remain inside the package. The Tcl check mocks the Vivado API to
test syntax, paths, options and project guards; it is not an actual Vivado run.

From the repository root, regenerate into a fresh directory:

```sh
python3 rtl/window_decoder/build_vivado_package.py --output vivado/window_decoder_next
```

The generator uses the canonical RTL and existing matrix exports already inside
QEC_SU26. The package excludes final-codeword handling, END flushing and a
continuous-input FIFO, which are not yet part of the implemented window path.

AMD references used for project setup: [launch_simulation](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/launch_simulation),
[memory-file initialization](https://docs.amd.com/r/en-US/ug901-vivado-synthesis/Loading-Memory-Contents-With-File-I/O-Tasks),
and [synthesis options](https://docs.amd.com/r/en-US/ug901-vivado-synthesis/Running-Synthesis-with-Tcl).
