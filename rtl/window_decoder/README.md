# Sliding-window decoder with the established Relay-BP

The active hierarchy is:

```text
window_relay_top
  window_decoder_top
    window_decoder_ctrl
    window_effects
  relay_window_adapter
    relay_bp_top (existing RTL, parameterized)
      cnu (existing, unchanged)
      vnu (existing, degree-generalized sum only)
```

There is no second BP implementation or software BP arithmetic oracle. The
previous replacement and its tests were removed, as were the older fake stub
and stub-only tests. C and C++ are not changed.

Default window dimensions: W=12, C=8, M=72, 8640 fault variables, 12 logical bits.
The controller accepts detector cycles using valid/ready, holds commit results
until accepted, carries corrections into the next window, and accumulates the
logical frame. It halts on failure. Input must pause during processing.

## Run verification

The self-contained Vivado package is in `../../vivado/window_decoder`, including
RTL snapshots, both sectors' ROMs, self-checking benches, constraints and
`create_project.tcl`. See its README for run and regeneration commands.

```sh
make test-relay       # Established RTL equivalence, adapter, connected small graph
make test-relay-full  # Full X/Z 8640-variable connected tests; large build
make test-effects
make lint
make test-matrices PYTHON=/path/to/stim/environment/bin/python
```

Verilator and a C++ compiler are needed to simulate the existing struct-array
CNU/VNU hierarchy. This compiles simulator-generated C++, not project C++.
Icarus is used for the effects tests. Artifacts default to `/tmp/qec-window-sim`.
Legacy-core lint warnings are reported, not hidden; lint uses nonfatal warnings
for that hierarchy because the unchanged arithmetic has existing width warnings.

See [RELAY_INTEGRATION.md](RELAY_INTEGRATION.md) for the exact scope of changes,
known inherited behavior, graph/prior configuration, and remaining validation.
See [matrices/README.md](matrices/README.md) for matrix provenance and conventions.
