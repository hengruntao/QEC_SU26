# Full-size mapping audit and first C=8 configuration

## What was checked

The original 1008 x 8785 H and 12 x 8785 A are preserved byte-for-byte.
The pinned Rust reference's gross X-memory circuit supplies an independent
detector interpretation. Its measurement-record dependencies, not its coordinate
labels, identify 12 regular 72-detector syndrome blocks followed by a 72-detector
final-data-readout block. Ancilla identities establish consistent row order.
All 8784 nonzero IBM H column signatures match these Stim signatures one-to-one.
The other 72 matrix rows (936..1007) are zero. Column 8784 is zero in H and A.
These are observed unused entries; their original allocation rationale is not known.

Thus 1008 rows does NOT mean 14 active syndrome cycles. The stored graph is a
finite 12-round memory graph with a final-readout boundary and an unused row block.
The 8784 nonzero columns have 720 earliest-detector owners per syndrome block and
144 in the final-codeword block. Every nonzero column touches at most adjacent
blocks. No fault-column reordering or padding was introduced by our tools.

## Commit policy, explicitly derived

Current verified small Relay RTL has no commit-width setting. C=8 follows the
earlier window-controller default, not a claim that the paper mandates eight.
For the first configuration define:

    m_com[j] = 1 if any H[r,j] is 1 with r < C*72, otherwise 0.

Equivalently, assign each nonempty fault column to its earliest detector block
and commit owners < C. This is a derived ownership policy, NOT an author-exported
mask or a proven physical gate-time label. The audit checks exhaustively that:
- No uncommitted column contributes to checks in the committed region.
- No committed column contributes beyond cycle C.
- Therefore all future detector effects of a committed estimate fit in one carry.

For C=8 there are 5760 committed faults, 504 distinct carry-contributing columns,
and exactly 10 contributing faults per carry row. These 504 columns all belong to
owner block 7: only faults crossing the 7/8 cut can affect carry. The distinct-column
count and XOR-input count differ because one column can touch multiple detectors.
Frame row weights are 480,480,480,480,480,480,544,544,608,576,672,608.
The final-codeword faults and the all-zero column are excluded from this mask.

## Logical convention: do not silently relabel bits

The stored IBM A is not numerically identical to the selected Stim observables
after H-based fault matching. The audit proves the exact identity:

    A_IBM = T * A_Stim + G * H   (over GF(2))

T is invertible with rank 12; G specifies syndrome-row parity combinations.
All coefficients are saved in configuration/c8/mapping_audit.json, and the
identity is checked across every fault column. IBM A remains unchanged.
Comparing IBM frame bits directly against Stim logical labels is incorrect.
For any e, apply T to the Stim observables and XOR G*(H*e) before comparing.

## Artifacts and reproduction

configuration/c8/commit_mask.npy: explicit derived binary mask in IBM column order.
configuration/c8/mapping_audit.json: hashes, row identities, ownership counts,
carry support and exact logical/gauge transformation.
generated/window_effects_pkg.sv: generated constants; not the empty handwritten package.
vectors/: golden transaction vectors using this finite-graph C=8 configuration.
data/ibm/gross_x_memory_12_rounds.stim: exact upstream circuit bytes, original
path recorded below and in the audit-source metadata.

From rtl/window_effects, with requirements-audit.txt installed:

```sh
python3 audit_window_mapping.py --circuit data/ibm/gross_x_memory_12_rounds.stim --commit-cycles 8 --output configuration/c8
python3 generate_effects_constants.py --mask configuration/c8/commit_mask.npy --commit-cycles 8 --mask-source "Derived earliest-detector ownership; see MAPPING.md and mapping_audit.json"
python3 check_effects_constants.py --mask configuration/c8/commit_mask.npy --commit-cycles 8
python3 generate_effects_vectors.py --mask configuration/c8/commit_mask.npy --commit-cycles 8
python3 -m unittest -v test_mapping_audit
python3 run_local_effects_test.py
```

Upstream circuit: tests/testdata/bicycle_bivariate/circuit=bicycle_bivariate_144_12_12_memory_X,distance=12,rounds=12,error_rate=0.001,noise_model=uniform_circuit,basis=CX,A=x^3+y+y^2,B=y^3+x+x^2.stim
Reference commit: d185194ba0cb4101ced4340d82b2ee6d42f225f0.

Local Verilator simulation passed 136 Python-golden transactions against the
handwritten RTL with these IBM constants and derived mask: 105 success-flagged,
18 failed and 13 invalid transactions, 366 stall cycles and reset recovery.
These are effects-unit stimuli, not actual Relay convergence results. The local
runner reproduces them and records logs/hashes under build/local_c8.

## Limits of this result

This validates a finite-graph effects configuration and its derived commit mask.
It does not prove that the finite graph's initialization/final-readout columns
or logical gauge can be reused unchanged for every sliding bulk window. That
must be reconciled with the future full-size core/window-buffer configuration.
Real Relay-run captures, continuous-window integration and VU19P timing remain
separate requirements. A random converged-flag input tests effects arithmetic,
not whether Relay BP would actually converge on that estimate.
