/* bp_common.h
 *
 * Pieces shared by iterations_bp.c and iterations_dmem_bp.c.  The Python
 * versions of those two scripts repeat this setup verbatim; here it is
 * factored out so the two C programs differ only in the BP maths itself.
 *
 * The printing helpers reproduce NumPy's array formatting (linewidth 75,
 * threshold 1000, edgeitems 3) so the C output can be diffed byte-for-byte
 * against the Python reference.
 */

#ifndef BP_COMMON_H
#define BP_COMMON_H

#include "gf2.h"

/* Upper bounds on the Tanner graph degrees.  The gross code [[144,12,12]] has
 * row weight 6 and column weight 6; 16 leaves room for other codes. */
#define MAX_CHECK_DEGREE    16
#define MAX_VARIABLE_DEGREE 16

typedef struct {
    int num_check_node;
    int num_variable_node;

    /* check_node_neighbor[i] -- which variable nodes check node i touches */
    int (*check_node_neighbor)[MAX_CHECK_DEGREE];
    int *check_node_degree;

    /* variable_node_neighbor[j] -- which check nodes variable node j touches */
    int (*variable_node_neighbor)[MAX_VARIABLE_DEGREE];
    int *variable_node_degree;
} tanner_graph;

/* Build both neighbour lists from H.  Exits with a message if any degree
 * exceeds the limits above. */
void tanner_graph_build(tanner_graph *graph, const gf2_matrix *H);
void tanner_graph_free(tanner_graph *graph);

/* Position of `value` in `list`, i.e. Python's list.index().  Returns -1 if
 * absent, which cannot happen for a consistent Tanner graph. */
int neighbor_index(const int *list, int length, int value);

/* out = (m @ vec) % 2.  `vec` has m->cols entries, `out` has m->rows. */
void gf2_mat_vec_mod2(const gf2_matrix *m, const int *vec, int *out);

/* ---- NumPy-compatible printing ---- */

/* print("<label><numpy repr of the vector>") */
void print_labeled_vector(const char *label, const int *v, int count);

/* print("<label><numpy repr of the 0/1 matrix>") */
void print_labeled_matrix(const char *label, const gf2_matrix *m);

#endif /* BP_COMMON_H */
