# Established Relay-BP window integration

## Scope

The decoder is the repository's `relay_bp_top.sv`, instantiating its original
`cnu.sv` and `vnu.sv`. No BP equations, LFSR, beta generator, or retry algorithm
are reimplemented in the window directory.

Changes to existing RTL are deliberately limited:

- Parameterize check/variable counts, CN/VN degrees and the two connectivity
  filenames. Default dimensions and filenames remain the original ones.
- Widen variable/port indexes and correction-weight accumulation as needed.
- Add optional WINDOW_MODE (default off), convergence mask and active mask.
  Unused CN slots carry neutral +15; unused VN slots receive zero messages.
- In WINDOW_MODE, snapshot the converged VNU decision vector before scanning
  its weight. The VNU decision is combinational from M_j_next and can change
  after the VNU update edge; without this snapshot a different, unchecked
  candidate could be committed. Legacy mode retains its original behavior.
- Replace the VNU's hardcoded sum of three messages with an ordered DEG loop,
  preserving its original ten-bit sum width for the existing MJ_W=8 setting.
  The window maximum degree six fits this width.
- Fix beta resampling in the existing VNU: sample on new_leg independently of
  en, because S_NEW_LEG precedes S_VNU_PHASE. The new beta is available before
  the next VN update. LFSR taps/seeds/advance and beta calculation are unchanged.

The CNU, package, sign-magnitude message format, beta arithmetic, rounding and
truncation, memory updates, outgoing-message saturation, LFSR taps/seeds/advance,
and original top-level retry/solution-count schedule are unchanged.

## Adapter and ports

`relay_window_adapter.sv` captures syndrome, masks, and selected four-bit priors,
then releases reset on the original one-shot core. It captures done/result and
holds a ready/valid response. Each new window starts a fresh core run, including
its existing reset seeds and beta reset value. No new RNG policy is introduced.

`window_relay_top.sv` connects that adapter to the controller/effects pair.
`iter_count[6:0]` and `leg_count[9:0]` retain the original core meanings: iteration
count in the final leg and zero-based leg index, not total transaction iterations.
They are captured with the result. Global reset aborts the entire window session.

## Graph and prior configuration

```sh
python3 export_relay_graph.py matrices/generated/x_checks/hardware /tmp/relay-x
```

This exports the existing core's `cnu_to_vnu_idx.mem` and
`cnu_to_vnu_port.mem` format, padded with variable-index sentinel N_VARS.
It checks graph reconstruction and unique VN-port ownership. X and Z graphs
both use max CN degree 35 and max VN degree 6. Export each sector independently.

Set IDX_FILE and PORT_FILE to those files. Set START_PRIOR_FILE and
BULK_PRIOR_FILE to **externally selected, already quantized four-bit priors** in
the same common column order. The wrapper does not invent a probability-to-LLR
quantizer. Test fixtures explicitly use uniform priors 7 and 6; these are test
stimuli, not calibrated paper priors. The existing repository convention is
`min(round(2*log((1-p)/p)),15)` in
`python_implementation/integrated_cnu_vnu/iterations_bp.py` and
`c_claude_reference/integrated_cnu_vnu/export_bb_code.py`. The Vivado package
builder now exports this rule for every active column in hardware/profiles.json.
Inactive zero-probability entries bypass log and
use a placeholder zero; the active mask disables them. This reuses the repo's
convention but has not been established as the paper authors' exact table.
The six controller mask/effects files come from the matching
sector and stride. Production defaults are C=8.

## Verification

`test_established_relay.py` loads original RTL from commit
840d6c451bdca80842135cdbbfe5ff89871c26a6 into a temporary test directory and renames
module identifiers for side-by-side simulation. It does not store or implement
another BP core in this source tree.

- 512 VNU stimulus cases compare messages, decisions, marginals, LFSR, beta and
  memory against the original for unchanged controls (new_leg only with en);
  DEG=6 with three zero ports also matches DEG=3.
  A directed nonzero-extra-port test verifies the degree extension is active.
- Eight 500-cycle default-sized core runs with MAX_LEGS=0 compare outputs, done,
  convergence, iteration and leg counts with the original, preserving first-leg
  behavior. Retry results are intentionally allowed to change after the beta fix.
  The synthetic regular graph has
  the original 72x144, CN-degree-six, VN-degree-three dimensions.
- Adapter tests use actual CNU/VNU instances: success, nonzero corrections,
  unsatisfiable checks, masked checks, inactive variables, profile changes,
  response stalls, input mutation after acceptance, reset abort, and reuse.
- Connected tests feed three overlapping windows and check the actual returned
  candidate against H, independently compute carry/frame, check the next request
  and startup-to-bulk transition, and stall commits. Small and full X/Z-sector
  configurations have separate targets; full-size compilation is expensive.
- The real-effects suite tests 17,412 vectors over both sectors.
- `beta_resampling_tb.sv` checks sampling with en=0, use by the first following
  VN update, stable memory/LFSR at the boundary, ordinary LFSR advancement,
  beta holding between legs and reset. It also follows the actual top through
  two retries after success/weight scanning and two after iteration exhaustion.
  The fixture connectivity for this small bench is generated by `beta_test`.

These checks establish compatibility and integration, not exact paper fidelity
or a logical-error-rate benchmark. Wider stride/noise coverage and production
prior calibration remain work.

## Inherited issues intentionally not redesigned

Inspection found existing behavior that should be reviewed separately:

- Seeds remain `8'(j+1)`. At larger graph sizes they repeat and include zero,
  an absorbing state of the original LFSR. No substitute seed scheme is added.
- The original solution stop comparison uses NUM_SOL-1 after sol_cnt increments.
  Its existing count behavior is preserved, not advertised as fixed.

These are not new architectural choices, but they limit claims of a correctly
randomized Relay search. Any fixes should be explicit and separately tested.

## Before Vivado

The package in `../../vivado/window_decoder` includes the established hierarchy,
a portable self-checking testbench, matching ROMs and a project script.
Confirm FPGA part/clock and inspect synthesis,
resource usage, graph routing and timing before claiming hardware readiness.

Final codeword processing, END padding/flushing and an upstream input FIFO are
not implemented. They do not block testing the current window transaction.

See [VIVADO_PACKAGE.md](VIVADO_PACKAGE.md) for the package file checklist.
