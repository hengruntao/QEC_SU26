#ifndef RNG_H
#define RNG_H
#include <stdint.h>

int rng_beta_int(uint32_t *state);

/* generating different seeds for #n VNUs
   global_seed=1 -> use default value */
void rng_seed_all(uint32_t *states, int n, uint32_t global_seed);

#endif