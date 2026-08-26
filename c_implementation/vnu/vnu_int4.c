#include <stdio.h>
#include "vnu_int4.h"

/*  
    Rust reference code relay/crates/relay_bp/src/bp/min_sum.rs
    line 590 - 614
    Implement the bound_value function to clamp any potential overflow
*/

static int bound_value(int val){
    if (val > MAX_VAL) return MAX_VAL;
    else if (val < -MAX_VAL) return -MAX_VAL;
    return val;
}

/*
    cnu_messages is an array. Passed by reference
*/
int vnu_hardware_int4(cnu_message_type* cnu_messages, int degree, int lambda_j, vnu_result_type* vnu_result_ptr){
    int miu_val[VNU_MAX_DEG];
    int marginals = lambda_j;
    int i;

    if (cnu_messages == NULL || vnu_result_ptr == NULL || degree < 0 || degree > VNU_MAX_DEG) return -1;

    /*
        ---- Step 1: Transfer CNU outputs to μ values ----
        CNU deferred the exclusive min to VNU
        selector == 1: this edge was the argmin -> use min2
        selector == 0: this edge was NOT the argmin -> use min1
    */

    for (i = 0; i < degree; i++){
        cnu_message_type* cnu_i_message = cnu_messages + i;
        int exclusive_minimum;
        if (cnu_i_message->selector == 1) exclusive_minimum = cnu_i_message->min2_scaled;
        else exclusive_minimum = cnu_i_message->min1_scaled;
        miu_val[i] = (cnu_i_message->sign == 1) ? -exclusive_minimum : exclusive_minimum;
    }

    /*
        ---- Step 2: Compute margin M_j (Equ 3) ----
    */

    for (i = 0; i < degree; i++){
        marginals += miu_val[i];
    }

    /*
        ---- Step 3: Per-edge exclusive sum (Equ 2) as VNU message v ----
        full sum - self = exclusive sum    
    */
    
    for (i = 0; i < degree; i++){
        vnu_result_ptr->vnu_messages[i] = bound_value(marginals - miu_val[i]);
    }

    /*
        ---- Step 4: Hard decision ----
        HD = 1/2 (1-sgn(marginal_j)); sign is 1 (positive); -1 (negative); 0 (0)
        e_j = 1 if M_j < 0 (IS error), 0 otherwise

        reference for the decision: marginal = 0, HD = 1:
        relay/crates/relay_bp/src/bp/min_sum.rs
        line 616-622
    */

    vnu_result_ptr->hard_decision = (marginals <= 0) ? 1 : 0;

    /*
        ---- Step 5: clamp marginal_j ----
    */

    vnu_result_ptr->marginal = bound_value(marginals);

    return 0;
}