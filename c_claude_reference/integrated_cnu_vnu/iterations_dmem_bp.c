/* iterations_dmem_bp.c
 *
 * C port of integrated_cnu_vnu/iterations_dmem_bp.py -- min-sum BP with
 * disordered memory (DMem-BP) over the gross code [[144,12,12]].
 *
 * Identical to iterations_bp.c except for the use_dmem flag, which enables the
 * error-prior update at the bottom of each iteration:
 *     Lambda_j(t) = (1-gamma)*Lambda_j(0) + gamma*M_j(t-1)
 * carried out with the shift-and-add multiplier in mem_strength.c.
 */

#include <stdio.h>

#include "bp_decoder.h"
#include "bp_test_data.h"

#define CASE 0

int main(void)
{
    bp_result r;
    int error_sum = 0, e_hat_sum = 0, syndrome_sum = 0;
    int i;

    bp_decode(test_error[CASE], test_lambda_int[CASE], /* use_dmem */ 1, &r);

    for (i = 0; i < NUM_VARIABLE_NODE; i++) {
        error_sum += test_error[CASE][i];
        e_hat_sum += r.e_hat[i];
    }
    for (i = 0; i < NUM_CHECK_NODE; i++) {
        syndrome_sum += r.syndrome[i];
    }

    printf("check matrix:                           H_x, %d x %d (d_c=%d, d_v=%d)\n",
           NUM_CHECK_NODE, NUM_VARIABLE_NODE, CHECK_DEGREE, VARIABLE_DEGREE);
    printf("physical error rate:                    %g\n", test_p[CASE]);
    printf("random seed:                            %d\n", test_seed[CASE]);
    bp_print_vector("actual_error:                           ",
                    test_error[CASE], NUM_VARIABLE_NODE);
    printf("actual_error_sum:                       %d\n", error_sum);
    bp_print_vector("e_hat (estimated_error):                ",
                    r.e_hat, NUM_VARIABLE_NODE);
    printf("e_hat_sum:                              %d\n", e_hat_sum);
    bp_print_vector("H*e_hat mod 2:                          ",
                    r.syndrome_check, NUM_CHECK_NODE);
    bp_print_vector("syndrome:                               ",
                    r.syndrome, NUM_CHECK_NODE);
    printf("syndrome_sum:                           %d\n", syndrome_sum);
    printf("t (# of iterations):                    %d\n", r.iterations);
    printf("decode successful (logic consistent):   %s\n", r.decode_success ? "True" : "False");
    printf("converged (syndrome consistent):        %s\n", r.converged ? "True" : "False");

    return 0;
}
