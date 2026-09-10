/* bp_decoder.c -- see bp_decoder.h
 *
 * C port of the iteration loop in integrated_cnu_vnu/iterations_bp.py and
 * iterations_dmem_bp.py.
 */

#include <stdio.h>

#include "bp_decoder.h"
#include "mem_strength.h"

#include "cnu_int4.h"
#include "vnu_int4.h"
#include "lfsr_rng.h"

/* The generated degrees must fit the CNU/VNU fixed-size result arrays.
 * A negative array size here is a compile error, so this is checked at build
 * time rather than trusted. */
typedef char bp_decoder_degrees_fit[
    (CHECK_DEGREE <= CNU_MAX_DEGREE && VARIABLE_DEGREE <= VNU_MAX_DEGREE) ? 1 : -1];

/* Working state.  File-scope so the frame stays small and the layout mirrors
 * the fixed buffers a hardware implementation would have. */
static int           vnu_message[NUM_VARIABLE_NODE][VARIABLE_DEGREE];
static int           error_prior[NUM_VARIABLE_NODE];
static int           cnu_inputs[NUM_CHECK_NODE][CHECK_DEGREE];
static cnu_result_t  cnu_results[NUM_CHECK_NODE];
static cnu_message_t vnu_inputs[NUM_VARIABLE_NODE][VARIABLE_DEGREE];
static vnu_result_t  vnu_results[NUM_VARIABLE_NODE];
static lfsr_rng_state_t rng_state[NUM_VARIABLE_NODE];

void bp_syndrome(const int *vec, int *out)
{
    int ii, d;
    for (ii = 0; ii < NUM_CHECK_NODE; ii++) {
        int acc = 0;
        for (d = 0; d < CHECK_DEGREE; d++) {
            acc ^= (vec[check_node_neighbor[ii][d]] & 1);
        }
        out[ii] = acc;
    }
}

void bp_logical_action(const int *vec, int *out)
{
    int r, c;
    for (r = 0; r < NUM_LOGICAL; r++) {
        int acc = 0;
        for (c = 0; c < NUM_VARIABLE_NODE; c++) {
            acc ^= (logical_A_x[r][c] & vec[c] & 1);
        }
        out[r] = acc;
    }
}

void bp_decode(const int *error, int lambda_int, int use_dmem, bp_result *result)
{
    int logical_action[NUM_LOGICAL];
    int t, ii, jj, kk, d;

    bp_syndrome(error, result->syndrome);

    /* ---- initializing vnu_message for first iteration ----
     * initial vnu_message = lambda_0 */
    for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
        error_prior[jj] = lambda_int;
        lfsr_rng_reset(&rng_state[jj], (uint8_t)(jj + 1));
        for (d = 0; d < VARIABLE_DEGREE; d++) {
            vnu_message[jj][d] = lambda_int;
        }
    }

    result->converged  = 0;
    result->iterations = 0;

    /* iteration begins */
    for (t = 1; t <= BP_MAX_ITERATION; t++) {

        /* 1. ---- input for CNU ----
         * vnu_message gives the message of a "column" but the CNU needs a
         * "row".  check_node_neighbor says which VNU sits on each edge, and
         * cnu_src_slot says which of that VNU's outputs carries this edge --
         * both precomputed by export_bb_code.py, so this is a pure gather. */
        for (ii = 0; ii < NUM_CHECK_NODE; ii++) {
            for (d = 0; d < CHECK_DEGREE; d++) {
                cnu_inputs[ii][d] =
                    vnu_message[check_node_neighbor[ii][d]][cnu_src_slot[ii][d]];
            }
        }

        /* 2. ---- CNU processing ---- */
        for (ii = 0; ii < NUM_CHECK_NODE; ii++) {
            cnu_hardware_int4(cnu_inputs[ii], CHECK_DEGREE,
                              result->syndrome[ii], t, &cnu_results[ii]);
        }

        /* 3. ---- CNU output to VNU input ----
         * The scatter back to "column" order.  min1/min2 are broadcast to
         * every edge of the check node; sign/selector are per-edge, picked
         * out with vnu_src_slot. */
        for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
            for (d = 0; d < VARIABLE_DEGREE; d++) {
                int cn = variable_node_neighbor[jj][d];
                int s  = vnu_src_slot[jj][d];
                vnu_inputs[jj][d].min1_scaled = cnu_results[cn].min1_scaled;
                vnu_inputs[jj][d].min2_scaled = cnu_results[cn].min2_scaled;
                vnu_inputs[jj][d].sign        = cnu_results[cn].signs[s];
                vnu_inputs[jj][d].selector    = cnu_results[cn].selectors[s];
            }
        }

        /* 4. ---- VNU phase ---- */
        for (kk = 0; kk < NUM_VARIABLE_NODE; kk++) {
            vnu_hardware_int4(vnu_inputs[kk], VARIABLE_DEGREE,
                              error_prior[kk], &vnu_results[kk]);
        }

        /* 5. ---- update vnu_message, collect hard decisions ---- */
        for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
            for (d = 0; d < VARIABLE_DEGREE; d++) {
                vnu_message[jj][d] = vnu_results[jj].vnu_messages[d];
            }
            result->e_hat[jj] = vnu_results[jj].hard_decision;
        }

        /* 6. ---- Convergence check: H*e_hat mod 2 == sigma ----
         * IMPORTANT: this ONLY means syndrome consistency,
         * NOT logical equivalence (A*e_hat = A*e). */
        bp_syndrome(result->e_hat, result->syndrome_check);
        result->converged = 1;
        for (ii = 0; ii < NUM_CHECK_NODE; ii++) {
            if (result->syndrome_check[ii] != result->syndrome[ii]) {
                result->converged = 0;
                break;
            }
        }

        result->iterations = t;
        if (result->converged) {
            break;
        }

        /* 7. ---- DMem-BP only: error_prior update ----
         * Lambda_j(t) = (1-gamma)*Lambda_j(0) + gamma*M_j(t-1)
         * This block is the entire difference from plain BP. */
        if (use_dmem) {
            for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
                int beta_int = (int)rng_state[jj].beta_int;
                int gamma_int = (int)lfsr_rng_gamma_int(&rng_state[jj]);

                error_prior[jj] =
                    memory_strength_mult(lambda_int, beta_int) +
                    memory_strength_mult(vnu_results[jj].marginal, gamma_int);
                }
        }
    }

    /* iteration ends, now check for logical equivalence (A*e_hat = A*e) */
    {
        int new_e[NUM_VARIABLE_NODE];
        for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
            new_e[jj] = result->e_hat[jj] ^ error[jj];
        }
        bp_logical_action(new_e, logical_action);
    }

    result->logical_success = 1;
    for (ii = 0; ii < NUM_LOGICAL; ii++) {
        if (logical_action[ii] != 0) {
            result->logical_success = 0;
            break;
        }
    }

    result->decode_success = (result->logical_success && result->converged);
}

void bp_print_vector(const char *label, const int *v, int count)
{
    const int per_line = 36;
    int i;

    printf("%s[", label);
    for (i = 0; i < count; i++) {
        if (i > 0) {
            printf((i % per_line == 0) ? "\n " : " ");
        }
        printf("%d", v[i]);
    }
    printf("]\n");
}

/* for (jj = 0; jj < NUM_VARIABLE_NODE; jj++) {
    lfsr_rng_step(&rng_state[jj], 1U, 1U);

WRITE in OUTERLEG for rng
    */