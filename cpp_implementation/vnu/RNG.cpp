#include "RNG.h"

/* 8-bit Fibonacci LFSR, same as the hand-written RTL (rtl/.../vnu.sv):
       lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3]};
   feedback polynomial x^8 + x^6 + x^5 + x^4 + 1, maximal length: every non-zero
   state lies on one cycle of 255 states. The all-zero state never changes, so a
   seed must be non-zero (rng_seed_all and gen_lfsr_seeds only produce non-zero states). */
static qec_lfsr_t lfsr_step(qec_lfsr_t state)
{
    const qec_bit_t feedback =
        state[7] ^ state[5] ^ state[4] ^ state[3];
    return (state << 1) | feedback;
}

/* One beta draw = one LFSR step, same order as vnu.sv on new_leg:
       beta_int <= BETA_BASE + lfsr[3:0];   (uses the CURRENT state)
       lfsr     <= next state;
   beta_int = 5 + lfsr[3:0]  ->  16 values, beta_int in [5, 20]
   (M = 16: beta = beta_int / 16 in [0.3125, 1.25], gamma = 1 - beta in [-0.25, 0.6875]) */
qec_beta_t rng_beta_int(qec_lfsr_t *state)
{
#ifdef VNU_OPT
#pragma HLS INLINE
#endif
    const qec_lfsr_t current = *state;
    *state = lfsr_step(current);
    return qec_beta_t(QEC_BETA_MIN) + qec_beta_t(current.range(3, 0));
}

void rng_hls_top(qec_lfsr_t state_in,
                 qec_lfsr_t *state_out,
                 qec_beta_t *beta_out)
{
    qec_lfsr_t state = state_in;
    *beta_out = rng_beta_int(&state);
    *state_out = state;
}

/* Per-VNU start states (offline helper: used by gen_lfsr_seeds.cpp and the testbenches,
   NOT reachable from decode_relay, so it is never synthesized).
   Leap-ahead seeding on the 255-state cycle: VN j starts floor(j * 255 / 144) steps after
   the global start state, i.e. the 144 VNUs are spread as evenly as possible around the cycle
   (gaps of 1 or 2 steps; with 144 VNUs on 255 states no larger spacing exists).
   global_seed == 0 selects the default start state 0xA5 (vnu.sv's default LFSR_SEED). */
void rng_seed_all(qec_lfsr_t states[QEC_NUM_VARIABLE_NODES],
                  qec_lfsr_t global_seed)
{
    const int period = 255;
    qec_lfsr_t state = (global_seed == 0) ? qec_lfsr_t(0xA5) : global_seed;
    int position = 0;   // how many steps "state" is ahead of the start state

    for (int variable = 0; variable < QEC_NUM_VARIABLE_NODES; ++variable) {
        const int target = (variable * period) / QEC_NUM_VARIABLE_NODES;
        while (position < target) {
            state = lfsr_step(state);
            ++position;
        }
        states[variable] = state;
    }
}
