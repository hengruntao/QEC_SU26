/* matrix_generator.c -- see matrix_generator.h */

#include <stdio.h>
#include <stdlib.h>

#include "matrix_generator.h"

/* poly_a = x**3 + y + y**2 ;  poly_b = y**3 + x + x**2
 * each term is a monomial x^a * y^b, listed as {a, b}. */
static const int POLY_A_TERMS[3][2] = { {3, 0}, {0, 1}, {0, 2} };
static const int POLY_B_TERMS[3][2] = { {0, 3}, {1, 0}, {2, 0} };

static int initialized = 0;
static gf2_matrix H_x, H_z, A_x, A_z;

/* Add the monomial x^a * y^b  =  S_l^a (x) S_m^b  into `m` (72x72).
 * Row index is i*BB_M + j with i in [0,l), j in [0,m); the monomial maps that
 * row to column ((i+a) mod l)*BB_M + ((j+b) mod m). */
static void add_monomial(gf2_matrix *m, int a, int b)
{
    int i, j;
    for (i = 0; i < BB_L; i++) {
        for (j = 0; j < BB_M; j++) {
            int row = i * BB_M + j;
            int col = ((i + a) % BB_L) * BB_M + ((j + b) % BB_M);
            GF2_AT(m, row, col) ^= 1;
        }
    }
}

static gf2_matrix build_polynomial(const int terms[][2], int num_terms)
{
    gf2_matrix m = gf2_alloc(BB_NUM_CHECK_NODE, BB_NUM_CHECK_NODE);
    int k;
    for (k = 0; k < num_terms; k++) {
        add_monomial(&m, terms[k][0], terms[k][1]);
    }
    return m;
}

/* dst[:, offset : offset + src->cols] = src */
static void paste_block(gf2_matrix *dst, const gf2_matrix *src, int col_offset)
{
    int r, c;
    for (r = 0; r < src->rows; r++) {
        for (c = 0; c < src->cols; c++) {
            GF2_AT(dst, r, col_offset + c) = GF2_AT(src, r, c);
        }
    }
}

static void fail(const char *what)
{
    fprintf(stderr, "matrix_generator: self-check failed (%s)\n", what);
    exit(1);
}

/* Verify the three conditions documented in matrix_generator.h. */
static void self_check(void)
{
    gf2_matrix A_xT = gf2_transpose(&A_x);
    gf2_matrix A_zT = gf2_transpose(&A_z);
    gf2_matrix H_zT = gf2_transpose(&H_z);

    gf2_matrix commute_x = gf2_multiply(&H_z, &A_xT);   /* H_z @ A_x^T */
    gf2_matrix commute_z = gf2_multiply(&H_x, &A_zT);   /* H_x @ A_z^T */
    gf2_matrix css       = gf2_multiply(&H_x, &H_zT);   /* H_x @ H_z^T */
    gf2_matrix pairing   = gf2_multiply(&A_x, &A_zT);   /* A_x @ A_z^T */

    if (!gf2_is_zero(&css))        fail("H_x @ H_z^T != 0");
    if (!gf2_is_zero(&commute_x))  fail("H_z @ A_x^T != 0");
    if (!gf2_is_zero(&commute_z))  fail("H_x @ A_z^T != 0");
    if (!gf2_is_identity(&pairing)) fail("A_x @ A_z^T != I");
    if (A_x.rows != BB_K || A_z.rows != BB_K) fail("wrong number of logical operators");

    gf2_free(&A_xT);
    gf2_free(&A_zT);
    gf2_free(&H_zT);
    gf2_free(&commute_x);
    gf2_free(&commute_z);
    gf2_free(&css);
    gf2_free(&pairing);
}

static void init(void)
{
    gf2_matrix A, B, A_T, B_T;
    gf2_matrix ker_H_z, ker_H_x;
    gf2_matrix A_x_raw, pairing, pairing_inv;

    if (initialized) {
        return;
    }

    /* ---- H_x = [A | B],  H_z = [B^T | A^T] ---- */
    A = build_polynomial(POLY_A_TERMS, 3);
    B = build_polynomial(POLY_B_TERMS, 3);
    A_T = gf2_transpose(&A);
    B_T = gf2_transpose(&B);

    H_x = gf2_alloc(BB_NUM_CHECK_NODE, BB_NUM_VARIABLE_NODE);
    paste_block(&H_x, &A, 0);
    paste_block(&H_x, &B, BB_NUM_CHECK_NODE);

    H_z = gf2_alloc(BB_NUM_CHECK_NODE, BB_NUM_VARIABLE_NODE);
    paste_block(&H_z, &B_T, 0);
    paste_block(&H_z, &A_T, BB_NUM_CHECK_NODE);

    gf2_free(&A);
    gf2_free(&B);
    gf2_free(&A_T);
    gf2_free(&B_T);

    /* ---- logical operators ----
     * X logicals: commute with every Z stabilizer, i.e. live in ker(H_z);
     * they are trivial exactly when they are already an X stabilizer, i.e.
     * already in the row space of H_x.  So the logical X space is the quotient
     *     ker(H_z) / rowspace(H_x)
     * and symmetrically for Z. */
    ker_H_z = gf2_nullspace(&H_z);
    ker_H_x = gf2_nullspace(&H_x);

    A_x_raw = gf2_quotient_basis(&ker_H_z, &H_x);
    A_z     = gf2_quotient_basis(&ker_H_x, &H_z);

    gf2_free(&ker_H_z);
    gf2_free(&ker_H_x);

    if (A_x_raw.rows != BB_K || A_z.rows != BB_K) {
        fail("quotient basis has the wrong dimension");
    }

    /* ---- symplectic normalisation ----
     * The two bases above are independent of each other, so their pairing
     * Omega = A_x_raw @ A_z^T is some invertible k x k matrix rather than I.
     * Rewriting A_x <- Omega^-1 @ A_x_raw fixes that: row operations keep every
     * row inside ker(H_z), and afterwards A_x @ A_z^T = I, matching the
     * convention qLDPC's get_logical_ops() returns. */
    {
        gf2_matrix A_zT = gf2_transpose(&A_z);
        pairing = gf2_multiply(&A_x_raw, &A_zT);
        gf2_free(&A_zT);
    }
    if (gf2_invert(&pairing, &pairing_inv) != 0) {
        fail("symplectic pairing is singular");
    }
    A_x = gf2_multiply(&pairing_inv, &A_x_raw);

    gf2_free(&pairing);
    gf2_free(&pairing_inv);
    gf2_free(&A_x_raw);

    self_check();
    initialized = 1;
}

const gf2_matrix *get_H_x(void) { init(); return &H_x; }
const gf2_matrix *get_H_z(void) { init(); return &H_z; }
const gf2_matrix *get_A_x(void) { init(); return &A_x; }
const gf2_matrix *get_A_z(void) { init(); return &A_z; }

void matrix_generator_free(void)
{
    if (!initialized) {
        return;
    }
    gf2_free(&H_x);
    gf2_free(&H_z);
    gf2_free(&A_x);
    gf2_free(&A_z);
    initialized = 0;
}
