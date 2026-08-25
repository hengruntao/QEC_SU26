# C implementation

C port of the Int4.2.8 CNU/VNU models and the BP decoders that drive them.

Unlike the Python side, this tree has **no external dependencies** — no qLDPC,
no NumPy, no SymPy. All it needs is a C99 compiler and `libm`.

## Layout

| C file | ported from |
|---|---|
| `cnu/cnu_int4.{h,c}` | `cnu_python/cnu_int4.py` |
| `cnu/cnu_int4_demo.c` | the `__main__` block of `cnu_int4.py` |
| `vnu/vnu_int4.{h,c}` | `vnu_python/vnu_int4.py` |
| `vnu/vnu_int4_demo.c` | the test block of `vnu_int4.py` |
| `integrated_cnu_vnu/matrix_generator.{h,c}` | `integrated_cnu_vnu/matrix_generator.py` |
| `integrated_cnu_vnu/iterations_bp.c` | `integrated_cnu_vnu/iterations_bp.py` |
| `integrated_cnu_vnu/iterations_dmem_bp.c` | `integrated_cnu_vnu/iterations_dmem_bp.py` |
| `integrated_cnu_vnu/unit_test_for_mult.c` | `integrated_cnu_vnu/unit_test_for_mult.py` |

Supporting modules with no Python counterpart:

| C file | why it exists |
|---|---|
| `integrated_cnu_vnu/gf2.{h,c}` | dense GF(2) linear algebra — replaces the qLDPC calls |
| `integrated_cnu_vnu/np_random.{h,c}` | bit-exact clone of `np.random.seed` / `np.random.rand` |
| `integrated_cnu_vnu/mem_strength.{h,c}` | `memory_strength_mult()`, which Python defines twice |
| `integrated_cnu_vnu/bp_common.{h,c}` | Tanner-graph build + NumPy-compatible printing |

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

`make check` diffs every program's stdout against `tests/expected/`, which holds
the **verbatim output of the Python scripts**. A clean pass means the port is
byte-for-byte faithful, down to NumPy's line wrapping.

## How the qLDPC dependency was removed

`matrix_generator.py` gets its matrices from `qldpc.codes.BBCode`. The C version
builds them directly from the bivariate-bicycle definition (gross code
`[[144,12,12]]`, `l = 12`, `m = 6`):

```
x = S_l (x) I_m       y = I_l (x) S_m       S_n = cyclic shift, S[i,(i+1)%n] = 1
A = x^3 + y + y^2     B = y^3 + x + x^2
H_x = [A | B]         H_z = [B^T | A^T]
```

`H_x` and `H_z` come out **bit-identical** to qLDPC's `code.matrix_x` and
`code.matrix_z` (verified by direct comparison).

The logical operators are recomputed here as the quotient spaces
`ker(H_z)/rowspace(H_x)` and `ker(H_x)/rowspace(H_z)`, then symplectically
paired so `A_x @ A_z^T = I`.

`A_x` and `A_z` are **not** bit-identical to `code.get_logical_ops()`, and they
cannot be: a logical operator is only defined up to multiplication by a
stabilizer, so every valid basis is a different, equally correct set of
representatives. What matters is that the decode verdict is the same, and it
provably is. For any `e` in `ker(H_x)` — which is exactly the case the decoder
tests, since `H(ê + e) = 0` once BP has converged — `A_x @ e = 0` holds for this
basis if and only if it holds for qLDPC's. This was checked two ways: the two
matrices span the same row space when restricted to `ker(H_x)`, and 20 000
random kernel vectors gave the identical verdict for both. `matrix_generator.c`
also asserts the three validity conditions at startup and aborts if any fails:

```
H_z @ A_x^T = 0      H_x @ A_z^T = 0      A_x @ A_z^T = I_k
```

## Reproducing the Python error pattern

`np_random.c` is a bit-exact reimplementation of NumPy's legacy MT19937
`RandomState`: Knuth's seeding, and doubles built from two 32-bit draws as
`((a >> 5) * 2^26 + (b >> 6)) / 2^53`. That is what lets the C decoder run on
the *same* error vector as `np.random.seed(21); np.random.rand(144)`, so the two
implementations can be diffed rather than merely compared statistically.

## Verification performed

* `make check` — all five programs byte-identical to the Python output.
* `H_x`, `H_z` bit-identical to qLDPC's.
* `A_x` proven equivalent to qLDPC's for every `e` in `ker(H_x)` (see above).
* A 200-run sweep (both decoders × `p` ∈ {0.05, 0.1, 0.15, 0.2} × seeds 0–24)
  against the real Python scripts: **200/200 byte-identical**. Coverage included
  59 converged and 141 non-converged runs, and the two converged-but-logically-
  failed runs whose verdict actually depends on the `A_x` basis.
* Clean under `-Wall -Wextra -pedantic`, clean under ASan + UBSan, no leaks.

## Deliberate differences from the Python

* `memory_strength_mult()` is defined once and shared, rather than copy-pasted
  into both `iterations_dmem_bp` and `unit_test_for_mult`.
* The Tanner-graph construction and result printing, which the two Python
  decoder scripts repeat verbatim, live in `bp_common.c`. The BP iteration loop
  itself is still written out in full in each decoder, so the two can be read
  side by side with their Python originals.
* `min1 >> t` is guarded for `t >= 31`. Python shifts arbitrarily far and yields
  0; in C that would be undefined behaviour, and the BP loop drives `t` to 60.
* Degrees are bounded at compile time (`CNU_MAX_DEGREE`, `VNU_MAX_DEGREE`,
  `MAX_CHECK_DEGREE`, `MAX_VARIABLE_DEGREE`, all 16) instead of using growable
  lists. The gross code needs 6. Exceeding a bound is a hard error, not silent
  corruption.

## Changing the experiment

The knobs are near the top of `iterations_bp.c` / `iterations_dmem_bp.c`:

```c
#define MAX_ITERATION       60
#define RANDOM_SEED         21
#define INT4_SCALE_FACTOR   2
static const double p = 0.1;
```

To decode X-type errors instead, swap `get_H_x()` for `get_H_z()` and `get_A_x()`
for `get_A_z()`. Note that `tests/expected/` is pinned to the values above, so
`make check` will report a diff after any such change — that is the intended
behaviour, not a regression.
