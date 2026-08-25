/* cnu_int4.c -- see cnu_int4.h
 *
 * C port of cnu_python/cnu_int4.py.
 * Difference between cnu_fl64: third input variable changed from "alpha" to "t"
 */

#include "cnu_int4.h"

/* alpha scaling is applied as  m - (m >> t).
 *
 * Python shifts by arbitrarily large counts and simply yields 0, but in C a
 * shift by >= the width of the promoted type is undefined behaviour, and the
 * BP loop drives t up to 60.  Saturate the shift count here so the C result
 * keeps matching the Python one. */
static int alpha_scale(int magnitude, int t)
{
    if (t >= 31) {
        return magnitude;   /* magnitude - 0 */
    }
    return magnitude - (magnitude >> t);
}

int cnu_hardware_int4(const int *vnu_messages, int degree, int sigma_i, int t,
                      cnu_result_t *result)
{
    int sign_bits[CNU_MAX_DEGREE];
    int magnitudes[CNU_MAX_DEGREE];
    int full_parity;
    int min1, min2;
    int i, j;

    if (vnu_messages == 0 || result == 0) {
        return -1;
    }
    if (degree < 1 || degree > CNU_MAX_DEGREE || t < 0) {
        return -1;
    }

    /* ---- Step 1: Decompose into sign bits and magnitudes ---- */
    /* Convention: sign bit 0 = positive (or zero), 1 = negative */
    for (i = 0; i < degree; i++) {
        /* v < 0 means MSB is 1 -> IS error; MSB is 0 -> NO error */
        sign_bits[i]  = (vnu_messages[i] < 0) ? 1 : 0;
        magnitudes[i] = (vnu_messages[i] < 0) ? -vnu_messages[i] : vnu_messages[i];
    }
    /*   e.g.:
     *   vnu_message  = [ 3, -5,  2, -7,  1, -4]
     *   sign_bits    = [ 0,  1,  0,  1,  0,  1]
     *   magnitudes   = [ 3,  5,  2,  7,  1,  4] */

    /* ---- Step 2: Compute full parity ---- */
    /* full_parity = s_0 ^ s_1 ^ ... ^ s_{d_c-1} ^ sigma_i
     *
     * 2 sources of info:
     *   1. sigma_i, syndrome bit from QPU (info from stabilizer)
     *   2. sign_bits, guesses from other VNU nodes */
    full_parity = sigma_i;
    for (i = 0; i < degree; i++) {
        full_parity ^= sign_bits[i];   /* parity = 0 -> even number of "1" (even number of "-") */
    }

    /* ---- Step 3: Compute min1, min2 ---- */
    /* min1: minimum of all magnitudes
     * min2: 2nd minimum of all magnitudes */
    min1 = INT4_MAX_VALUE;   /* initialized to max_val of int4 */
    min2 = INT4_MAX_VALUE;
    for (i = 0; i < degree; i++) {
        int temp_val = magnitudes[i];
        if (temp_val < min1) {
            min2 = min1;
            min1 = temp_val;
        } else if (temp_val < min2) {
            min2 = temp_val;
        }
    }

    /* ---- Step 4: Per-edge sign and selector ---- */
    /* sign_out_j = full_parity ^ s_j
     * selector_j = 1 if magnitude_j is the minimum (to choose from min1 & min2)
     * sign = 0 means positive -> likely NO error; sign = 1 means negative -> likely IS error */
    for (j = 0; j < degree; j++) {
        result->signs[j]     = full_parity ^ sign_bits[j];
        result->selectors[j] = (magnitudes[j] == min1) ? 1 : 0;
    }

    /* ---- Step 5: Alpha scaling and return ---- */
    /* alpha is the scaling factor for CNU hardware, it's not the original
     * component of Equ (1) in the FPGA paper */
    result->degree      = degree;
    result->min1_scaled = alpha_scale(min1, t);
    result->min2_scaled = alpha_scale(min2, t);

    return 0;
}
