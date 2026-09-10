#!/usr/bin/env python3
"""
export_bb_code.py -- the one place qLDPC is used.

WHY THIS FILE EXISTS
--------------------
The C decoder needs two constants that describe the gross code [[144,12,12]]:

    H_x   the X-type check matrix        72 x 144
    A_x   the X-type logical operators   12 x 144

H_x is cheap: it is just a polynomial in cyclic shift matrices, and writing it
out in C takes about 40 lines and no library at all.

A_x is not.  Deriving it means computing ker(H_z), quotienting by the row space
of H_x, and symplectically pairing the result against the Z-side basis -- that
is dense GF(2) nullspace, RREF, quotient basis and matrix inverse, roughly 500
lines of C that exist only to reproduce a table that never changes.

So A_x is the real reason this script exists.  Since a Python pass is needed
for it anyway, H_x rides along: exporting both keeps the C side free of the
bivariate-bicycle construction too, and makes the generated file line up
one-to-one with matrix_generator.py's get_H_x() / get_A_x().

Everything DERIVED from H (the Tanner graph, the per-edge slot indices) is
deliberately NOT exported.  That derivation is 31 lines of C, and having it
visible in bp_decoder.c is worth more than saving those lines -- it is the part
a reader needs to follow to understand the CNU/VNU regrouping.

This script also exports a batch of decode cases with the results the Python
reference produces, so the C side can be regression-tested with no interpreter
present.  That replaces reimplementing NumPy's Mersenne Twister in C.

OUTPUT
------
    bb_code_data.{h,c}   H and A_x
    bp_test_data.{h,c}   error patterns + reference decode results

Both pairs are checked into git: qLDPC is not installed everywhere, and the
data only changes when the code parameters do.

USAGE
-----
Needs an interpreter with qldpc installed:

    /opt/anaconda3/envs/relay_bp/bin/python export_bb_code.py

or, from the parent directory:

    make generate
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# The Python reference implementation lives two levels up.  Importing it -- as
# opposed to re-deriving anything here -- is deliberate: the golden results
# below must come from the exact functions the Python scripts call, or they
# would not be a reference at all.
sys.path.insert(0, os.path.join(REPO, "integrated_cnu_vnu"))
sys.path.insert(0, os.path.join(REPO, "cnu_python"))
sys.path.insert(0, os.path.join(REPO, "vnu_python"))

from matrix_generator import get_H_x, get_A_x          # noqa: E402
from cnu_int4 import cnu_hardware_int4                 # noqa: E402
from vnu_int4 import vnu_hardware_int4                 # noqa: E402

# Must match bp_decoder.h.  Kept here as well because the golden results depend
# on it -- if the two disagree, the regression test will report a mismatch
# rather than silently comparing against the wrong thing.
MAX_ITERATION = 60

# Int4.2.8: values saturate at 15, priors are scaled by 2.
INT4_SCALE_FACTOR = 2
INT4_MAX_VALUE = 15

# DMem-BP constants, mirroring mem_strength.h.
MEM_NUM_SHIFT = 3
MEM_BETA_INT = 7
MEM_GAMMA_INT = 1

# (p, seed) pairs to export.
#
# Case 0 is what iterations_bp.py and iterations_dmem_bp.py run, so it is the
# case the two C decoder programs report -- keep it first.  The rest exist to
# give the regression test coverage of runs that do NOT converge, and of runs
# that converge to a logically wrong answer.
TEST_CASES = [(0.1, 21)]
for _p in (0.05, 0.1, 0.15, 0.2):
    for _seed in (0, 3, 7, 11, 22):
        TEST_CASES.append((_p, _seed))


# ---------------------------------------------------------------------------
# The two matrices
# ---------------------------------------------------------------------------

def build_matrices():
    """Fetch H_x and A_x from qLDPC and establish the shape facts the C side
    hard-codes as #defines.

    The degree check matters: bp_decoder.c stores the Tanner graph in fixed
    [NUM][DEGREE] arrays, which is only valid for a regular code.  The gross
    code is regular (row weight 6, column weight 3), but if someone points this
    script at an irregular code the C layout would silently overflow, so the
    assumption is verified here where it can still be reported clearly.
    """
    H = np.asarray(get_H_x()).astype(int) % 2
    A_x = np.asarray(get_A_x()).astype(int) % 2
    num_check, num_var = H.shape

    row_weights = sorted(set(int(w) for w in H.sum(axis=1)))
    col_weights = sorted(set(int(w) for w in H.sum(axis=0)))
    if len(row_weights) != 1 or len(col_weights) != 1:
        raise SystemExit(
            f"irregular code (row weights {row_weights}, column weights {col_weights}); "
            "bp_decoder.c assumes a constant degree"
        )

    return dict(H=H, A_x=A_x, num_check=num_check, num_var=num_var,
                dc=row_weights[0], dv=col_weights[0])


# ---------------------------------------------------------------------------
# Reference decoder -- produces the golden results
# ---------------------------------------------------------------------------

def memory_strength_mult(v, coeff):
    """Python twin of memory_strength_mult() in mem_strength.c.

    Duplicated here on purpose: this file must be able to produce golden
    results without the C side existing or being correct.  A reference that
    called into the thing it is checking would be worthless.
    """
    sign = -1 if v < 0 else 1
    abs_v = abs(v)
    sum_val = 0
    k = 0
    while abs_v:
        if abs_v & 1:
            sum_val += ((1 << k) * coeff) >> MEM_NUM_SHIFT
        abs_v >>= 1
        k += 1
    return sign * sum_val


def run_decoder(tab, p, seed, dmem):
    """Run the Python reference decoder on one (p, seed) case.

    The loop body is transcribed from iterations_bp.py / iterations_dmem_bp.py
    and calls the same cnu_hardware_int4 / vnu_hardware_int4 those scripts
    import, so the results it produces are the results those scripts produce.
    (Verified: case 0 reproduces both scripts' printed output exactly.)

    Returns the error pattern, the prior, and everything the C side is checked
    against -- e_hat, iteration count, and both success flags.
    """
    H = tab["H"]
    num_check, num_var = tab["num_check"], tab["num_var"]

    cn_nb = [[j for j in range(num_var) if H[i][j]] for i in range(num_check)]
    vn_nb = [[i for i in range(num_check) if H[i][j]] for j in range(num_var)]

    # np.random.seed + rand is what the Python scripts use; reproducing it here
    # is what lets the C side skip a NumPy-compatible RNG entirely.
    np.random.seed(seed)
    error = (np.random.rand(num_var) < p).astype(int)
    syndrome = (H @ error) % 2

    lambda_0_int = min(round(float(np.log((1 - p) / p)) * INT4_SCALE_FACTOR), INT4_MAX_VALUE)
    error_prior = [lambda_0_int] * num_var
    vnu_message = [[error_prior[j]] * len(vn_nb[j]) for j in range(num_var)]

    e_hat = np.zeros(num_var, dtype=int)
    converged = False
    t = 0

    for t in range(1, MAX_ITERATION + 1):
        # column-view messages regrouped into row-view CNU inputs
        cnu_inputs = [
            [vnu_message[jj][vn_nb[jj].index(ii)] for jj in cn_nb[ii]]
            for ii in range(num_check)
        ]
        cnu_results = [cnu_hardware_int4(cnu_inputs[ii], syndrome[ii], t)
                       for ii in range(num_check)]

        # row-view CNU outputs scattered back into column-view VNU inputs
        vnu_inputs = []
        for jj in range(num_var):
            msgs = []
            for cn in vn_nb[jj]:
                idx = cn_nb[cn].index(jj)
                msgs.append({
                    "min1_scaled": cnu_results[cn]["min1_scaled"],
                    "min2_scaled": cnu_results[cn]["min2_scaled"],
                    "sign": cnu_results[cn]["signs"][idx],
                    "selector": cnu_results[cn]["selectors"][idx],
                })
            vnu_inputs.append(msgs)

        vnu_results = [vnu_hardware_int4(vnu_inputs[k], error_prior[k])
                       for k in range(num_var)]

        for jj in range(num_var):
            vnu_message[jj] = vnu_results[jj]["vnu_messages"]

        e_hat = np.array([vnu_results[jj]["hard_decision"] for jj in range(num_var)])

        # syndrome consistency only -- NOT logical equivalence
        converged = np.array_equal((H @ e_hat) % 2, syndrome)
        if converged:
            break

        # the entire difference between BP and DMem-BP
        if dmem:
            for jj in range(num_var):
                error_prior[jj] = (
                    memory_strength_mult(lambda_0_int, MEM_BETA_INT)
                    + memory_strength_mult(vnu_results[jj]["marginal"], MEM_GAMMA_INT)
                )

    # logical equivalence: is the residual error e_hat ^ error a stabilizer?
    logical_action = (tab["A_x"] @ (e_hat ^ error)) % 2
    decode_success = bool(np.all(logical_action == 0)) and bool(converged)

    return dict(error=error.tolist(), lambda_int=lambda_0_int, e_hat=e_hat.tolist(),
                iterations=t, converged=int(converged), decode_success=int(decode_success))


# ---------------------------------------------------------------------------
# C emission
# ---------------------------------------------------------------------------

BANNER = ("/* Generated by export_bb_code.py -- do not edit by hand.\n"
          " * Regenerate with `make generate` (needs an interpreter with qldpc).\n"
          " */\n")


def emit_2d(name, rows, cols_macro, width=1):
    """Render a 2-D int table as a C definition.

    Rows are emitted one per line so that a diff of the generated file points at
    a specific check node / logical operator rather than at one enormous line.
    """
    body = ",\n".join(
        "    {" + ",".join(f"{v:{width}d}" for v in row) + "}" for row in rows
    )
    return f"const int {name}[{len(rows)}][{cols_macro}] = {{\n{body}\n}};\n\n"


def emit_1d(name, values, width=3, per_line=20):
    """Render a 1-D int table as a C definition, wrapped to stay readable."""
    chunks = ["    " + ",".join(f"{v:{width}d}" for v in values[i:i + per_line])
              for i in range(0, len(values), per_line)]
    return f"const int {name}[{len(values)}] = {{\n{',' .join([])}{',\n'.join(chunks)}\n}};\n\n"


def write_code_data(tab):
    """Write bb_code_data.{h,c}: the two matrices plus the shape #defines.

    Declared extern in the header and defined once in the .c, rather than as
    static tables in the header -- otherwise every translation unit that
    includes it gets its own copy of ~11k ints.
    """
    h = [BANNER, "\n#ifndef BB_CODE_DATA_H\n#define BB_CODE_DATA_H\n\n"]
    h.append("/* Gross code [[144,12,12]], X-type checks.  Generated from qLDPC;\n"
             " * see integrated_cnu_vnu/matrix_generator.py for the construction.\n"
             " *\n"
             " * Only the two matrices live here.  Everything derived from H -- the\n"
             " * Tanner graph and the per-edge slot indices -- is computed in\n"
             " * bp_decoder.c, where it is readable. */\n\n")
    h.append(f"#define NUM_CHECK_NODE     {tab['num_check']}\n")
    h.append(f"#define NUM_VARIABLE_NODE  {tab['num_var']}\n")
    h.append(f"#define CHECK_DEGREE       {tab['dc']}    /* row weight of H, verified at export */\n")
    h.append(f"#define VARIABLE_DEGREE    {tab['dv']}    /* column weight of H, likewise        */\n")
    h.append(f"#define NUM_LOGICAL        {tab['A_x'].shape[0]}    /* k, the number of logical qubits     */\n\n")
    h.append("/* H_x -- matrix_generator.py's get_H_x().  Row ii lists which qubits\n"
             " * check node ii touches; the decoder needs it for the syndrome. */\n")
    h.append("extern const int H[NUM_CHECK_NODE][NUM_VARIABLE_NODE];\n\n")
    h.append("/* A_x -- matrix_generator.py's get_A_x().  A decode is a logical success\n"
             " * when logical_A_x @ (e_hat ^ error) == 0 over GF(2).  This is the table\n"
             " * that would cost ~500 lines of GF(2) linear algebra to rebuild in C. */\n")
    h.append("extern const int logical_A_x[NUM_LOGICAL][NUM_VARIABLE_NODE];\n\n")
    h.append("#endif /* BB_CODE_DATA_H */\n")

    c = [BANNER, '\n#include "bb_code_data.h"\n\n']
    c.append(emit_2d("H", tab["H"].tolist(), "NUM_VARIABLE_NODE"))
    c.append(emit_2d("logical_A_x", tab["A_x"].tolist(), "NUM_VARIABLE_NODE"))

    open(os.path.join(HERE, "bb_code_data.h"), "w").write("".join(h))
    open(os.path.join(HERE, "bb_code_data.c"), "w").write("".join(c))


def write_test_data(tab, bp, dmem):
    """Write bp_test_data.{h,c}: error patterns and the reference results.

    This is what makes the C side testable without Python at run time, and it
    is why np_random.c no longer exists -- the error vectors NumPy would have
    generated are simply shipped as data.
    """
    n = len(TEST_CASES)
    h = [BANNER, "\n#ifndef BP_TEST_DATA_H\n#define BP_TEST_DATA_H\n\n"]
    h.append('#include "bb_code_data.h"\n\n')
    h.append("/* Decode cases with the results the Python reference produced.\n"
             " * Case 0 is (p=0.1, seed=21), the case the Python scripts run. */\n")
    h.append(f"#define NUM_TEST_CASES {n}\n\n")
    h.append("/* inputs */\n")
    h.append("extern const double test_p[NUM_TEST_CASES];\n")
    h.append("extern const int test_seed[NUM_TEST_CASES];\n")
    h.append("extern const int test_lambda_int[NUM_TEST_CASES];\n")
    h.append("extern const int test_error[NUM_TEST_CASES][NUM_VARIABLE_NODE];\n\n")
    for tag, label in (("bp", "plain BP"), ("dmem", "DMem-BP")):
        h.append(f"/* reference results, {label} */\n")
        h.append(f"extern const int golden_{tag}_iterations[NUM_TEST_CASES];\n")
        h.append(f"extern const int golden_{tag}_converged[NUM_TEST_CASES];\n")
        h.append(f"extern const int golden_{tag}_success[NUM_TEST_CASES];\n")
        h.append(f"extern const int golden_{tag}_e_hat[NUM_TEST_CASES][NUM_VARIABLE_NODE];\n\n")
    h.append("#endif /* BP_TEST_DATA_H */\n")

    c = [BANNER, '\n#include "bp_test_data.h"\n\n']
    c.append("const double test_p[NUM_TEST_CASES] = {\n    "
             + ", ".join(f"{p:g}" for p, _ in TEST_CASES) + "\n};\n\n")
    c.append(emit_1d("test_seed", [s for _, s in TEST_CASES]))
    c.append(emit_1d("test_lambda_int", [r["lambda_int"] for r in bp]))
    c.append(emit_2d("test_error", [r["error"] for r in bp], "NUM_VARIABLE_NODE"))
    for tag, res in (("bp", bp), ("dmem", dmem)):
        c.append(emit_1d(f"golden_{tag}_iterations", [r["iterations"] for r in res]))
        c.append(emit_1d(f"golden_{tag}_converged", [r["converged"] for r in res]))
        c.append(emit_1d(f"golden_{tag}_success", [r["decode_success"] for r in res]))
        c.append(emit_2d(f"golden_{tag}_e_hat", [r["e_hat"] for r in res], "NUM_VARIABLE_NODE"))

    open(os.path.join(HERE, "bp_test_data.h"), "w").write("".join(h))
    open(os.path.join(HERE, "bp_test_data.c"), "w").write("".join(c))


def main():
    """Fetch the matrices, decode every test case with the Python reference,
    and write the four generated files.  Prints a per-case summary so the
    coverage (converged / not converged / logically failed) is visible."""
    tab = build_matrices()
    print(f"gross code: {tab['num_check']} checks x {tab['num_var']} variables, "
          f"d_c={tab['dc']}, d_v={tab['dv']}, k={tab['A_x'].shape[0]}")

    bp, dmem = [], []
    for p, seed in TEST_CASES:
        b = run_decoder(tab, p, seed, dmem=False)
        d = run_decoder(tab, p, seed, dmem=True)
        bp.append(b)
        dmem.append(d)
        print(f"  p={p:<5} seed={seed:<3} "
              f"BP: t={b['iterations']:<3} conv={b['converged']} ok={b['decode_success']}   "
              f"DMem: t={d['iterations']:<3} conv={d['converged']} ok={d['decode_success']}")

    write_code_data(tab)
    write_test_data(tab, bp, dmem)
    print(f"\nwrote bb_code_data.{{h,c}} and bp_test_data.{{h,c}} into {HERE}")


if __name__ == "__main__":
    main()
