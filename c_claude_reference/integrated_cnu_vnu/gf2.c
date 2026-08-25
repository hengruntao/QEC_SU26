/* gf2.c -- see gf2.h */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gf2.h"

static void *xcalloc(size_t count, size_t size)
{
    void *p = calloc(count ? count : 1, size);
    if (p == NULL) {
        fprintf(stderr, "gf2: out of memory\n");
        exit(1);
    }
    return p;
}

gf2_matrix gf2_alloc(int rows, int cols)
{
    gf2_matrix m;
    m.rows = rows;
    m.cols = cols;
    m.data = (unsigned char *)xcalloc((size_t)rows * (size_t)cols, 1);
    return m;
}

gf2_matrix gf2_copy(const gf2_matrix *src)
{
    gf2_matrix m = gf2_alloc(src->rows, src->cols);
    memcpy(m.data, src->data, (size_t)src->rows * (size_t)src->cols);
    return m;
}

gf2_matrix gf2_identity(int n)
{
    gf2_matrix m = gf2_alloc(n, n);
    int i;
    for (i = 0; i < n; i++) {
        GF2_AT(&m, i, i) = 1;
    }
    return m;
}

void gf2_free(gf2_matrix *m)
{
    if (m != NULL) {
        free(m->data);
        m->data = NULL;
        m->rows = 0;
        m->cols = 0;
    }
}

/* row_dst ^= row_src, over the whole row */
static void xor_rows(gf2_matrix *m, int dst, int src)
{
    int c;
    for (c = 0; c < m->cols; c++) {
        GF2_AT(m, dst, c) ^= GF2_AT(m, src, c);
    }
}

static void swap_rows(gf2_matrix *m, int a, int b)
{
    int c;
    if (a == b) {
        return;
    }
    for (c = 0; c < m->cols; c++) {
        unsigned char tmp = GF2_AT(m, a, c);
        GF2_AT(m, a, c) = GF2_AT(m, b, c);
        GF2_AT(m, b, c) = tmp;
    }
}

int gf2_rref(gf2_matrix *m, int *pivot_cols)
{
    int rank = 0;
    int col;

    for (col = 0; col < m->cols && rank < m->rows; col++) {
        int pivot = -1;
        int r;

        for (r = rank; r < m->rows; r++) {
            if (GF2_AT(m, r, col)) {
                pivot = r;
                break;
            }
        }
        if (pivot < 0) {
            continue;   /* free column */
        }

        swap_rows(m, rank, pivot);

        /* clear this column everywhere else -- "reduced" echelon form */
        for (r = 0; r < m->rows; r++) {
            if (r != rank && GF2_AT(m, r, col)) {
                xor_rows(m, r, rank);
            }
        }

        if (pivot_cols != NULL) {
            pivot_cols[rank] = col;
        }
        rank++;
    }

    return rank;
}

gf2_matrix gf2_nullspace(const gf2_matrix *src)
{
    gf2_matrix work = gf2_copy(src);
    int *pivot_cols = (int *)xcalloc((size_t)(work.rows > 0 ? work.rows : 1), sizeof(int));
    unsigned char *is_pivot = (unsigned char *)xcalloc((size_t)work.cols, 1);
    int rank = gf2_rref(&work, pivot_cols);
    int nullity = work.cols - rank;
    gf2_matrix basis = gf2_alloc(nullity, work.cols);
    int i, free_idx = 0;

    for (i = 0; i < rank; i++) {
        is_pivot[pivot_cols[i]] = 1;
    }

    /* One kernel vector per free column: set that column to 1, then read the
     * pivot entries straight out of the RREF. */
    for (i = 0; i < work.cols; i++) {
        int r;
        if (is_pivot[i]) {
            continue;
        }
        GF2_AT(&basis, free_idx, i) = 1;
        for (r = 0; r < rank; r++) {
            GF2_AT(&basis, free_idx, pivot_cols[r]) = GF2_AT(&work, r, i);
        }
        free_idx++;
    }

    free(pivot_cols);
    free(is_pivot);
    gf2_free(&work);
    return basis;
}

gf2_matrix gf2_transpose(const gf2_matrix *m)
{
    gf2_matrix t = gf2_alloc(m->cols, m->rows);
    int r, c;
    for (r = 0; r < m->rows; r++) {
        for (c = 0; c < m->cols; c++) {
            GF2_AT(&t, c, r) = GF2_AT(m, r, c);
        }
    }
    return t;
}

gf2_matrix gf2_multiply(const gf2_matrix *a, const gf2_matrix *b)
{
    gf2_matrix p;
    int r, k, c;

    if (a->cols != b->rows) {
        fprintf(stderr, "gf2_multiply: shape mismatch (%dx%d) @ (%dx%d)\n",
                a->rows, a->cols, b->rows, b->cols);
        exit(1);
    }

    p = gf2_alloc(a->rows, b->cols);
    for (r = 0; r < a->rows; r++) {
        for (k = 0; k < a->cols; k++) {
            if (!GF2_AT(a, r, k)) {
                continue;
            }
            for (c = 0; c < b->cols; c++) {
                GF2_AT(&p, r, c) ^= GF2_AT(b, k, c);
            }
        }
    }
    return p;
}

int gf2_invert(const gf2_matrix *m, gf2_matrix *inverse)
{
    gf2_matrix aug;
    int n = m->rows;
    int r, c, rank;

    if (m->rows != m->cols) {
        return -1;
    }

    /* [ m | I ] --> RREF --> [ I | m^-1 ] when m is invertible */
    aug = gf2_alloc(n, 2 * n);
    for (r = 0; r < n; r++) {
        for (c = 0; c < n; c++) {
            GF2_AT(&aug, r, c) = GF2_AT(m, r, c);
        }
        GF2_AT(&aug, r, n + r) = 1;
    }

    rank = gf2_rref(&aug, NULL);
    if (rank != n) {
        gf2_free(&aug);
        return -1;
    }

    *inverse = gf2_alloc(n, n);
    for (r = 0; r < n; r++) {
        for (c = 0; c < n; c++) {
            GF2_AT(inverse, r, c) = GF2_AT(&aug, r, n + c);
        }
    }

    gf2_free(&aug);
    return 0;
}

gf2_matrix gf2_quotient_basis(const gf2_matrix *space, const gf2_matrix *subspace)
{
    /* Incremental echelon basis: feed in every row of `subspace` first, then
     * every row of `space`.  A row of `space` that still has a leading 1 after
     * reduction is independent of everything seen so far, so it contributes a
     * new dimension to the quotient. */
    int cols = space->cols;
    int capacity = subspace->rows + space->rows;
    gf2_matrix echelon = gf2_alloc(capacity, cols);
    int *pivot_of = (int *)xcalloc((size_t)(capacity > 0 ? capacity : 1), sizeof(int));
    int count = 0;
    gf2_matrix out = gf2_alloc(space->rows, cols);
    int out_rows = 0;
    unsigned char *v = (unsigned char *)xcalloc((size_t)cols, 1);
    int pass, i, c, j;

    if (subspace->cols != cols) {
        fprintf(stderr, "gf2_quotient_basis: column count mismatch\n");
        exit(1);
    }

    for (pass = 0; pass < 2; pass++) {
        const gf2_matrix *rows_in = (pass == 0) ? subspace : space;

        for (i = 0; i < rows_in->rows; i++) {
            int lead = -1;

            memcpy(v, &GF2_AT(rows_in, i, 0), (size_t)cols);

            /* reduce against the basis collected so far */
            for (j = 0; j < count; j++) {
                if (v[pivot_of[j]]) {
                    for (c = 0; c < cols; c++) {
                        v[c] ^= GF2_AT(&echelon, j, c);
                    }
                }
            }

            for (c = 0; c < cols; c++) {
                if (v[c]) {
                    lead = c;
                    break;
                }
            }
            if (lead < 0) {
                continue;   /* already inside the span -- adds nothing */
            }

            memcpy(&GF2_AT(&echelon, count, 0), v, (size_t)cols);
            pivot_of[count] = lead;
            count++;

            if (pass == 1) {
                /* v = original row + (some combination of subspace rows and
                 * earlier quotient reps), so it represents the same class. */
                memcpy(&GF2_AT(&out, out_rows, 0), v, (size_t)cols);
                out_rows++;
            }
        }
    }

    /* Shrink to the rows actually used. */
    {
        gf2_matrix trimmed = gf2_alloc(out_rows, cols);
        memcpy(trimmed.data, out.data, (size_t)out_rows * (size_t)cols);
        gf2_free(&out);
        out = trimmed;
    }

    gf2_free(&echelon);
    free(pivot_of);
    free(v);
    return out;
}

int gf2_is_zero(const gf2_matrix *m)
{
    size_t i, n = (size_t)m->rows * (size_t)m->cols;
    for (i = 0; i < n; i++) {
        if (m->data[i]) {
            return 0;
        }
    }
    return 1;
}

int gf2_is_identity(const gf2_matrix *m)
{
    int r, c;
    if (m->rows != m->cols) {
        return 0;
    }
    for (r = 0; r < m->rows; r++) {
        for (c = 0; c < m->cols; c++) {
            unsigned char expected = (r == c) ? 1 : 0;
            if (GF2_AT(m, r, c) != expected) {
                return 0;
            }
        }
    }
    return 1;
}
