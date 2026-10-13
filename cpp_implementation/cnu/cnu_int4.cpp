#include "cnu_int4.h"

static cnu_magnitude_t alpha_shift(cnu_magnitude_t magnitude,
                                   cnu_iteration_t t)
{
    if (t >= QEC_MAGNITUDE_BITS) {
        return magnitude;
    }
    return magnitude - (magnitude >> t);
}

void cnu_hardware_int4(
    const cnu_message_t vnu_messages[CNU_DEGREE],
    cnu_bit_t sigma_i,
    cnu_iteration_t t,
    cnu_result_type *result)
{
#ifdef CNU_OPT
    // [pragma 5] INLINE: paste this function's body into the caller (no separate module,
    //            no start/done handshake; lets HLS optimise across the call boundary)
#pragma HLS INLINE
#endif
    cnu_bit_t sign_bits[CNU_DEGREE];
    cnu_magnitude_t magnitudes[CNU_DEGREE];
#ifdef CNU_OPT
    // [pragma 1] ARRAY_PARTITION: split each 6-element array into 6 separate registers,
    //            so all 6 elements can be read/written in the same clock cycle.
#pragma HLS ARRAY_PARTITION variable=sign_bits  type=complete
#pragma HLS ARRAY_PARTITION variable=magnitudes type=complete
#endif
    cnu_bit_t full_parity = sigma_i;
    cnu_magnitude_t min1 = QEC_MAX_MAGNITUDE;
    cnu_magnitude_t min2 = QEC_MAX_MAGNITUDE;

    for (int edge = 0; edge < CNU_DEGREE; ++edge) {
#ifdef CNU_OPT
        // [pragma 2] UNROLL: build 6 copies of the loop body side by side (one per edge)
        //            instead of one copy reused 6 times.
#pragma HLS UNROLL
#endif
        sign_bits[edge] = vnu_messages[edge] < 0;
        magnitudes[edge] = sign_bits[edge]
                               ? cnu_magnitude_t(-vnu_messages[edge])
                               : cnu_magnitude_t(vnu_messages[edge]);
        full_parity ^= sign_bits[edge];
    }

    for (int edge = 0; edge < CNU_DEGREE; ++edge) {
#ifdef CNU_OPT
        // [pragma 2] UNROLL: build 6 copies of the loop body side by side (one per edge)
        //            instead of one copy reused 6 times.
#pragma HLS UNROLL
#endif
        const cnu_magnitude_t magnitude = magnitudes[edge];
        if (magnitude < min1) {
            min2 = min1;
            min1 = magnitude;
        } else if (magnitude < min2) {
            min2 = magnitude;
        }
    }

    for (int edge = 0; edge < CNU_DEGREE; ++edge) {
#ifdef CNU_OPT
        // [pragma 2] UNROLL: build 6 copies of the loop body side by side (one per edge)
        //            instead of one copy reused 6 times.
#pragma HLS UNROLL
#endif
        result->signs_per_edge[edge] = full_parity ^ sign_bits[edge];
        result->selectors_per_edge[edge] = magnitudes[edge] == min1;
    }

    result->min1_scaled = alpha_shift(min1, t);
    result->min2_scaled = alpha_shift(min2, t);
}

void cnu_hls_top(
    const cnu_message_t vnu_messages[CNU_DEGREE],
    cnu_bit_t sigma_i,
    cnu_iteration_t t,
    cnu_result_type *result)
{
#ifdef CNU_OPT
    // [pragma 3] ARRAY_PARTITION on the top-level input: 6 separate input ports
    //            instead of one RAM-style port that delivers one element per cycle.
#pragma HLS ARRAY_PARTITION variable=vnu_messages type=complete
    // [pragma 4] PIPELINE II=1: the CNU may accept a new set of inputs every clock cycle.
#pragma HLS PIPELINE II=1
#endif
    cnu_hardware_int4(vnu_messages, sigma_i, t, result);
}

int cnu_hardware_int4(
    const int vnu_messages[CNU_DEGREE],
    int degree,
    int sigma_i,
    int t,
    cnu_result_type *result)
{
    if (vnu_messages == 0 || result == 0 || degree != CNU_DEGREE || t < 0) {
        return -1;
    }

    cnu_message_t narrowed_messages[CNU_DEGREE];
#ifdef CNU_OPT
#pragma HLS INLINE
#pragma HLS ARRAY_PARTITION variable=narrowed_messages type=complete
#endif
    for (int edge = 0; edge < CNU_DEGREE; ++edge) {
#ifdef CNU_OPT
#pragma HLS UNROLL
#endif
        narrowed_messages[edge] = vnu_messages[edge];
    }

    cnu_hardware_int4(narrowed_messages, cnu_bit_t(sigma_i),
                      cnu_iteration_t(t), result);
    return 0;
}