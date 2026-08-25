/* vnu_int4.c -- see vnu_int4.h
 *
 * C port of vnu_python/vnu_int4.py.
 */

#include "vnu_int4.h"

/* Rust reference code relay/crates/relay_bp/src/bp/min_sum.rs
 *   line 590 - 614
 * Implement the bound_value function to clamp any potential overflow */
static int bound_value(int val)
{
    if (val > VNU_MAX_VALUE) {
        return VNU_MAX_VALUE;
    } else if (val < -VNU_MAX_VALUE) {
        return -VNU_MAX_VALUE;
    }
    return val;
}

int vnu_hardware_int4(const cnu_message_t *cnu_messages, int degree,
                      int lambda_j, vnu_result_t *result)
{
    int miu_values[VNU_MAX_DEGREE];
    int marginal_j;
    int i;

    if (cnu_messages == 0 || result == 0) {
        return -1;
    }
    if (degree < 1 || degree > VNU_MAX_DEGREE) {
        return -1;
    }

    /* ---- Step 1: Transfer CNU outputs to miu values ---- */
    /* CNU deferred the exclusive min to VNU
     * selector == 1: this edge was the argmin -> use min2
     * selector == 0: this edge was NOT the argmin -> use min1 */
    for (i = 0; i < degree; i++) {
        const cnu_message_t *cnu_i_message = &cnu_messages[i];
        int exclusive_minimum;

        if (cnu_i_message->selector == 1) {
            exclusive_minimum = cnu_i_message->min2_scaled;
        } else {
            exclusive_minimum = cnu_i_message->min1_scaled;
        }

        /* (-1)^sign * exclusive_minimum */
        miu_values[i] = (cnu_i_message->sign != 0) ? -exclusive_minimum
                                                   :  exclusive_minimum;
    }

    /* ---- Step 2: Compute margin M_j (Equ 3) ---- */
    marginal_j = lambda_j;   /* initialize to Lambda_j */
    for (i = 0; i < degree; i++) {
        marginal_j += miu_values[i];
    }

    /* ---- Step 3: Per-edge exclusive sum (Equ 2) as VNU message v ---- */
    /* full sum - self = exclusive sum */
    for (i = 0; i < degree; i++) {
        result->vnu_messages[i] = bound_value(marginal_j - miu_values[i]);
    }

    /* ---- Step 4: Hard decision ---- */
    /* HD = 1/2 (1-sgn(marginal_j)); sign is 1 (positive); -1 (negative); 0 (0)
     * e_j = 1 if M_j < 0 (IS error), 0 otherwise
     *
     * reference for the decision: marginal = 0, HD = 1:
     * relay/crates/relay_bp/src/bp/min_sum.rs
     *   line 616-622 */
    result->hard_decision = (marginal_j <= 0) ? 1 : 0;

    /* ---- Step 5: clamp marginal_j ---- */
    result->degree   = degree;
    result->marginal = bound_value(marginal_j);

    return 0;
}
