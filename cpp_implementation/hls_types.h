#ifndef QEC_HLS_TYPES_H
#define QEC_HLS_TYPES_H

#include <ap_int.h>

static const int QEC_MESSAGE_BITS = 5;
static const int QEC_MAGNITUDE_BITS = 4;
static const int QEC_MAX_MAGNITUDE = 15;
static const int QEC_NUM_VARIABLE_NODES = 144;

/* memory strength scale M = 2^QEC_MEMORY_SCALE_LOG2 = 16 (was 8).
   beta_int = round(beta * M); the RNG draws beta_int in [QEC_BETA_MIN, QEC_BETA_MAX] = [5, 20]
   (paper 2510.21600: gamma in [-0.24, 0.66] -> beta in [0.34, 1.24] -> [5, 20] at M = 16;
    same values as the RTL vnu.sv with M_LOG2 = 4) */
static const int QEC_MEMORY_SCALE_LOG2 = 4;
static const int QEC_BETA_MIN = 5;
static const int QEC_BETA_MAX = 20;

typedef ap_uint<1> qec_bit_t;
typedef ap_int<QEC_MESSAGE_BITS> qec_message_t;
typedef ap_uint<QEC_MAGNITUDE_BITS> qec_magnitude_t;
typedef ap_uint<5> qec_beta_t;     // 5 bits: beta_int up to 20 (was 4 bits, max 10)
typedef ap_int<7> qec_vnu_accumulator_t;
typedef ap_uint<7> bp_iteration_t;
typedef ap_uint<8> qec_lfsr_t;     // 8-bit LFSR, same as the RTL VNU (was 32 bits)

#endif
