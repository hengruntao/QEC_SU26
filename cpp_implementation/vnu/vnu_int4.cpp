#include "vnu_int4.h"

static const int MEMORY_SCALE_SHIFT = 3;

static qec_message_t bound_value(qec_vnu_accumulator_t value)
{
    if (value > QEC_MAX_MAGNITUDE) {
        return qec_message_t(QEC_MAX_MAGNITUDE);
    }
    if (value < -QEC_MAX_MAGNITUDE) {
        return qec_message_t(-QEC_MAX_MAGNITUDE);
    }
    return qec_message_t(value);
}

qec_vnu_accumulator_t memory_strength_mult(qec_message_t value,
                                           qec_beta_t coefficient)
{
    const qec_bit_t negative = value < 0;
    const qec_magnitude_t magnitude =
        negative ? qec_magnitude_t(-value) : qec_magnitude_t(value);
    qec_vnu_accumulator_t sum = 0;

    for (int bit = 0; bit < QEC_MAGNITUDE_BITS; ++bit) {
        if (magnitude[bit]) {
            const ap_uint<8> partial =
                (ap_uint<8>(1) << bit) * ap_uint<8>(coefficient);
            sum += qec_vnu_accumulator_t(partial >> MEMORY_SCALE_SHIFT);
        }
    }

    return negative ? qec_vnu_accumulator_t(-sum) : sum;
}

void vnu_hardware_int4(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    qec_magnitude_t lambda_0,
    qec_bit_t init,
    qec_bit_t new_leg,
    vnu_state_type *state,
    vnu_result_type *result)
{
    qec_vnu_accumulator_t mu[VNU_DEGREE];

    for (int edge = 0; edge < VNU_DEGREE; ++edge) {
        const qec_magnitude_t exclusive_minimum =
            cnu_messages[edge].selector ? cnu_messages[edge].min2_scaled
                                        : cnu_messages[edge].min1_scaled;
        mu[edge] = cnu_messages[edge].sign
                       ? qec_vnu_accumulator_t(-exclusive_minimum)
                       : qec_vnu_accumulator_t(exclusive_minimum);
    }

    if (new_leg) {
        state->beta_int = rng_beta_int(&state->lfsr);
    }

    qec_vnu_accumulator_t marginal;
    if (init) {
        marginal = qec_vnu_accumulator_t(lambda_0);
    } else {
        marginal = memory_strength_mult(qec_message_t(lambda_0),
                                        state->beta_int)
                 + qec_vnu_accumulator_t(state->M_reg)
                 - memory_strength_mult(state->M_reg, state->beta_int);
    }

    marginal = qec_vnu_accumulator_t(bound_value(marginal));
    for (int edge = 0; edge < VNU_DEGREE; ++edge) {
        marginal += mu[edge];
    }

    for (int edge = 0; edge < VNU_DEGREE; ++edge) {
        result->vnu_messages[edge] = bound_value(marginal - mu[edge]);
    }

    result->hard_decision = marginal <= 0;
    result->marginal = bound_value(marginal);
    state->M_reg = result->marginal;
}

void vnu_hls_top(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    qec_magnitude_t lambda_0,
    qec_bit_t init,
    qec_bit_t new_leg,
    vnu_state_type *state,
    vnu_result_type *result)
{
    vnu_hardware_int4(cnu_messages, lambda_0, init, new_leg, state, result);
}

int memory_strength_mult(int value, int coefficient)
{
    return static_cast<int>(
        memory_strength_mult(qec_message_t(value), qec_beta_t(coefficient)));
}

int vnu_hardware_int4(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    int degree,
    int lambda_0,
    int init,
    int new_leg,
    vnu_state_type *state,
    vnu_result_type *result)
{
    if (cnu_messages == 0 || state == 0 || result == 0 ||
        degree != VNU_DEGREE || lambda_0 < 0 ||
        lambda_0 > QEC_MAX_MAGNITUDE) {
        return -1;
    }

    vnu_hardware_int4(cnu_messages, qec_magnitude_t(lambda_0),
                      qec_bit_t(init), qec_bit_t(new_leg), state, result);
    return 0;
}
