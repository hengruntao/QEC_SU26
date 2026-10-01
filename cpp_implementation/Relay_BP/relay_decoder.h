#ifndef RELAY_BP_H
#define RELAY_BP_H

#include "../DMem_BP/dmem_bp.h"

#define RELAY_R 8   //maximum number of relay legs (0-indexed)

#define RELAY_S 1   //number of solutions sought

#define RELAY_T0 80 //maximum number of iterations for the first leg
#define RELAY_TR 60 //maximum number of iterations for each leg except the first one

#define RELAY_BETA_LEG_0 7

int decode_relay(const int error[H_X_COLS], int lambda_j_0_int, uint32_t seed,
                 int e_hat_out[H_X_COLS], int *total_iters_out,
                 int *num_sol_out, int *legs_used_out);

#endif