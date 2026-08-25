/* iterations_dmem_bp.c
 *
 * C port of integrated_cnu_vnu/iterations_dmem_bp.py -- min-sum BP with
 * disordered memory (DMem-BP) over the gross code [[144,12,12]].
 *
 * Identical to iterations_bp.c except for the error-prior update at the bottom
 * of each iteration:
 *     Lambda_j(t) = (1-gamma)*Lambda_j(0) + gamma*M_j(t-1)
 * carried out with the shift-and-add multiplier in mem_strength.c.
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "bp_common.h"
#include "matrix_generator.h"
#include "mem_strength.h"
#include "np_random.h"

#include "cnu_int4.h"
#include "vnu_int4.h"

#define MAX_ITERATION       60
#define RANDOM_SEED         21
#define INT4_SCALE_FACTOR   2    /* the 2 in Int4.2.8 */

/* p is physical error rate */
static const double p = 0.1;

static int error[BB_NUM_VARIABLE_NODE];
static int syndrome[BB_NUM_CHECK_NODE];
static int syndrome_check[BB_NUM_CHECK_NODE];
static int e_hat[BB_NUM_VARIABLE_NODE];
static int new_e[BB_NUM_VARIABLE_NODE];
static int logical_action[BB_K];

/* Lambda_j(t), updated every iteration; initialized to Lambda_j(0) */
static int error_prior[BB_NUM_VARIABLE_NODE];

static int vnu_message[BB_NUM_VARIABLE_NODE][MAX_VARIABLE_DEGREE];

static int           cnu_inputs[BB_NUM_CHECK_NODE][MAX_CHECK_DEGREE];
static cnu_result_t  cnu_results[BB_NUM_CHECK_NODE];
static cnu_message_t vnu_inputs[BB_NUM_VARIABLE_NODE][MAX_VARIABLE_DEGREE];
static vnu_result_t  vnu_results[BB_NUM_VARIABLE_NODE];

int main(void)
{
    /* ---- define check matrix ----
     * see matrix_generator.h for get_H_x() & get_H_z() */
    const gf2_matrix *H = get_H_x();
    const gf2_matrix *A_x;
    tanner_graph graph;

    int num_check_node, num_variable_node;
    double uniform[BB_NUM_VARIABLE_NODE];
    np_random_state rng;
    double lambda_0_float;
    int lambda_0_int;
    int t, t_final = 0;
    int converged = 0, logical_success = 0, decode_success;
    int error_sum = 0, e_hat_sum = 0, syndrome_sum = 0;
    int i, ii, jj, kk, d;

    tanner_graph_build(&graph, H);
    num_check_node    = graph.num_check_node;
    num_variable_node = graph.num_variable_node;

    /* ---- initializing vnu_message for first iteration ----
     * use seed here for replication purpose */
    np_random_seed(&rng, RANDOM_SEED);
    np_random_rand(&rng, uniform, num_variable_node);

    for (jj = 0; jj < num_variable_node; jj++) {
        error[jj] = (uniform[jj] < p) ? 1 : 0;
    }

    gf2_mat_vec_mod2(H, error, syndrome);

    /* initial vnu_message = lambda_0
     * Int4.2.8 => max_value = 15; scaling factor = 2 */
    lambda_0_float = log((1.0 - p) / p);
    lambda_0_int = (int)nearbyint(lambda_0_float * INT4_SCALE_FACTOR);   /* Lambda_j(0) */
    if (lambda_0_int > INT4_MAX_VALUE) {
        lambda_0_int = INT4_MAX_VALUE;
    }
    for (jj = 0; jj < num_variable_node; jj++) {
        error_prior[jj] = lambda_0_int;
    }

    for (jj = 0; jj < num_variable_node; jj++) {
        for (d = 0; d < graph.variable_node_degree[jj]; d++) {
            vnu_message[jj][d] = error_prior[jj];
        }
    }

    /* iteration begins */
    for (t = 1; t <= MAX_ITERATION; t++) {

        /* 1. ---- input for CNU ---- (column messages -> row messages) */
        for (ii = 0; ii < num_check_node; ii++) {
            for (d = 0; d < graph.check_node_degree[ii]; d++) {
                int vn = graph.check_node_neighbor[ii][d];
                int index = neighbor_index(graph.variable_node_neighbor[vn],
                                           graph.variable_node_degree[vn], ii);
                cnu_inputs[ii][d] = vnu_message[vn][index];
            }
        }

        /* 2. ---- CNU processing ---- */
        for (ii = 0; ii < num_check_node; ii++) {
            if (cnu_hardware_int4(cnu_inputs[ii], graph.check_node_degree[ii],
                                  syndrome[ii], t, &cnu_results[ii]) != 0) {
                fprintf(stderr, "cnu_hardware_int4 failed at check node %d\n", ii);
                return 1;
            }
        }

        /* ---- CNU output to VNU input ---- */
        for (jj = 0; jj < num_variable_node; jj++) {
            for (d = 0; d < graph.variable_node_degree[jj]; d++) {
                int cn = graph.variable_node_neighbor[jj][d];
                int vn_idx = neighbor_index(graph.check_node_neighbor[cn],
                                            graph.check_node_degree[cn], jj);
                vnu_inputs[jj][d].min1_scaled = cnu_results[cn].min1_scaled;
                vnu_inputs[jj][d].min2_scaled = cnu_results[cn].min2_scaled;
                vnu_inputs[jj][d].sign        = cnu_results[cn].signs[vn_idx];
                vnu_inputs[jj][d].selector    = cnu_results[cn].selectors[vn_idx];
            }
        }

        /* ---- VNU phase ---- */
        for (kk = 0; kk < num_variable_node; kk++) {
            if (vnu_hardware_int4(vnu_inputs[kk], graph.variable_node_degree[kk],
                                  error_prior[kk], &vnu_results[kk]) != 0) {
                fprintf(stderr, "vnu_hardware_int4 failed at variable node %d\n", kk);
                return 1;
            }
        }

        /* ---- update vnu_message ---- */
        for (jj = 0; jj < num_variable_node; jj++) {
            for (d = 0; d < graph.variable_node_degree[jj]; d++) {
                vnu_message[jj][d] = vnu_results[jj].vnu_messages[d];
            }
        }

        /* ---- Convergence check ---- */
        for (jj = 0; jj < num_variable_node; jj++) {
            e_hat[jj] = vnu_results[jj].hard_decision;
        }

        gf2_mat_vec_mod2(H, e_hat, syndrome_check);
        converged = 1;
        for (ii = 0; ii < num_check_node; ii++) {
            if (syndrome_check[ii] != syndrome[ii]) {
                converged = 0;
                break;
            }
        }

        t_final = t;
        if (converged) {
            break;
        }

        /* ---- For DMem-BP: error_prior update
         *      Lambda_j(t) = (1-gamma)*Lambda_j(0) + gamma*M_j(t-1) ---- */
        for (jj = 0; jj < num_variable_node; jj++) {
            error_prior[jj] =
                memory_strength_mult(lambda_0_int, MEM_STRENGTH_BETA_INT) +
                memory_strength_mult(vnu_results[jj].marginal, MEM_STRENGTH_GAMMA_INT);
        }
    }

    /* iteration ends, now check for logical equivalence (A*e_hat = A*e) */
    A_x = get_A_x();
    for (jj = 0; jj < num_variable_node; jj++) {
        new_e[jj] = e_hat[jj] ^ error[jj];
    }
    gf2_mat_vec_mod2(A_x, new_e, logical_action);
    logical_success = 1;
    for (i = 0; i < A_x->rows; i++) {
        if (logical_action[i] != 0) {
            logical_success = 0;
            break;
        }
    }

    decode_success = (logical_success && converged);

    for (jj = 0; jj < num_variable_node; jj++) {
        error_sum += error[jj];
        e_hat_sum += e_hat[jj];
    }
    for (ii = 0; ii < num_check_node; ii++) {
        syndrome_sum += syndrome[ii];
    }

    print_labeled_matrix("check matrix:                           ", H);
    printf("physical error rate:                    %g\n", p);
    print_labeled_vector("actual_error:                           ", error, num_variable_node);
    printf("actual_error_sum:                       %d\n", error_sum);
    print_labeled_vector("e_hat (estimated_error):                ", e_hat, num_variable_node);
    printf("e_hat_sum:                              %d\n", e_hat_sum);
    print_labeled_vector("H·ê mod 2:                              ", syndrome_check, num_check_node);
    print_labeled_vector("syndrome:                               ", syndrome, num_check_node);
    printf("syndrome_sum:                           %d\n", syndrome_sum);
    printf("t (# of iterations):                    %d\n", t_final);
    printf("decode successful (logic consistent):   %s\n", decode_success ? "True" : "False");
    printf("converged (syndrome consistent):        %s\n", converged ? "True" : "False");

    tanner_graph_free(&graph);
    matrix_generator_free();
    return 0;
}
