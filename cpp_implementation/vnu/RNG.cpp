#include "RNG.h"

static qec_lfsr_t lfsr_step(qec_lfsr_t state)
{
    const qec_bit_t feedback =
        state[31] ^ state[21] ^ state[1] ^ state[0];
    return (state << 1) | feedback;
}

qec_beta_t rng_beta_int(qec_lfsr_t *state)
{
    qec_lfsr_t next = *state;
    if (next == 0) {
        next = 1;
    }

    for (int step = 0; step < 3; ++step) {
        next = lfsr_step(next);
    }

    *state = next;
    return qec_beta_t(3) + qec_beta_t(next.range(2, 0));
}

void rng_hls_top(qec_lfsr_t state_in,
                 qec_lfsr_t *state_out,
                 qec_beta_t *beta_out)
{
    qec_lfsr_t state = state_in;
    *beta_out = rng_beta_int(&state);
    *state_out = state;
}

static qec_lfsr_t lin_apply(
    const qec_lfsr_t transform[32], qec_lfsr_t state)
{
    qec_lfsr_t result = 0;
    for (int bit = 0; bit < 32; ++bit) {
        if (state[bit]) {
            result ^= transform[bit];
        }
    }
    return result;
}

static void lin_compose(qec_lfsr_t output[32],
                        const qec_lfsr_t left[32],
                        const qec_lfsr_t right[32])
{
    qec_lfsr_t temporary[32];
    for (int bit = 0; bit < 32; ++bit) {
        temporary[bit] = lin_apply(left, right[bit]);
    }
    for (int bit = 0; bit < 32; ++bit) {
        output[bit] = temporary[bit];
    }
}

static void lfsr_jump_matrix(qec_lfsr_t transform[32], qec_lfsr_t distance)
{
    qec_lfsr_t base[32];
    qec_lfsr_t result[32];

    for (int bit = 0; bit < 32; ++bit) {
        base[bit] = lfsr_step(qec_lfsr_t(1) << bit);
        result[bit] = qec_lfsr_t(1) << bit;
    }

    for (int power = 0; power < 32; ++power) {
        if (distance[power]) {
            lin_compose(result, base, result);
        }
        lin_compose(base, base, base);
    }

    for (int bit = 0; bit < 32; ++bit) {
        transform[bit] = result[bit];
    }
}

void rng_seed_all(qec_lfsr_t states[QEC_NUM_VARIABLE_NODES],
                  qec_lfsr_t global_seed)
{
    qec_lfsr_t jump[32];
    qec_lfsr_t state = global_seed == 0 ? qec_lfsr_t(0x1234ABCDu)
                                        : global_seed;
    const qec_lfsr_t stride =
        qec_lfsr_t(0xFFFFFFFFu / QEC_NUM_VARIABLE_NODES);

    lfsr_jump_matrix(jump, stride);
    for (int variable = 0; variable < QEC_NUM_VARIABLE_NODES; ++variable) {
        states[variable] = state;
        state = lin_apply(jump, state);
    }
}
