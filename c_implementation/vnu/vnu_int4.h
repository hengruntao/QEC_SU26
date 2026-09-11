/*
    ------ Copied from python implementation ------
    VNU: processes one variable node (one column of H).
    
    Inputs:
        cnu_messages : list of dict, length = i
                      Each dict from a neighboring CNU i has keys:
                        'sign'        : int (0 or 1)
                        'selector'    : int (0 or 1)
                        'min1_scaled' : int
                        'min2_scaled' : int
        lambda_j    : int
                      Error prior Λ_j(0) = log((1-p_j)/p_j)
                      Λ_j(t) = (1-γ_j)*Λ_j(0) + γ_j*M_j(t−1)
    
    IMPORTANRT:
        IT IS the CALLER's responsibility to pass in-scale lambda_j

    Returns:
            (struct)
            'vnu_messages'   : list of int4, ν_{j→i} for each edge
            'marginal'       : int, M_j
            'hard_decision'  : int (0 or 1), ê_j

*/

#ifndef VNU_INT4_H
#define VNU_INT4_H
#define VNU_MAX_DEG 6
#include "../int4_max_val.h"

/*
    This defines a single CNU_i to VNU_j message.
    And the current working VNU_j will gather the info from all its neighboring CNUs.
*/
typedef struct {
    int sign;
    int selector;
    int min1_scaled;
    int min2_scaled;
} cnu_message_type;

/*
    This defines what VNU_j outputs.
    vnu_messages is an array containing the message from this current VNU_j to all its neighboring CNUs.
*/
typedef struct {
    int vnu_messages[VNU_MAX_DEG];
    int marginal;
    int hard_decision;
} vnu_result_type;

/*
    storing values for the fig3c extra datapath
*/

typedef struct {
    uint32_t lfsr;      /* RNG state，每个 VNU 一个，常驻 */
    int      beta_int;  /* 当前 leg 的 1-γ；leg 0 = 7 */
    int      M_reg;     /* Fig 3c 的 M_j register */
} vnu_state_type;

/*
    - cnu_message is the combined set of info from VNU_j's neighboring CNUs
      use struct here instead of int* as in cnu_int4.h is because info from CNUs to VNU_j is more complicated than a single array

    - vnu_result_ptr points to the struct that stores the output of VNU_j
*/

int vnu_hardware_int4(cnu_message_type* cnu_message, int degree, int lambda_0_int, int init, int new_leg, vnu_state_type* st, vnu_result_type* vnu_result_ptr);

#endif