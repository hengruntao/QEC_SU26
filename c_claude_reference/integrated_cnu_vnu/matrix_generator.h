/* matrix_generator.h
 *
 * ---- intro ----
 * this file generates check matrix (H) and logical action matrix (A)
 * NOTICE: parameters are hardcoded for gross code [[144,12,12]]
 * See math in paper arXiv:2308.07915v2
 *
 * C port of integrated_cnu_vnu/matrix_generator.py.  The Python version calls
 * the qLDPC package (codes.BBCode); C has no such dependency, so the matrices
 * are built here directly:
 *
 *   x = S_l (x) I_m,  y = I_l (x) S_m       S_n = cyclic shift, S[i,(i+1)%n]=1
 *   A = x^3 + y + y^2                       (poly_a)
 *   B = y^3 + x + x^2                       (poly_b)
 *   H_x = [A | B]        H_z = [B^T | A^T]
 *
 * H_x and H_z come out bit-for-bit identical to qLDPC's code.matrix_x and
 * code.matrix_z (verified against the Python module).
 *
 * A_x and A_z are NOT bit-for-bit identical to qLDPC's get_logical_ops(): a
 * logical operator is only defined up to multiplication by a stabilizer, so
 * every valid basis is a different but equally correct representative set.
 * What matters for decoding is that the basis is valid, which is pinned down
 * by three conditions this module asserts at startup:
 *
 *     H_z @ A_x^T = 0      (X logicals commute with the Z stabilizers)
 *     H_x @ A_z^T = 0      (Z logicals commute with the X stabilizers)
 *     A_x @ A_z^T = I_k    (symplectic pairing, so both have full rank k)
 *
 * Given those, for any e in ker(H_x) -- which is exactly the case the decoder
 * tests, since H(e_hat + e) = 0 once it has converged -- A_x @ e = 0 holds for
 * this basis if and only if it holds for qLDPC's.  So `decode_success` is
 * identical either way.
 */

#ifndef MATRIX_GENERATOR_H
#define MATRIX_GENERATOR_H

#include "gf2.h"

/* Here we use gross code [[144,12,12]] ([[n,k,d]])
 * l = 12, m = 6 */
#define BB_L 12
#define BB_M 6
#define BB_NUM_CHECK_NODE     (BB_L * BB_M)         /*  72 rows of H    */
#define BB_NUM_VARIABLE_NODE  (2 * BB_L * BB_M)     /* 144 columns of H */
#define BB_K                  12                    /* logical qubits   */

/* Z-type physical error <-> H_x <-> A_x (X-type logical operator)
 *
 * ---- get check matrix H ----
 *     H_x for Z-type error
 *     H_z for X-type error
 *
 * The returned matrices are owned by this module; do not free them. */
const gf2_matrix *get_H_x(void);
const gf2_matrix *get_H_z(void);

/* ---- get logical matrix A ----
 *     A for X_type logical operator
 *     A for Z_type logical operator */
const gf2_matrix *get_A_x(void);
const gf2_matrix *get_A_z(void);

/* Optional teardown, for a clean exit under a leak checker. */
void matrix_generator_free(void);

#endif /* MATRIX_GENERATOR_H */
