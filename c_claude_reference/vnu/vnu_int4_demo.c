/* vnu_int4_demo.c
 *
 * Port of the test block at the bottom of vnu_python/vnu_int4.py.
 *
 * miu = [-2, -1]
 * marginal = 3 + (-2) + (-1) = 0
 * vnu_message = [0-(-2), 0-(-1)] = [2, 1]
 * hard_decision = 1  (<= 0)
 */

#include <stdio.h>

#include "vnu_int4.h"

int main(void)
{
    /* {'sign', 'selector', 'min1_scaled', 'min2_scaled'} */
    const cnu_message_t cnu_msgs_1[2] = {
        { 1, 0, 2, 4 },
        { 1, 0, 1, 3 }
    };
    vnu_result_t result;
    int i;

    if (vnu_hardware_int4(cnu_msgs_1, 2, /* lambda_j */ 3, &result) != 0) {
        fprintf(stderr, "vnu_hardware_int4: invalid arguments\n");
        return 1;
    }

    printf("{'vnu_messages': [");
    for (i = 0; i < result.degree; i++) {
        printf("%d%s", result.vnu_messages[i], (i + 1 < result.degree) ? ", " : "");
    }
    printf("], 'marginal': %d, 'hard_decision': %d}\n",
           result.marginal, result.hard_decision);

    return 0;
}
