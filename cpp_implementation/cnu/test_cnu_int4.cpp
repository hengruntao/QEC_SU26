#if !defined(SYNTHESIS) && !defined(__SYNTHESIS__)

#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "cnu_int4.h"

static std::vector<std::string> split_csv_row(const std::string &row)
{
    std::vector<std::string> fields;
    std::string field;
    bool quoted = false;

    for (std::string::size_type i = 0; i < row.size(); ++i) {
        const char ch = row[i];
        if (ch == '"') {
            quoted = !quoted;
        } else if (ch == ',' && !quoted) {
            fields.push_back(field);
            field.clear();
        } else {
            field.push_back(ch);
        }
    }
    fields.push_back(field);
    return fields;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        std::cerr << "usage: test_cnu_int4 <cnu_test_vectors_int4.csv>\n";
        return 2;
    }

    std::ifstream input(argv[1]);
    if (!input) {
        std::cerr << "cannot open " << argv[1] << "\n";
        return 2;
    }

    std::string row;
    std::getline(input, row);

    int cases = 0;
    int failures = 0;
    while (std::getline(input, row)) {
        const std::vector<std::string> f = split_csv_row(row);
        if (f.size() != 24) {
            std::cerr << "malformed CSV row " << cases + 2 << "\n";
            return 2;
        }

        cnu_message_t messages[CNU_DEGREE];
        for (int edge = 0; edge < CNU_DEGREE; ++edge) {
            messages[edge] = std::stoi(f[2 + edge]);
        }

        cnu_result_type result;
        cnu_hardware_int4(messages,
                          cnu_bit_t(std::stoi(f[8])),
                          cnu_iteration_t(std::stoi(f[9])),
                          &result);

        bool pass = true;
        for (int edge = 0; edge < CNU_DEGREE; ++edge) {
            pass = pass && result.signs_per_edge[edge].to_uint() ==
                               static_cast<unsigned>(std::stoi(f[10 + 2 * edge]));
            pass = pass && result.selectors_per_edge[edge].to_uint() ==
                               static_cast<unsigned>(std::stoi(f[11 + 2 * edge]));
        }
        pass = pass && result.min1_scaled.to_uint() ==
                           static_cast<unsigned>(std::stoi(f[22]));
        pass = pass && result.min2_scaled.to_uint() ==
                           static_cast<unsigned>(std::stoi(f[23]));

        if (!pass) {
            std::cerr << "FAIL vector " << f[0] << ": " << f[1] << "\n";
            ++failures;
        }
        ++cases;
    }

    std::cout << "CNU vectors: " << cases << ", failures: " << failures << "\n";
    return failures == 0 ? 0 : 1;
}

#endif
