/* test_bp.c
 *
 * Regression test: run both decoders over every case in bp_test_data.c and
 * compare against the results the Python reference produced.
 *
 * This replaces diffing printed text against the Python scripts -- it compares
 * the decoded values themselves (every bit of e_hat, the iteration count, and
 * both success flags), over many more cases than the scripts cover, and needs
 * no Python interpreter at run time.
 */

#include <stdio.h>

#include "bp_decoder.h"
#include "bp_test_data.h"

static int check_one(int c, int use_dmem,
                     const int *g_iterations, const int *g_converged,
                     const int *g_success, const int (*g_e_hat)[NUM_VARIABLE_NODE])
{
    bp_result r;
    int mismatches = 0;
    int i;

    bp_decode(test_error[c], test_lambda_int[c], use_dmem, &r);

    for (i = 0; i < NUM_VARIABLE_NODE; i++) {
        if (r.e_hat[i] != g_e_hat[c][i]) {
            mismatches++;
        }
    }
    if (mismatches || r.iterations != g_iterations[c] ||
        r.converged != g_converged[c] || r.decode_success != g_success[c]) {
        printf("  FAIL  %-5s p=%-5g seed=%-3d | t %d/%d  conv %d/%d  ok %d/%d  e_hat diff %d bits\n",
               use_dmem ? "dmem" : "bp", test_p[c], test_seed[c],
               r.iterations, g_iterations[c], r.converged, g_converged[c],
               r.decode_success, g_success[c], mismatches);
        return 1;
    }
    return 0;
}

int main(void)
{
    int failures = 0;
    int converged_cases = 0, logical_failures = 0;
    int c;

    for (c = 0; c < NUM_TEST_CASES; c++) {
        failures += check_one(c, 0, golden_bp_iterations, golden_bp_converged,
                              golden_bp_success, golden_bp_e_hat);
        failures += check_one(c, 1, golden_dmem_iterations, golden_dmem_converged,
                              golden_dmem_success, golden_dmem_e_hat);

        converged_cases += golden_bp_converged[c] + golden_dmem_converged[c];
        /* converged but logically wrong -- the only runs whose verdict depends
         * on the logical operator basis */
        logical_failures += (golden_bp_converged[c] && !golden_bp_success[c]);
        logical_failures += (golden_dmem_converged[c] && !golden_dmem_success[c]);
    }

    printf("%d cases x 2 decoders = %d runs vs the Python reference\n",
           NUM_TEST_CASES, NUM_TEST_CASES * 2);
    printf("  coverage: %d converged, %d not converged, %d converged-but-logical-failure\n",
           converged_cases, NUM_TEST_CASES * 2 - converged_cases, logical_failures);
    printf("%s\n", failures ? "FAILED" : "all runs match");

    return failures != 0;
}
