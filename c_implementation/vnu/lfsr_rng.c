#include "lfsr_rng.h"

enum {
    INITIAL_BETA_INT = 7,
    BETA_OFFSET = 3,
    RANDOM_VALUE_MASK = 0x07,
    MEMORY_SCALE = 8
};

void lfsr_rng_reset(lfsr_rng_state_t *state, uint8_t seed)
{
    if (state == 0) {
        return;
    }

    state->lfsr = seed;
    state->beta_int = INITIAL_BETA_INT;
}

void lfsr_rng_step(lfsr_rng_state_t *state, uint8_t en, uint8_t new_leg)
{
    uint8_t old_lfsr;
    uint8_t feedback;

    if (state == 0 || en == 0U) {
        return;
    }

    old_lfsr = state->lfsr;

    /* A leg samples the current RNG value before this cycle advances it. */
    if (new_leg != 0U) {
        state->beta_int =
            (uint8_t)(BETA_OFFSET + (old_lfsr & RANDOM_VALUE_MASK));
    }

    feedback = (uint8_t)(((old_lfsr >> 7U) ^
                          (old_lfsr >> 5U) ^
                          (old_lfsr >> 4U) ^
                          (old_lfsr >> 3U)) & 0x01U);

    state->lfsr = (uint8_t)((uint8_t)(old_lfsr << 1U) | feedback);
}

int8_t lfsr_rng_gamma_int(const lfsr_rng_state_t *state)
{
    if (state == 0) {
        return 0;
    }

    return (int8_t)(MEMORY_SCALE - (int)state->beta_int);
}
