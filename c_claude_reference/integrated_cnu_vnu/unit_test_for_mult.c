/* unit_test_for_mult.c
 *
 * Intro:
 * This is the unit test for function memory_strength_mult()
 * This function is used in DMem-BP to implement the optimized multiplication
 * described in the FPGA paper.
 *
 * C port of integrated_cnu_vnu/unit_test_for_mult.py.
 */

#include <stdio.h>

#include "mem_strength.h"

static void check(int actual, int expected_numerator)
{
    /* the Python test compares against e.g. 88/8, i.e. the exact quotient */
    printf("%s\n", (actual * MEM_STRENGTH_SCALE_FACTOR == expected_numerator) ? "True" : "False");
}

int main(void)
{
    int v;
    int is_same = 1;

    /* ---- unit test: FPGA paper Appendix C, Table 2 (M=8, coeff=7) ---- */
    check(memory_strength_mult(15, 7), 88);   /* 88 / 8 */
    check(memory_strength_mult(8,  7), 56);   /* 56 / 8 */
    check(memory_strength_mult(4,  7), 24);   /* 24 / 8 */
    check(memory_strength_mult(2,  7), 8);    /*  8 / 8 */
    check(memory_strength_mult(1,  7), 0);    /*  0 / 8 */

    /* ---- gamma=0: DMem-BP degenerates to BP (coeff=M) ----
     * Lambda_j(t) = Lambda_j(0), without any difference!!! */
    for (v = -15; v <= 15; v++) {   /* v is Lambda_j(0), in [-15,15] for int4 precision */
        if (memory_strength_mult(v, MEM_STRENGTH_SCALE_FACTOR) != v) {
            is_same = 0;
        }
    }
    printf("Memory strength scaling does NOT affect pure BP: %s\n", is_same ? "True" : "False");

    return 0;
}
