#ifndef QEC_HLS_TYPES_H
#define QEC_HLS_TYPES_H

#include <ap_int.h>

static const int QEC_MESSAGE_BITS = 5;
static const int QEC_MAGNITUDE_BITS = 4;
static const int QEC_MAX_MAGNITUDE = 15;

typedef ap_uint<1> qec_bit_t;
typedef ap_int<QEC_MESSAGE_BITS> qec_message_t;
typedef ap_uint<QEC_MAGNITUDE_BITS> qec_magnitude_t;
typedef ap_uint<7> bp_iteration_t;

#endif
