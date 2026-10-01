#ifndef RNG_H
#define RNG_H

#include "../hls_types.h"

qec_beta_t rng_beta_int(qec_lfsr_t *state);

void rng_hls_top(qec_lfsr_t state_in,
                 qec_lfsr_t *state_out,
                 qec_beta_t *beta_out);

void rng_seed_all(qec_lfsr_t states[QEC_NUM_VARIABLE_NODES],
                  qec_lfsr_t global_seed);

#endif
