#include <stdio.h>
#include "vnu_int4.h"
#include "RNG.h"

static const int num_shift = 3;

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
This is used for the bias update for DMem-BP

# From FPGA paper (optimization of multiplication)
# We further reduce the logic requirements by simplifying the multiplication:
# Instead of implementing a full multiplier for µ_int β_int,
# we expand each bit of the bitwise representation of µ_int to β_int, shift right by m places,
# then null all effective factional bits before summing resulting values for the total result.
*/

int memory_strength_mult (int v, int coeff) {
    // define sign, so later can use the abs value
    int sign = (v < 0) ? -1:1;
    int abs_v = (v < 0) ? -v:v;
    int sum_val = 0;
    int value = 0;
    int k =0;   // k is the bit position, initialize to 0 (LSB)
    while (abs_v > 0){ 
        if(abs_v & 1){ // if the kth bit is 1
            value = 1 << k; // decimal value of the kth bit (2^k)
            value = value * coeff;  // value * coeff ... (beta_int OR gamma_int)
            sum_val += value >> num_shift;  // value / 8
        }
        abs_v = abs_v >> 1; // get rid of the LSB, and get ready for the next iteration
        k++;
    }

    return sign * sum_val;
}


/*
    cnu_messages is an array. Passed by reference
*/
int vnu_hardware_int4(cnu_message_type* cnu_messages, int degree, int lambda_0_int, int t, vnu_result_type* vnu_result_ptr){
    int miu_val[VNU_MAX_DEG];
    int marginals;
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
        ---- Step 2: Use RNG to update beta_int, and initialize marginals
        For DMem-BP: error_prior update  Λ_j(t) = (1-γ)·Λ_j(0) + γ·M_j(t-1)
    */
    uint32_t st = 0xACE1ACE1u;      /* 这个 VNU 的 LFSR state, 非零 */
    int beta_int = rng_beta_int(&st);
    if (t = 1){
        marginals = lambda_0_int;
    } else {
        marginals = memory_strength_mult(lambda_0_int, beta_int) + vnu_result_ptr->marginal - memory_strength_mult(vnu_result_ptr->marginal, beta_int);
    }

    /*
        ---- Step 3: Compute margin M_j (Equ 3) ----
    */
    for (i = 0; i < degree; i++){
        marginals += miu_val[i];
    }

    /*
        ---- Step 4: Per-edge exclusive sum (Equ 2) as VNU message v ----
        full sum - self = exclusive sum    
    */
    
    for (i = 0; i < degree; i++){
        vnu_result_ptr->vnu_messages[i] = bound_value(marginals - miu_val[i]);
    }

    /*
        ---- Step 5: Hard decision ----
        HD = 1/2 (1-sgn(marginal_j)); sign is 1 (positive); -1 (negative); 0 (0)
        e_j = 1 if M_j < 0 (IS error), 0 otherwise

        reference for the decision: marginal = 0, HD = 1:
        relay/crates/relay_bp/src/bp/min_sum.rs
        line 616-622
    */

    vnu_result_ptr->hard_decision = (marginals <= 0) ? 1 : 0;

    /*
        ---- Step 6: clamp marginal_j ----
    */

    vnu_result_ptr->marginal = bound_value(marginals);

    return 0;
}