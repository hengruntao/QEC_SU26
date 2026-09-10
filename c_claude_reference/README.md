# C implementation

C port of the Int4.2.8 CNU/VNU models and the BP decoders that drive them.

The runtime side needs only a C99 compiler — no qLDPC, no NumPy, no SymPy, and
no libm.

## The split: fixed data offline, iteration logic in C

The Python side leans on `qldpc` for the check matrix and `numpy` for the error
pattern. Neither is runtime data — the gross code `[[144,12,12]]` matrix and its
logical operators are compile-time constants, and the error patterns are test
vectors. So they are generated **once** by `export_bb_code.py` and linked in as
C arrays, instead of reimplementing GF(2) linear algebra and MT19937 in C.

That removes about 950 lines from the C side (dense GF(2) nullspace/RREF/inverse,
the bivariate-bicycle construction, a NumPy-compatible Mersenne Twister, and the
NumPy array-printing emulation). What is left is the part actually worth writing
in C: the CNU, the VNU, and the iteration loop.

```
export_bb_code.py  ──(qLDPC, numpy — run once)──>  bb_code_data.{h,c}
                                                   bp_test_data.{h,c}
                                                          │
                                                          ▼
                                          C: bp_decoder.c + cnu_int4.c + vnu_int4.c
```

Both generated pairs are **checked into git**: qLDPC is not installed
everywhere, and the data only changes if the code parameters do.

## Layout

| C file | ported from |
|---|---|
| `cnu/cnu_int4.{h,c}` | `cnu_python/cnu_int4.py` |
| `cnu/cnu_int4_demo.c` | the `__main__` block of `cnu_int4.py` |
| `vnu/vnu_int4.{h,c}` | `vnu_python/vnu_int4.py` |
| `vnu/vnu_int4_demo.c` | the test block of `vnu_int4.py` |
| `integrated_cnu_vnu/bp_decoder.{h,c}` | the iteration loop of both `iterations_*.py` |
| `integrated_cnu_vnu/iterations_bp.c` | `iterations_bp.py` (driver + reporting) |
| `integrated_cnu_vnu/iterations_dmem_bp.c` | `iterations_dmem_bp.py` (driver + reporting) |
| `integrated_cnu_vnu/unit_test_for_mult.c` | `unit_test_for_mult.py` |
| `integrated_cnu_vnu/mem_strength.{h,c}` | `memory_strength_mult()`, which Python defines twice |

Generated and test-only:

| file | what it is |
|---|---|
| `integrated_cnu_vnu/export_bb_code.py` | the generator — replaces `matrix_generator.py` |
| `integrated_cnu_vnu/bb_code_data.{h,c}` | Tanner graph, slot tables, logical operators |
| `integrated_cnu_vnu/bp_test_data.{h,c}` | error patterns + Python reference results |
| `integrated_cnu_vnu/test_bp.c` | regression test over every case, both decoders |

Plain BP and DMem-BP differ by exactly one block, so `bp_decode()` takes a
`use_dmem` flag rather than existing twice.

## Build and run

```bash
make
```

```bash
make run
```

```bash
make check
```

```bash
make generate
```

`make generate` re-runs the exporter and needs an interpreter with qLDPC; the
Makefile defaults to `PYTHON = /opt/anaconda3/envs/relay_bp/bin/python`.
Everything else builds and runs with no Python at all.

## What gets exported, and why each piece

`bb_code_data.c` holds four tables. The first two are the Tanner graph; the
second two are the part worth explaining.

**The dense H is never exported.** Every use of `H` in the decoder is
`H @ vec mod 2`, and the nonzero positions of row `ii` are exactly
`check_node_neighbor[ii]`. So the syndrome is an XOR over 6 entries rather than
a 144-term dot product, and 10368 zeros/ones collapse to 432 indices.

**The two `list.index()` lookups are precomputed.** Python redoes these on every
edge on every iteration:

```python
index  = variable_node_neighbor[jj].index(ii)    # assembling the CNU input
vn_idx = check_node_neighbor[cn].index(jj)       # assembling the VNU input
```

They are fixed by `H`, so they ship as `cnu_src_slot` and `vnu_src_slot` and the
CNU↔VNU regrouping becomes a pure gather:

```c
cnu_inputs[ii][d] = vnu_message[check_node_neighbor[ii][d]][cnu_src_slot[ii][d]];
```

That regrouping — the row-view ↔ column-view transpose — is the fiddliest part
of the integration layer, and this turns it into table lookups with no search.

**`logical_A_x`** is the X-type logical operator basis, needed for the
`A_x @ (ê ^ e) == 0` check. Taken straight from qLDPC's `get_logical_ops()`, so
unlike the earlier hand-rolled version there is no question of basis equivalence.

## Verification

`make check` does two things:

1. **`test_bp`** — runs both decoders over all 21 exported cases and compares
   every bit of `e_hat`, the iteration count, and both success flags against
   the Python reference results baked into `bp_test_data.c`. 42 runs, covering
   14 converged, 28 non-converged, and 2 converged-but-logically-failed cases
   (the last are the only runs whose verdict depends on the logical basis).
2. **golden diffs** — `cnu_int4_demo`, `vnu_int4_demo` and `unit_test_for_mult`
   are diffed byte-for-byte against the verbatim Python stdout in
   `tests/expected/`.

Separately confirmed by hand: `iterations_bp` and `iterations_dmem_bp` reproduce
the real `iterations_bp.py` / `iterations_dmem_bp.py` exactly — all 144 bits of
`e_hat`, all 72 bits of the syndrome, the iteration counts (5 and 6), the sums,
and the verdicts.

Also clean under `-Wall -Wextra -pedantic`, ASan, and UBSan.

Note that `test_bp` compares *decoded values*, not printed text. That is a
stronger check than the previous byte-for-byte stdout diff against Python, and
it is why the decoders no longer emulate NumPy's array formatting.

## Deliberate differences from the Python

* The check matrix, logical operators, and error patterns are generated ahead of
  time rather than computed at startup (see above).
* `memory_strength_mult()` is defined once and shared, rather than copy-pasted
  into both `iterations_dmem_bp` and `unit_test_for_mult`.
* The iteration loop lives once in `bp_decoder.c` with a `use_dmem` flag,
  instead of being duplicated across two near-identical scripts.
* `min1 >> t` is guarded for `t >= 31`. Python shifts arbitrarily far and yields
  0; in C that would be undefined behaviour, and the loop drives `t` to 60.
* Degrees are compile-time constants from the generated header
  (`CHECK_DEGREE` 6, `VARIABLE_DEGREE` 3), with a build-time assertion that they
  fit `CNU_MAX_DEGREE` / `VNU_MAX_DEGREE`.

## Changing the experiment

Error rates and seeds live in `TEST_CASES` at the top of `export_bb_code.py`;
edit and run `make generate`. Case 0 is what `iterations_bp` and
`iterations_dmem_bp` report, so keep the case you want as the headline first.

`BP_MAX_ITERATION` is in `bp_decoder.h` — change it in `export_bb_code.py` too,
or the golden data will disagree.

To decode X-type errors instead, switch `get_H_x()`/`get_A_x()` to
`get_H_z()`/`get_A_z()` in `export_bb_code.py` and regenerate; no C changes.
