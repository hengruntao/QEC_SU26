/*
    ------ Copied from python implementation ------
    CNU: processes one check node (one row of H)
    input as "v", output as "miu"
    
    Inputs:
        vnu_messages : list/array of int, range [-15, +15] for int4.2.8
                        Incoming messages v_{j->i} from neighboring variable nodes.
        sigma_i      : int (0 or 1) 1 means parity check detects an odd number of errors
                        Syndrome/detector bit for this check node. (message from QPU)
        t            : int (>= 1), BP iteration index.
                        Determines alpha = 1 - 2^(-t).
    IMPORTANT concept:
        sigma_i is the ONLY ground truth (message from the stabilizer in QPU)
        vnu_messages are ONLY guesses!!

    Returns:
            (struct)
            'min1_scaled'  : int, alpha * min1 (shared across all edges)
            'min2_scaled'  : int, alpha * min2 (shared across all edges)
            'signs_per_edge'        : list of int (0 or 1), per-edge output sign bits
            'selectors_per_edge'    : list of int (0 or 1), per-edge selector bits

*/



#ifndef CNU_INT4_H
#define CNU_INT4_H
#define CNU_MAX_DEG 6
#include "../int4_max_val.h"

/*
    This defines what CNU_i outputs.



*/

typedef struct {
    int min1_scaled;
    int min2_scaled;
    int signs_per_edge[CNU_MAX_DEG];
    int selectors_per_edge[CNU_MAX_DEG];
} cnu_result_type;

/*
    - VNU messages is an array. And that array is passed by reference here. (NOT the same as vnu_result_type defined in vnu_int4.h)
      It consists of all the info from all CNU_i's neighboring VNUs

    - degree is the length of vnu_messages, or simply the number of neighboring VNUs CNU_i has

    - cnu_result_ptr points to the struct that stores the output of CNU_i
*/
int cnu_hardware_int4(int* vnu_messages, int degree, int sigma_i, int t, cnu_result_type* cnu_result_ptr);

#endif