/* gf2.h
 *
 * Minimal dense linear algebra over GF(2) (the field {0,1} with XOR as "+").
 *
 * The Python side gets its matrices from the qLDPC package; the C side has no
 * such dependency, so matrix_generator.c builds the gross-code check matrices
 * from first principles and derives the logical operators with the routines
 * below.  See matrix_generator.h for why that yields the same decoding verdict
 * as qLDPC's basis even though the individual basis vectors differ.
 *
 * Entries are stored one byte per bit (row-major).  The matrices here are at
 * most 144x288, so clarity beats bit-packing.
 */

#ifndef GF2_H
#define GF2_H

typedef struct {
    int rows;
    int cols;
    unsigned char *data;   /* row-major, every entry is 0 or 1 */
} gf2_matrix;

/* All allocating routines abort the process on out-of-memory. */
gf2_matrix gf2_alloc(int rows, int cols);           /* zero filled          */
gf2_matrix gf2_copy(const gf2_matrix *m);
gf2_matrix gf2_identity(int n);
void       gf2_free(gf2_matrix *m);

/* Element access.  No bounds checking -- callers stay inside the shape. */
#define GF2_AT(m, r, c) ((m)->data[(size_t)(r) * (size_t)((m)->cols) + (size_t)(c)])

/* Reduced row echelon form, in place.
 * pivot_cols (may be NULL) receives the pivot column of each of the first
 * `rank` rows.  Returns the rank. */
int gf2_rref(gf2_matrix *m, int *pivot_cols);

/* Basis of {v : m @ v = 0}, returned as the ROWS of the result. */
gf2_matrix gf2_nullspace(const gf2_matrix *m);

gf2_matrix gf2_transpose(const gf2_matrix *m);
gf2_matrix gf2_multiply(const gf2_matrix *a, const gf2_matrix *b);

/* Inverse of a square matrix.  Returns 0 on success, -1 if singular. */
int gf2_invert(const gf2_matrix *m, gf2_matrix *inverse);

/* Rows of `space` that are linearly independent modulo the row space of
 * `subspace`, each already reduced against `subspace`.  This is a basis of the
 * quotient space  rowspace(space) / rowspace(subspace). */
gf2_matrix gf2_quotient_basis(const gf2_matrix *space, const gf2_matrix *subspace);

int gf2_is_zero(const gf2_matrix *m);
int gf2_is_identity(const gf2_matrix *m);

#endif /* GF2_H */
