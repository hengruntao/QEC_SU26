#ifndef CNU_INT4_H
#define CNU_INT4_H

#include "../int4_max_val.h"

#define CNU_DEGREE 6
#define CNU_MAX_DEG CNU_DEGREE

typedef qec_bit_t cnu_bit_t;
typedef qec_message_t cnu_message_t;
typedef qec_magnitude_t cnu_magnitude_t;
typedef bp_iteration_t cnu_iteration_t;

typedef struct {
    cnu_magnitude_t min1_scaled;
    cnu_magnitude_t min2_scaled;
    cnu_bit_t signs_per_edge[CNU_DEGREE];
    cnu_bit_t selectors_per_edge[CNU_DEGREE];
} cnu_result_type;

void cnu_hardware_int4(
    const cnu_message_t vnu_messages[CNU_DEGREE],
    cnu_bit_t sigma_i,
    cnu_iteration_t t,
    cnu_result_type *result);

// Compatibility entry point for the not-yet-converted DMem-BP caller.
int cnu_hardware_int4(
    const int vnu_messages[CNU_DEGREE],
    int degree,
    int sigma_i,
    int t,
    cnu_result_type *result);

#endif
