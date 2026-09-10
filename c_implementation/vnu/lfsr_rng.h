#ifndef LFSR_RNG_H
#define LFSR_RNG_H

#include <stdint.h>

/* Per-VNU RNG state. One instance is required for each variable node. */
typedef struct {
    uint8_t lfsr;
    uint8_t beta_int;
} lfsr_rng_state_t;

/* Restore the configured seed and the initial beta value, 7/8. */
void lfsr_rng_reset(lfsr_rng_state_t *state, uint8_t seed);

/* Advance one decoder cycle. beta_int is updated only at a new Relay leg. */
void lfsr_rng_step(lfsr_rng_state_t *state, uint8_t en, uint8_t new_leg);

/* Return gamma in units of 1/8, where gamma_int = 8 - beta_int. */
int8_t lfsr_rng_gamma_int(const lfsr_rng_state_t *state);

#endif
