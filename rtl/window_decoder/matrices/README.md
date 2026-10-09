# Window matrix definitions

The generated hardware/ subdirectory in each sector now supplies a common
8640-column graph for startup and bulk. See ../PHASE2.md for its active masks,
profile remapping, effects RTL, and complete verification commands. The original
startup/bulk reference definitions below are retained for source comparisons.

These files define the matrix inputs needed by Algorithm 2 (page 16) of
"Real-time decoding of the gross code memory with FPGAs". They were generated
from the gross-code memory circuits in the paper-linked Relay repository,
not from an unpublished author FPGA configuration.

## Sources and scope

Source repository: https://github.com/trmue/relay

Local reference revision: d185194ba0cb4101ced4340d82b2ee6d42f225f0.
Inputs are the two tests/testdata/bicycle_bivariate circuits with
144_12_12_memory_X and 144_12_12_memory_Z, rounds=12, error_rate=0.001,
noise_model=uniform_circuit, basis=CX, A=x^3+y+y^2, B=y^3+x+x^2.
Every manifest records its input filename, SHA-256 digest, and Stim version.
The p=0.001 priors are reference priors, not fixed production decoder settings.

The PDF specifies W=12 for the gross code and the matrix operations. It does
not supply exact matrix entries, the detector-index mapping, or a complete
commit-mask construction. The policies below are explicit implementation
choices consistent with Algorithm 2's dimensions and single-cycle carry.
They require research review before claiming equivalence to the paper's tables.
The supplied circuits are reference examples, not proof of an identical
gate schedule or noise configuration to the paper's FPGA experiment.

This step generates definitions and test data. It does not change the RTL,
connect Relay-BP, quantize priors, or validate logical-error rates.

## The generated matrices

There are four configurations under generated/: x_checks/startup,
x_checks/bulk, z_checks/startup, and z_checks/bulk.
Sector names describe the measured checks: X checks detect Z-type errors;
Z checks detect X-type errors. Y faults can contribute to both sectors.
Decoding the sectors independently discards their cross-sector correlations.

| Object | Dimensions | Purpose |
| --- | --- | --- |
| H_tilde | 864 x N_ERRORS | Window detector flips produced by each error column |
| A_tilde | 12 x N_ERRORS | Logical flips produced by each error column |
| H_hat | 72 x 144 | Noiseless syndrome calculated from final codeword |
| L | 12 x 144 | Logical readout calculated from final codeword |
| m_com | N_ERRORS bits | Columns touching the first C detector cycles |
| m_cvg | 864 bits | Detector checks in the first C cycles |

N_ERRORS is 8640 in both bulk configurations and X startup, and 8568 in
Z startup. These are circuit-fault signatures, not 144 physical data qubits.
The matrices have irregular connectivity; the current fixed-degree Relay-BP
fabric cannot consume them without adaptation.

The reference C=8 selects the paper's illustrated (12,8) setting, not a uniquely
prescribed stride. manifest.json also exports masks for every C=1,...,11.
Changing C requires selecting the corresponding carry rows as well as masks.
The phase-1 controller still treats C as a compile-time parameter; runtime
stride configuration is a future change.

## Exact ordering and construction

1. Read each Stim detector's measurement-record dependencies. Classify it by
   M or MX readout basis; group it by its latest measurement group. Each sector
   has 13 blocks of 72 detectors: 12 syndrome rounds and a final readout boundary.
2. Preserve detector declaration order within each sector block. Verify that
   the referenced syndrome-ancilla qubit order is identical in every block.
   The manifest records these ancilla IDs and original detector IDs.
3. Generate an undecomposed Stim detector error model. Keep each mechanism's
   detector effects in this sector and all its observable effects. Reject
   detector-invisible logical mechanisms, rather than guessing their window
   ownership. None occur in these two inputs.
4. Anchor each mechanism to its earliest affected sector cycle. Represent its
   detector support relative to that cycle. Reject support spanning more than
   two adjacent cycles; all retained faults in these inputs satisfy this bound.
5. Within each anchor cycle, merge mechanisms only if BOTH the full relative
   detector support and logical support agree. Their independent parity prior
   combines as p_new = p_old + p - 2*p_old*p, not p_old+p. Source mechanism IDs
   remain in templates.json for traceability. This is a merge of Stim DEM
   mechanisms, not a claim that a column uniquely identifies a physical gate fault.
6. Sort the merged signatures lexicographically by detector support then logical
   support. Order window columns by anchor cycle then by that signature order.
   columns.json explicitly records every resulting column and its prior.

Detector bit r = t*72+i means detector i in local cycle t. The earliest cycle
occupies the least-significant 72 bits, matching window_decoder_ctrl.
Error bit j means column j of BOTH H_tilde and A_tilde. Logical bit l means
Stim observable L_l. Preserve this basis; do not substitute the existing
qLDPC-generated logical operators without a verified basis conversion.

For H_hat and L, codeword bit q indexes the manifest's ascending data_qubits
list. This is important because the circuit's final measurements interleave
qubit IDs (0,72,1,73,...). H_hat takes the final data-measurement terms in each
final detector; L takes the final measurement terms in OBSERVABLE_INCLUDE.

## Startup, bulk, and boundaries

startup is an exact matrix projection of the supplied finite experiment's first
12 sector detector blocks, using that circuit's actual priors at each cycle.
Final-only mechanisms anchored at cycle 12 are excluded. It is a reference for
that finite circuit, not a complete model of every startup/flush configuration.
In particular, the Z circuit's last regular cycle has boundary-dependent priors.

bulk repeats the interior anchor-cycle-1 template over 12 local cycles. Before
doing so, the generator checks that all other interior anchor cycles 2 through
10 have the same signatures and probabilities (within floating-point tolerance).
It therefore defines a stationary extension inferred from the reference circuit.
It does not come from a longer circuit supplied by the authors.

Each column retains its effects outside the right window edge in
boundary_detectors. H_tilde omits those rows but retains the column: this is an
open right boundary. Masked convergence requires only the committed detector
region, allowing the undecided right edge to remain unconverged. Error columns
at that edge are not committed.

The commit policy selects all columns with earliest affected cycle < C.
The convergence policy selects detector rows < C*72. For every supported C,
the generator verifies that all columns touching a committed detector are
selected, and that their remaining support reaches at most cycle C. Thus the
only retained-cycle detector correction is precisely the M-bit carry in
Algorithm 2. These are checked structural properties, not a logical-error-rate
guarantee or evidence that the authors chose the identical masks.

The original startup and bulk profiles have different Z-sector column counts.
The hardware/ graph reconciles these through an exact common-column mapping and
explicit inactive startup columns. Use its profiles.json mapping when translating
reference error vectors. END padding and final decode scheduling remain future work.

## File format and RTL use

Each *.mem file contains one row per line, hexadecimal, with column/bit zero
at the RIGHTMOST (least-significant) bit. Files are suitable for $readmemh.
The row width is N_ERRORS for window/effects matrices and 144 for final readout
matrices. window_dimensions.svh contains localparams for inclusion inside a module.

| File | Contents |
| --- | --- |
| h_tilde_rows.mem | Full window parity-check rows |
| a_tilde_rows.mem | Full window logical-action rows |
| carry_rows.mem | H_tilde[C*72:(C+1)*72] with columns ANDed by m_com |
| frame_rows.mem | A_tilde with columns ANDed by m_com |
| h_hat_rows.mem | Noiseless final-codeword syndrome rows |
| logical_readout_rows.mem | L rows |
| commit_mask.mem | One N_ERRORS-bit row for the example C |
| convergence_mask.mem | One 864-bit row for the example C |
| columns.json | Sparse column definitions, priors, template IDs, omitted boundary support |
| templates.json | Relative signatures and original DEM mechanism IDs |
| manifest.json | Dimensions, ordering, source hash, policies, all stride masks |

For an estimated error vector e:

```text
e_com = e AND m_com
delta_f[l] = XOR_j(A_tilde[l,j] AND e_com[j])
delta_d[r] = XOR_j(H_tilde[r,j] AND e_com[j])
u[i] = delta_d[C*72+i]
```

The effects block may use pre-masked carry_rows and frame_rows with e, or use
the full matrix rows with e_com. These are equivalent. The current controller
already outputs e_com; masking a second time does not change the answer.

## Reproduce and verify

Install requirements.txt into a Python environment, then from this directory:

```sh
make generate PYTHON=/path/to/environment/bin/python
make test PYTHON=/path/to/environment/bin/python
```

RELAY_ROOT defaults to the sibling Relay checkout and can be overridden.
The environment used here is /tmp/qec-matrix-venv/bin/python. It is temporary;
requirements.txt records dependencies for a lasting environment.

Verification includes hand-calculated XOR examples, every merged column,
129024 individual source-mechanism replays through Stim across both sectors,
128 combined-fault replays, 512 final-codeword conversions through Stim,
random column-XOR comparisons for all 11 strides, exact exported-mask and
row-order checks, rank-66 noiseless checks, rank-12 logical readouts, cross-sector
stabilizer commutation, and full-rank logical pairing.

These tests establish matrix extraction and arithmetic consistency with the
selected Stim circuits and documented projection. They do not establish equality
to the paper authors' unpublished tables, full streaming decoder correctness,
Relay-BP accuracy, or FPGA resource/timing feasibility.
