#if !defined(SYNTHESIS) && !defined(__SYNTHESIS__)

#include <cstdint>
#include <cstdio>

#include "RNG.h"

/* Expected values come from an independent model of the RTL rule (rtl/.../vnu.sv, M_LOG2 = 4):
     beta_int <= 5 + lfsr[3:0];   lfsr <= {lfsr[6:0], lfsr[7]^lfsr[5]^lfsr[4]^lfsr[3]};
   starting from 0xA5 (vnu.sv default LFSR_SEED). */
int main()
{
    static const unsigned expected_states[] = {
        0x4Au, 0x95u, 0x2Au, 0x54u, 0xA9u, 0x53u, 0xA7u, 0x4Eu
    };
    static const unsigned expected_betas[] = {10, 15, 10, 15, 9, 14, 8, 12};

    qec_lfsr_t state = 0xA5;
    int failures = 0;

    for (int i = 0; i < 8; ++i) {
        qec_lfsr_t next_state = 0;
        qec_beta_t beta = 0;
        rng_hls_top(state, &next_state, &beta);

        if (static_cast<unsigned>(next_state) != expected_states[i] ||
            static_cast<unsigned>(beta) != expected_betas[i]) {
            std::printf("FAIL sequence[%d]: state=%02X beta=%u\n", i,
                        static_cast<unsigned>(next_state),
                        static_cast<unsigned>(beta));
            ++failures;
        }
        state = next_state;
    }

    /* all-zero state: beta = 5 and the LFSR stays at 0 (same as the RTL);
       seeds must therefore be non-zero (gen_lfsr_seeds checks this) */
    qec_lfsr_t zero_next = 1;
    qec_beta_t zero_beta = 0;
    rng_hls_top(0, &zero_next, &zero_beta);
    if (static_cast<unsigned>(zero_next) != 0u ||
        static_cast<unsigned>(zero_beta) != 5u) {
        std::printf("FAIL zero state: state=%02X beta=%u\n",
                    static_cast<unsigned>(zero_next),
                    static_cast<unsigned>(zero_beta));
        ++failures;
    }

    /* period: a non-zero state returns to itself after exactly 255 steps */
    qec_lfsr_t s = 0xA5;
    int period = 0;
    do {
        qec_beta_t unused;
        rng_hls_top(s, &s, &unused);
        ++period;
    } while (s != 0xA5 && period < 1000);
    if (period != 255) {
        std::printf("FAIL period: %d (expected 255)\n", period);
        ++failures;
    }

    std::printf("RNG tests: %d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}

#endif