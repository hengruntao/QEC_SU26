// #ifndef RELAY_BP_H
// #define RELAY_BP_H

// #include "../DMem_BP/dmem_bp.h"

// #define RELAY_R 8   //maximum number of relay legs (0-indexed)

// #define RELAY_S 1   //number of solutions sought

// #define RELAY_T0 80 //maximum number of iterations for the first leg
// #define RELAY_TR 60 //maximum number of iterations for each leg except the first one

// #define RELAY_BETA_LEG_0 7

// /* HLS top function.
//    syndrome  : packed σ, bit i = check i               (relay_bp_top: syndrome[71:0])
//    lambda_0  : per-VN unsigned prior Λ_j(0), 4 bit     (relay_bp_top: lambda_0[0:143])
//    seed      : LFSR seed -- to be removed when the RNG is replaced by a fixed β table
//    e_hat_out : packed ê, bit j = variable j            (relay_bp_top: e_hat[143:0])
//    return    : 1 if at least one leg converged         (relay_bp_top: converged)       */
// int decode_relay(syndrome_t syndrome,
//                  const qec_magnitude_t lambda_0[H_X_COLS],
//                  uint32_t seed,
//                  e_hat_t *e_hat_out, int *total_iters_out,
//                  int *num_sol_out, int *legs_used_out);

// #endif


/* using beta table */
#ifndef RELAY_BP_H
#define RELAY_BP_H

#include "../DMem_BP/dmem_bp.h"

#define RELAY_R 8   //maximum number of relay legs (0-indexed)

#define RELAY_S 1   //number of solutions sought

#define RELAY_T0 80 //maximum number of iterations for the first leg
#define RELAY_TR 60 //maximum number of iterations for each leg except the first one

#define RELAY_BETA_LEG_0 7

/* HLS top function.
   syndrome   : packed σ, bit i = check i              (relay_bp_top: syndrome[71:0])
   lambda_0   : per-VN unsigned prior Λ_j(0), 4 bit     (relay_bp_top: lambda_0[0:143])
   beta_table : β_int per leg and VN, 4 bit; row r is used by leg r (row 0 = leg 0)
                test mode: β of every leg comes from this table; the VNU LFSRs are kept
                but never asked for a new β (is_new_leg = 0), so all implementations see the same β
                (paper 2510.21600 §4.2.1: β = 1 − γ, β_int = round(β·M), M = 8)
   e_hat_out  : packed ê, bit j = variable j            (relay_bp_top: e_hat[143:0])
   return     : 1 if at least one leg converged         (relay_bp_top: converged)       */
int decode_relay(syndrome_t syndrome,
                 const qec_magnitude_t lambda_0[H_X_COLS],
                 const qec_beta_t beta_table[RELAY_R + 1][H_X_COLS],
                 e_hat_t *e_hat_out, int *total_iters_out,
                 int *num_sol_out, int *legs_used_out);

#endif