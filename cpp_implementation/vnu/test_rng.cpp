#if !defined(SYNTHESIS) && !defined(__SYNTHESIS__)

#include <cstdint>
#include <cstdio>

#include "RNG.h"

int main()
{
    static const uint32_t expected_states[] = {
        0x91A55E68u,
        0x8D2AF340u,
        0x69579A01u,
        0x4ABCD00Cu,
        0x55E68067u,
        0xAF34033Eu,
        0x79A019F4u,
        0xCD00CFA4u
    };
    static const unsigned expected_betas[] = {3, 3, 4, 7, 10, 9, 7, 7};

    qec_lfsr_t state = 0x1234ABCDu;
    int failures = 0;

    for (int i = 0; i < 8; ++i) {
        qec_lfsr_t next_state = 0;
        qec_beta_t beta = 0;
        rng_hls_top(state, &next_state, &beta);

        if (static_cast<uint32_t>(next_state) != expected_states[i] ||
            static_cast<unsigned>(beta) != expected_betas[i]) {
            std::printf("FAIL sequence[%d]: state=%08X beta=%u\n", i,
                        static_cast<uint32_t>(next_state),
                        static_cast<unsigned>(beta));
            ++failures;
        }
        state = next_state;
    }

    qec_lfsr_t zero_next = 0;
    qec_beta_t zero_beta = 0;
    rng_hls_top(0, &zero_next, &zero_beta);
    if (static_cast<uint32_t>(zero_next) != 13u ||
        static_cast<unsigned>(zero_beta) != 8u) {
        std::printf("FAIL zero seed: state=%08X beta=%u\n",
                    static_cast<uint32_t>(zero_next),
                    static_cast<unsigned>(zero_beta));
        ++failures;
    }

    std::printf("RNG tests: %d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}

#endif
