#if !defined(SYNTHESIS) && !defined(__SYNTHESIS__)

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "vnu_int4.h"

static std::vector<std::string> split_csv_row(const std::string &row)
{
    std::vector<std::string> fields;
    std::stringstream stream(row);
    std::string field;
    while (std::getline(stream, field, ',')) {
        fields.push_back(field);
    }
    return fields;
}

static int run_csv_vectors(const char *path)
{
    std::ifstream input(path);
    if (!input) {
        std::fprintf(stderr, "Could not open VNU vectors: %s\n", path);
        return 1;
    }

    std::string row;
    std::getline(input, row);
    int cases = 0;
    int failures = 0;

    while (std::getline(input, row)) {
        if (row.empty()) {
            continue;
        }
        const std::vector<std::string> f = split_csv_row(row);
        if (f.size() != 20) {
            std::fprintf(stderr, "Malformed CSV row %d: got %zu fields\n",
                         cases + 2, f.size());
            return 1;
        }

        cnu_to_vnu_message_t inputs[VNU_DEGREE];
        for (int edge = 0; edge < VNU_DEGREE; ++edge) {
            const int base = 3 + edge * 4;
            inputs[edge].sign = std::atoi(f[base].c_str());
            inputs[edge].selector = std::atoi(f[base + 1].c_str());
            inputs[edge].min1_scaled = std::atoi(f[base + 2].c_str());
            inputs[edge].min2_scaled = std::atoi(f[base + 3].c_str());
        }

        const int lambda = std::atoi(f[2].c_str());
        vnu_state_type state = {qec_lfsr_t(1), qec_beta_t(7),
                                qec_message_t(lambda)};
        vnu_result_type result;
        vnu_hls_top(inputs, qec_magnitude_t(lambda), qec_bit_t(1),
                    qec_bit_t(0), &state, &result);

        for (int edge = 0; edge < VNU_DEGREE; ++edge) {
            const int expected = std::atoi(f[15 + edge].c_str());
            if (static_cast<int>(result.vnu_messages[edge]) != expected) {
                std::printf("FAIL case %d edge %d: got %d expected %d\n",
                            cases, edge,
                            static_cast<int>(result.vnu_messages[edge]), expected);
                ++failures;
            }
        }

        const int expected_marginal = std::atoi(f[18].c_str());
        const int expected_hard_decision = std::atoi(f[19].c_str());
        if (static_cast<int>(result.marginal) != expected_marginal ||
            static_cast<int>(result.hard_decision) != expected_hard_decision) {
            std::printf("FAIL case %d result: marginal=%d/%d hard=%d/%d\n",
                        cases, static_cast<int>(result.marginal),
                        expected_marginal,
                        static_cast<int>(result.hard_decision),
                        expected_hard_decision);
            ++failures;
        }
        ++cases;
    }

    if (cases != 344) {
        std::printf("FAIL vector count: got %d expected 344\n", cases);
        ++failures;
    }
    std::printf("VNU CSV vectors: %d cases, %d failure(s)\n", cases, failures);
    return failures;
}

static int run_stateful_vectors()
{
    cnu_to_vnu_message_t zeros[VNU_DEGREE] = {};
    vnu_result_type result;
    int failures = 0;

    for (int edge = 0; edge < VNU_DEGREE; ++edge) {
        zeros[edge].sign = 0;
        zeros[edge].selector = 0;
        zeros[edge].min1_scaled = 0;
        zeros[edge].min2_scaled = 0;
    }

    vnu_state_type state = {qec_lfsr_t(0x1234ABCDu), qec_beta_t(7),
                            qec_message_t(-15)};
    vnu_hls_top(zeros, qec_magnitude_t(15), qec_bit_t(0), qec_bit_t(0),
                &state, &result);
    if (static_cast<int>(result.marginal) != 7 ||
        static_cast<int>(state.M_reg) != 7) {
        std::printf("FAIL retained-beta state update: marginal=%d M_reg=%d\n",
                    static_cast<int>(result.marginal),
                    static_cast<int>(state.M_reg));
        ++failures;
    }

    state.M_reg = 4;
    vnu_hls_top(zeros, qec_magnitude_t(8), qec_bit_t(0), qec_bit_t(1),
                &state, &result);
    if (static_cast<unsigned>(state.beta_int) != 3u ||
        static_cast<uint32_t>(state.lfsr) != 0x91A55E68u ||
        static_cast<int>(result.marginal) != 6) {
        std::printf("FAIL new-leg update: beta=%u lfsr=%08X marginal=%d\n",
                    static_cast<unsigned>(state.beta_int),
                    static_cast<uint32_t>(state.lfsr),
                    static_cast<int>(result.marginal));
        ++failures;
    }

    vnu_hls_top(zeros, qec_magnitude_t(8), qec_bit_t(0), qec_bit_t(0),
                &state, &result);
    if (static_cast<int>(result.marginal) != 8 ||
        static_cast<int>(state.M_reg) != 8) {
        std::printf("FAIL consecutive state update: marginal=%d M_reg=%d\n",
                    static_cast<int>(result.marginal),
                    static_cast<int>(state.M_reg));
        ++failures;
    }

    std::printf("VNU stateful vectors: %d failure(s)\n", failures);
    return failures;
}

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "vnu_test_vectors_int4.csv";
    const int failures = run_csv_vectors(path) + run_stateful_vectors();
    return failures == 0 ? 0 : 1;
}

#endif
