/* cnu_int4_demo.c
 *
 * Port of the `if __name__ == "__main__"` block at the bottom of
 * cnu_python/cnu_int4.py.  Prints the result in the same shape as the Python
 * dict so the two can be diffed directly.
 *
 * Expectation:
 *   min1_scaled = 1,  min2_scaled = 1
 *   signs     = [0, 1, 0, 1, 0, 1]
 *   selectors = [0, 0, 0, 0, 1, 0]
 */

#include <stdio.h>

#include "cnu_int4.h"

static void print_bit_list(const char *label, const int *bits, int len)
{
    int i;
    printf("%s[", label);
    for (i = 0; i < len; i++) {
        printf("%d%s", bits[i], (i + 1 < len) ? ", " : "");
    }
    printf("]");
}

int main(void)
{
    const int vnu_messages[6] = { 3, -5, 2, -7, 1, -4 };
    cnu_result_t result;

    if (cnu_hardware_int4(vnu_messages, 6, /* sigma_i */ 1, /* t */ 1, &result) != 0) {
        fprintf(stderr, "cnu_hardware_int4: invalid arguments\n");
        return 1;
    }

    printf("{'min1_scaled': %d, 'min2_scaled': %d, ",
           result.min1_scaled, result.min2_scaled);
    print_bit_list("'signs': ", result.signs, result.degree);
    printf(", ");
    print_bit_list("'selectors': ", result.selectors, result.degree);
    printf("}\n");

    return 0;
}
