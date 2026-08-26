#include <stdio.h>
#include "cnu_int4.h"

static int alpha_shift(int magintude, int t){
    if (t >= 31) return magintude;  // set to 31 because int has 32 bits. And shifting beyong that number is undefined behavior
    return magintude - (magintude >> t);
}

int cnu_hardware_int4(int* vnu_messages, int degree, int sigma_i, int t, cnu_result_type* cnu_result_ptr){
    int sign_bits[CNU_MAX_DEG];
    int magnitudes[CNU_MAX_DEG];
    int full_parity = sigma_i;
    int min1 = MAX_VAL;
    int min2 = MAX_VAL;
    int i;

    if(vnu_messages == NULL || cnu_result_ptr == NULL || t < 0 || degree < 0 || degree > CNU_MAX_DEG){
        return -1;
    }

    /* ---- Step 1: Decompose vnu_messages into sign bits and magnitudes ----
    Convention: sign bit 0 = positive (or zero), 1 = negative */

    for (i = 0; i < degree; i++){
        sign_bits[i] = (vnu_messages[i] < 0) ? 1 : 0;   // vnu < 0 means MSB is 1 -> IS error; MSB is 0 -> NO error
        magnitudes[i] = (vnu_messages[i] < 0) ? -vnu_messages[i] : vnu_messages[i];
    }
    /*  e.g.:
        vnu_message  = [ 3, -5,  2, -7,  1, -4]
        sign_bits    = [ 0,  1,  0,  1,  0,  1]
        magnitudes   = [ 3,  5,  2,  7,  1,  4]
    */


    /* ---- Step 2: Compute full parity ----
        full_parity = s_0 ⊕ s_1 ⊕ ... ⊕ s_{d_c-1} ⊕ σ_i

        2 sources of info:
            1. sigma_i, syndrom bit from QPU (info from stabilizer)
            2. sign_bits, guesses from other VNU nodes
    */

    for(i = 0; i < degree; i++){
        full_parity ^= sign_bits[i];
    }


    /* ---- Step 3: Compute min1, min2, argmin_idx ----
        min1: minimum of all magnitude
        min2: 2nd minimum of all magnitude
        argmin_idx: index of the first min1 -> if min1 repeats, only the first one is recorded
    */

    for(i = 0; i < degree; i++){
        int temp_val = magnitudes[i];
        if (temp_val < min1){
            min2 = min1;
            min1 = temp_val;
        }
        else if(temp_val < min2){
            min2 = temp_val;
        }
    }


    /* ---- Step 4: Per-edge sign and selector ----
        sign_out_j = full_parity ⊕ s_j
        selector_j = 1 if j == argmin_idx (use min2), else 0 (use min1)
        sign = 0 means positive -> likely NO error; sign = 1 means negative -> likely IS error
    */
    for (i = 0; i < degree; i++){
        cnu_result_ptr->signs_per_edge[i] = full_parity ^ sign_bits[i];
        cnu_result_ptr->selectors_per_edge[i] = (magnitudes[i] == min1) ? 1:0;
    }

    /* ---- Step 5: Alpha scaling and return ----
    α is the scaling factor for CNU hardware, it's not the original component of Equ (1) in FPGA paper
    */

    cnu_result_ptr->min1_scaled = alpha_shift(min1, t);
    cnu_result_ptr->min2_scaled = alpha_shift(min2, t);

    return 0;

}