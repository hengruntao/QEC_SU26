# Commit and effects: handwritten rebuild

The first-pass window_effects.sv body has been handwritten. A complete reference
testbench lives in reference/tb_window_effects.sv. The root package remains an
empty learning skeleton; generated/window_effects_pkg.sv contains actual constants.
See MAPPING.md for the audited finite-graph C=8 configuration, derived commit mask
and logical-basis relation to Stim. No FPGA timing success is claimed.
Existing Relay BP/C++ is untouched.

## Authoritative data, not the previous 8640-fault graph

data/ibm contains exact IBM reference H (1008 x 8785) and A (12 x 8785)
archives from https://github.com/trmue/relay, pinned by provenance.json.
The Rust loader is crates/relay_bp/src/dem.rs; it loads these archives without
changing columns. Constants and incoming e_hat must share that column order.
IBM's original license accompanies the data.

Configuration status and remaining integration questions:
- No author-exported commit mask was found. configuration/c8/commit_mask.npy
  now records an explicit earliest-detector ownership policy, with exhaustive
  graph-cut checks. It is not silently presented as the authors' mask.
- The Stim audit establishes 12 syndrome blocks plus one final-readout block;
  the remaining 72 H rows are zero. Continuous bulk-window reuse still needs
  separate validation; this export is a finite-memory graph.
- C=8 is the first explicit configuration, following our earlier controller
  default, not a paper mandate. Carry uses rows [576:648], 504 distinct committed
  fault columns and 10 inputs per row. See MAPPING.md for the derivation.
- Algorithm 2 line 18 labels the fault mask m_cvg despite defining m_cvg in
  detector space. Golden model uses m_com (8785 bits), not a detector mask.
- H matches the Stim X-memory signatures exactly. A differs by a proven
  invertible logical-basis transform plus syndrome gauge; IBM A is preserved.
  Raw Stim observable labels and IBM frame labels must not be compared directly.

## Interface and failure policy

Request transfer: in_valid && in_ready; e_hat and converged belong to that request.
Response transfer: out_valid && out_ready; outputs must remain stable while stalled.
Reset clears accumulated frame and pending response. The eventual RTL must not
update the frame twice under backpressure. Invalid inputs do not create responses.
Golden model is transaction-based and does not prescribe pipeline latency.

Successful request: e_com=e_hat & m_com, delta_f=A*e_com, frame ^= delta_f,
carry=(H*e_com)[C*72:(C+1)*72]. All products are GF(2).
Failure: frame unchanged, carry zero, out_success=0, but a valid response still
acknowledges the request. Window buffer must NOT advance/apply carry on failure.
No converged result is fabricated. One global reset starts a new frame session.

## Support software

Create a Python environment and install requirements.txt. From this directory:

```sh
python3 -m unittest -v test_support
python3 generate_effects_constants.py --mask path/to/commit_mask.npy --commit-cycles 8 --mask-source "reviewed source and rule"
python3 check_effects_constants.py --mask path/to/commit_mask.npy --commit-cycles 8
python3 generate_effects_vectors.py --mask path/to/commit_mask.npy --commit-cycles 8
```

C=8 above is an example invocation, not a validated IBM window setting.
Generator emits generated/window_effects_pkg.sv and a JSON manifest. It only
exports the commit mask, 12 pre-masked A rows and 72 pre-masked H carry rows;
it never creates the RTL body. The checker uses an independent dense NPZ reader.
Each row bit j selects fault j, and packed hex bit 0 is the rightmost digit's LSB.
The empty handwritten package is NOT compiled alongside the generated package.

Vectors include directed, random, invalid, failed and session-reset transactions.
transactions.txt columns: reset input_valid converged e_hat_hex output_valid
success carry_hex frame_hex. Each line is a transaction, not a clock cycle.
The future handwritten SV scoreboard must also test stalls and consecutive input.

For captured full-size Relay runs, --relay-captures captures.json accepts:

```json
{
  "source_hashes": {"H": "sha256", "A": "sha256", "mask": "sha256"},
  "provenance": "core revision, configuration and run identity",
  "transactions": [{"e_hat_hex": "...", "converged": true, "reset": true}]
}
```

Hashes must match the manifest. No real full-size Relay captures are supplied:
the current core is 144 variables, and its outputs cannot validate this interface
by padding. Synthetic support-test fixtures are explicitly not Relay evidence.

## Vivado 2025.1

From QEC_SU26, the learning project can be opened now:

```tcl
set argv {--action create}
source rtl/window_effects/run_effects_vivado.tcl
```

After handwriting the bodies, remove IMPLEMENTATION_PENDING markers and run
the checker first. Then choose --action sim or --action synth, provide --mask
and --commit-cycles, and use a fresh --out. --python selects the Python executable
with NumPy installed. The script refuses simulation/synthesis of empty skeletons.

Synthesis uses xcvu19p-fsva3824-2-e out-of-context at 12 ns, so the internal
8785-bit interface is not treated as physical FPGA pins. Reports include detailed
critical paths, utilization and unconstrained-path checks. Clock-only OOC timing
is for register-to-register logic; input/output timing budgets remain integration
work. Positive post-synthesis slack is not routed timing closure or an Fmax claim.
No Vivado run is possible on this host, and no timing result exists yet.
