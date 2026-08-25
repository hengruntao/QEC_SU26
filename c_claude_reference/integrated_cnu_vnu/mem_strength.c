/* mem_strength.c -- see mem_strength.h */

#include "mem_strength.h"

int memory_strength_mult(int v, int coeff)
{
    int sign;
    unsigned int abs_v;
    int sum_val = 0;
    int k = 0;   /* k is the bit position, initialize to 0 */

    /* define sign, so later can use the abs value */
    if (v < 0) {
        sign = -1;
    } else {
        sign = 1;
    }

    abs_v = (v < 0) ? (unsigned int)(-v) : (unsigned int)v;

    while (abs_v) {          /* while abs_v != 0 <=> still 1s in abs_v, so still need to do calculation */
        if (abs_v & 1U) {                    /* if the kth bit is 1               */
            int value = (1 << k);            /* decimal value of the kth bit (2^k) */
            value = value * coeff;           /* value * coeff ... (beta_int OR gamma_int) */
            sum_val += value >> MEM_STRENGTH_NUM_SHIFT;   /* value / 8 */
        }
        abs_v >>= 1;         /* get rid of the LSB, and get ready for the next iteration */
        k++;
    }

    return sign * sum_val;
}
