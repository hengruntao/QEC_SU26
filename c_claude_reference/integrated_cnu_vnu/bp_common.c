/* bp_common.c -- see bp_common.h */

#include <stdio.h>
#include <stdlib.h>

#include "bp_common.h"

/* NumPy's default print options (np.get_printoptions()). */
#define NP_LINEWIDTH 75
#define NP_THRESHOLD 1000
#define NP_EDGEITEMS 3

static void *xmalloc(size_t size)
{
    void *p = malloc(size ? size : 1);
    if (p == NULL) {
        fprintf(stderr, "bp_common: out of memory\n");
        exit(1);
    }
    return p;
}

void tanner_graph_build(tanner_graph *graph, const gf2_matrix *H)
{
    int i, j;

    graph->num_check_node    = H->rows;
    graph->num_variable_node = H->cols;

    graph->check_node_neighbor =
        (int (*)[MAX_CHECK_DEGREE])xmalloc(sizeof(int) * MAX_CHECK_DEGREE * (size_t)H->rows);
    graph->check_node_degree = (int *)xmalloc(sizeof(int) * (size_t)H->rows);

    graph->variable_node_neighbor =
        (int (*)[MAX_VARIABLE_DEGREE])xmalloc(sizeof(int) * MAX_VARIABLE_DEGREE * (size_t)H->cols);
    graph->variable_node_degree = (int *)xmalloc(sizeof(int) * (size_t)H->cols);

    /* ---- get check node's neighbor list
     *      (which check node is connected to which variable node) ---- */
    for (i = 0; i < H->rows; i++) {
        int degree = 0;
        for (j = 0; j < H->cols; j++) {
            if (GF2_AT(H, i, j) == 1) {
                if (degree >= MAX_CHECK_DEGREE) {
                    fprintf(stderr, "tanner_graph_build: check node %d exceeds "
                                    "MAX_CHECK_DEGREE (%d)\n", i, MAX_CHECK_DEGREE);
                    exit(1);
                }
                graph->check_node_neighbor[i][degree++] = j;
            }
        }
        graph->check_node_degree[i] = degree;
    }

    /* ---- get variable node's neighbor list
     *      (which variable node is connected to which check node) ---- */
    for (i = 0; i < H->cols; i++) {
        int degree = 0;
        for (j = 0; j < H->rows; j++) {
            if (GF2_AT(H, j, i) == 1) {
                if (degree >= MAX_VARIABLE_DEGREE) {
                    fprintf(stderr, "tanner_graph_build: variable node %d exceeds "
                                    "MAX_VARIABLE_DEGREE (%d)\n", i, MAX_VARIABLE_DEGREE);
                    exit(1);
                }
                graph->variable_node_neighbor[i][degree++] = j;
            }
        }
        graph->variable_node_degree[i] = degree;
    }
}

void tanner_graph_free(tanner_graph *graph)
{
    free(graph->check_node_neighbor);
    free(graph->check_node_degree);
    free(graph->variable_node_neighbor);
    free(graph->variable_node_degree);
    graph->check_node_neighbor    = NULL;
    graph->check_node_degree      = NULL;
    graph->variable_node_neighbor = NULL;
    graph->variable_node_degree   = NULL;
}

int neighbor_index(const int *list, int length, int value)
{
    int i;
    for (i = 0; i < length; i++) {
        if (list[i] == value) {
            return i;
        }
    }
    return -1;
}

void gf2_mat_vec_mod2(const gf2_matrix *m, const int *vec, int *out)
{
    int r, c;
    for (r = 0; r < m->rows; r++) {
        int acc = 0;
        for (c = 0; c < m->cols; c++) {
            acc ^= (int)(GF2_AT(m, r, c) & (unsigned char)(vec[c] & 1));
        }
        out[r] = acc;
    }
}

/* ---------------------------------------------------------------------------
 * NumPy array formatting
 *
 * Mirrors numpy.core.arrayprint._formatArray: `line` accumulates words plus a
 * trailing separator, a word that would push it past the width budget starts a
 * new line (dropping that trailing separator, numpy's line.rstrip()), and
 * arrays with more than `threshold` elements are summarised to the first and
 * last `edgeitems` entries along every axis.
 * ------------------------------------------------------------------------- */

typedef struct {
    int length;          /* len(line), including any pending separator */
    int pending_sep;     /* a separator is owed before the next word   */
    int hanging_indent;  /* indent for continuation lines              */
    int elem_width;      /* width budget checked against               */
} np_line;

/* numpy's _extendLine, plus the deferred separator. */
static void np_put(np_line *line, const char *word, int word_length)
{
    if (line->length + word_length > line->elem_width) {
        int i;
        putchar('\n');                      /* s += line.rstrip() + "\n"  */
        for (i = 0; i < line->hanging_indent; i++) {
            putchar(' ');
        }
        line->length      = line->hanging_indent;
        line->pending_sep = 0;              /* the rstrip drops it        */
    }
    if (line->pending_sep) {
        putchar(' ');
        line->pending_sep = 0;
    }
    fputs(word, stdout);
    line->length += word_length;
}

/* numpy's "line += separator" -- counted now, emitted only if the line lives. */
static void np_separator(np_line *line)
{
    line->length += 1;
    line->pending_sep = 1;
}

/* Width numpy pads every integer element to: the longest decimal form present. */
static int integer_element_width(const int *v, int count)
{
    int width = 1;
    int i;
    for (i = 0; i < count; i++) {
        char buf[32];
        int len = snprintf(buf, sizeof buf, "%d", v[i]);
        if (len > width) {
            width = len;
        }
    }
    return width;
}

/* Print the last (element) axis of an array: "[a b c ... x y z]".
 *
 * The opening '[' stands in for the first hanging indent, exactly as numpy's
 * "'[' + s[len(hanging_indent):] + ']'" does. */
static void print_last_axis(const int *v, int count, int elem_fmt_width,
                            int hanging_indent, int curr_width, int summarize)
{
    np_line line;
    char word[64];
    int leading  = summarize ? NP_EDGEITEMS : 0;
    int trailing = summarize ? NP_EDGEITEMS : count;
    int length;
    int i;

    line.length         = hanging_indent;
    line.pending_sep    = 0;
    line.hanging_indent = hanging_indent;
    /* elem_width = curr_width - max(len(separator.rstrip()), len(']')) */
    line.elem_width     = curr_width - 1;

    putchar('[');

    for (i = 0; i < leading; i++) {
        length = snprintf(word, sizeof word, "%*d", elem_fmt_width, v[i]);
        np_put(&line, word, length);
        np_separator(&line);
    }
    if (summarize) {
        np_put(&line, "...", 3);
        np_separator(&line);
    }
    /* all trailing elements but the very last, which carries no separator */
    for (i = trailing; i > 1; i--) {
        length = snprintf(word, sizeof word, "%*d", elem_fmt_width, v[count - i]);
        np_put(&line, word, length);
        np_separator(&line);
    }
    length = snprintf(word, sizeof word, "%*d", elem_fmt_width, v[count - 1]);
    np_put(&line, word, length);

    putchar(']');
}

void print_labeled_vector(const char *label, const int *v, int count)
{
    int summarize = (count > NP_THRESHOLD);
    fputs(label, stdout);
    print_last_axis(v, count, integer_element_width(v, count),
                    /* hanging_indent */ 1, /* curr_width */ NP_LINEWIDTH, summarize);
    putchar('\n');
}

void print_labeled_matrix(const char *label, const gf2_matrix *m)
{
    /* A 0/1 matrix, so every element formats to width 1. */
    int summarize = ((long)m->rows * (long)m->cols > NP_THRESHOLD);
    int leading   = summarize ? NP_EDGEITEMS : 0;
    int trailing  = summarize ? NP_EDGEITEMS : m->rows;
    int *row = (int *)xmalloc(sizeof(int) * (size_t)m->cols);
    int i, c;

    /* next_width = curr_width - len(']'); next_hanging_indent = indent + ' ' */
    const int next_width = NP_LINEWIDTH - 1;
    const int next_hanging_indent = 2;

    fputs(label, stdout);
    putchar('[');   /* stands in for the outer hanging indent of one space */

    for (i = 0; i < m->rows; i++) {
        int is_leading  = (i < leading);
        int is_trailing = (i >= m->rows - trailing);

        if (summarize && !is_leading && !is_trailing) {
            if (i == leading) {
                fputs("\n ...", stdout);   /* line_sep + hanging_indent + "..." */
            }
            continue;
        }

        if (i > 0) {
            fputs("\n ", stdout);          /* line_sep + hanging_indent */
        }
        for (c = 0; c < m->cols; c++) {
            row[c] = GF2_AT(m, i, c);
        }
        print_last_axis(row, m->cols, 1, next_hanging_indent, next_width, summarize);
    }

    putchar(']');
    putchar('\n');
    free(row);
}
