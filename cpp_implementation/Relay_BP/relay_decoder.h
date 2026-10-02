#define RELAY_BP_H

#include "../DMem_BP/dmem_bp.h"

#define RELAY_R 8   //maximum number of relay legs (0-indexed)

#define RELAY_S 1   //number of solutions sought

#define RELAY_T0 80 //maximum number of iterations for the first leg
#define RELAY_TR 60 //maximum number of iterations for each leg except the first one

#define RELAY_BETA_LEG_0 7

/* HLS top function.
   syndrome  : packed σ, bit i = check i               (relay_bp_top: syndrome[71:0])
   lambda_0  : per-VN unsigned prior Λ_j(0), 4 bit     (relay_bp_top: lambda_0[0:143])
   seed      : LFSR seed -- to be removed when the RNG is replaced by a fixed β table
   e_hat_out : packed ê, bit j = variable j            (relay_bp_top: e_hat[143:0])
   return    : 1 if at least one leg converged         (relay_bp_top: converged)       */
int decode_relay(syndrome_t syndrome,
                 const qec_magnitude_t lambda_0[H_X_COLS],
                 uint32_t seed,
                 e_hat_t *e_hat_out, int *total_iters_out,
                 int *num_sol_out, int *legs_used_out);

#endif