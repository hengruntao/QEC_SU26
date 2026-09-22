#ifndef VNU_INT4_H
#define VNU_INT4_H

#include "../int4_max_val.h"
#include "RNG.h"

#define VNU_DEGREE 3
#define VNU_MAX_DEG VNU_DEGREE

typedef struct {
    qec_bit_t sign;
    qec_bit_t selector;
    qec_magnitude_t min1_scaled;
    qec_magnitude_t min2_scaled;
} cnu_to_vnu_message_t;

typedef struct {
    qec_message_t vnu_messages[VNU_DEGREE];
    qec_message_t marginal;
    qec_bit_t hard_decision;
} vnu_result_type;

typedef struct {
    qec_lfsr_t lfsr;
    qec_beta_t beta_int;
    qec_message_t M_reg;
} vnu_state_type;

qec_vnu_accumulator_t memory_strength_mult(qec_message_t value,
                                           qec_beta_t coefficient);

void vnu_hardware_int4(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    qec_magnitude_t lambda_0,
    qec_bit_t init,
    qec_bit_t new_leg,
    vnu_state_type *state,
    vnu_result_type *result);

void vnu_hls_top(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    qec_magnitude_t lambda_0,
    qec_bit_t init,
    qec_bit_t new_leg,
    vnu_state_type *state,
    vnu_result_type *result);

int memory_strength_mult(int value, int coefficient);

int vnu_hardware_int4(
    const cnu_to_vnu_message_t cnu_messages[VNU_DEGREE],
    int degree,
    int lambda_0,
    int init,
    int new_leg,
    vnu_state_type *state,
    vnu_result_type *result);

#endif
