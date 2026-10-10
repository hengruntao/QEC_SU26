#ifndef LFSR_BETA_TABLE_H
#define LFSR_BETA_TABLE_H

/* Testbench helper, NOT part of the HLS design.
   Records what the per-VNU LFSRs would have produced into a β table, so that
   decode_relay(..., beta_table, ...) reproduces the old seed/LFSR build bit-exactly:
     row 0          = beta_leg0 for every VN               (leg 0)
     row r (r >= 1) = r-th rng_beta_int() draw of VN j     (leg r)
   with the VN states seeded by rng_seed_all(seed), as the old decode_relay() did. */

#include "../vnu/RNG.h"

static inline void fill_beta_table_from_lfsr(qec_beta_t table[][QEC_NUM_VARIABLE_NODES],
                                             int num_rows,
                                             qec_lfsr_t seed,
                                             qec_beta_t beta_leg0)
{
    qec_lfsr_t states[QEC_NUM_VARIABLE_NODES];
    rng_seed_all(states, seed);
    for (int j = 0; j < QEC_NUM_VARIABLE_NODES; ++j) table[0][j] = beta_leg0;
    for (int r = 1; r < num_rows; ++r)
        for (int j = 0; j < QEC_NUM_VARIABLE_NODES; ++j)
            table[r][j] = rng_beta_int(&states[j]);
}

#endif