#include <stdint.h>

/* 32-bit Fibonacci LFSR, feedback = s[31]^s[21]^s[1]^s[0], period 2^32-1 */
int rng_beta_int(uint32_t *state){
    uint32_t s = *state;
    uint32_t fb;
    int k;

    if (s == 0u) s = 1u;                    /* all-zero is the lock-up state */

    for (k = 0; k < 3; k++){                /* advance 3 steps -> 3 new bits */
        fb = ((s >> 31) ^ (s >> 21) ^ (s >> 1) ^ s) & 1u;
        s  = (s << 1) | fb;
    }

    *state = s;
    return 3 + (int)(s & 0x7u);             /* 3 + {0..7} = [3, 10] */
}