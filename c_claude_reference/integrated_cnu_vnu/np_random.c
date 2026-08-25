/* np_random.c -- see np_random.h */

#include "np_random.h"

#define MT_N          NP_MT19937_N
#define MT_M          397
#define MT_MATRIX_A   0x9908b0dfU
#define MT_UPPER_MASK 0x80000000U
#define MT_LOWER_MASK 0x7fffffffU

void np_random_seed(np_random_state *state, unsigned int seed)
{
    int pos;
    /* Knuth's PRNG as used in the Mersenne Twister reference implementation */
    for (pos = 0; pos < MT_N; pos++) {
        state->key[pos] = seed & 0xffffffffU;
        seed = (1812433253U * (seed ^ (seed >> 30)) + (unsigned int)pos + 1U) & 0xffffffffU;
    }
    state->pos = MT_N;
}

/* Regenerate the whole 624-word block. */
static void mt19937_gen(np_random_state *state)
{
    unsigned int y;
    int i;

    for (i = 0; i < MT_N - MT_M; i++) {
        y = (state->key[i] & MT_UPPER_MASK) | (state->key[i + 1] & MT_LOWER_MASK);
        state->key[i] = state->key[i + MT_M] ^ (y >> 1) ^ (-(int)(y & 1U) & MT_MATRIX_A);
    }
    for (; i < MT_N - 1; i++) {
        y = (state->key[i] & MT_UPPER_MASK) | (state->key[i + 1] & MT_LOWER_MASK);
        state->key[i] = state->key[i + (MT_M - MT_N)] ^ (y >> 1) ^ (-(int)(y & 1U) & MT_MATRIX_A);
    }
    y = (state->key[MT_N - 1] & MT_UPPER_MASK) | (state->key[0] & MT_LOWER_MASK);
    state->key[MT_N - 1] = state->key[MT_M - 1] ^ (y >> 1) ^ (-(int)(y & 1U) & MT_MATRIX_A);

    state->pos = 0;
}

unsigned int np_random_next_uint32(np_random_state *state)
{
    unsigned int y;

    if (state->pos == MT_N) {
        mt19937_gen(state);
    }
    y = state->key[state->pos++];

    /* tempering */
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);

    return y & 0xffffffffU;
}

double np_random_next_double(np_random_state *state)
{
    unsigned int a = np_random_next_uint32(state) >> 5;   /* 27 bits */
    unsigned int b = np_random_next_uint32(state) >> 6;   /* 26 bits */
    return (a * 67108864.0 + b) / 9007199254740992.0;
}

void np_random_rand(np_random_state *state, double *out, int count)
{
    int i;
    for (i = 0; i < count; i++) {
        out[i] = np_random_next_double(state);
    }
}
