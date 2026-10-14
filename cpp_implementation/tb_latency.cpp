/* tb_latency.cpp -- testbench for measuring decode_relay() cycles (Vitis HLS csim + cosim).
 *
 * Target build: RELAY_R 600, RELAY_S 5 (paper Fig. 7/8 parameters).
 * 6 fixed shots. Expected C-model results (g++, Step B + 8-bit LFSR, beta_int in [5,20], M = 16,
 * seeds = relay_lfsr_seeds.h with RELAY_LFSR_GLOBAL_SEED 0; same with and without the *_OPT flags):
 *   shot weight total_iters legs_used num_sol converged
 *     0     1          5         5        5       1
 *     1    10         18         5        5       1
 *     2    12         54         5        5       1
 *     3    11         26         5        5       1
 *     4    13        149         6        5       1
 *     5    14         27         5        5       1
 * (Before Step B -- beta_table input, 32-bit LFSR seed 1, M = 8 -- the same shots gave
 *  total_iters 5/21/62/91/152/236 and legs_used 5/5/5/6/6/8.)
 * Fixed inputs: lambda_0[j] = 9 for all j (p = 0.01). beta is no longer a decode_relay input:
 * leg 0 uses RELAY_BETA_LEG_0, later legs draw from the per-VNU LFSRs inside decode_relay.
 *
 * Usage:  tb <out.csv> <first_shot> <last_shot> [ref.csv]
 *   csim : tb csim.csv 0 5             -> reference results for all shots
 *   cosim: tb cosim_3.csv 3 3 csim.csv -> one shot, compared with the reference
 * Exit code 0 = no mismatch (cosim reports FAIL on a non-zero exit code).
 */
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "Relay_BP/relay_decoder.h"
#include "vnu/RNG.h"   // explicit, as in the Step A testbench (cosim experiment 2)

#if RELAY_R != 600 || RELAY_S != 5
#error "tb_latency.cpp expects RELAY_R 600 and RELAY_S 5 -- the expected numbers above are for that build"
#endif

#define NSHOTS 6
static const int shot_w[NSHOTS] = {1, 10, 12, 11, 13, 14};
static const int shot_pos[NSHOTS][14] = {
    {115},
    {94, 105, 123, 87, 96, 25, 142, 118, 59, 109},
    {64, 8, 84, 136, 61, 55, 11, 0, 5, 50, 88, 52},
    {101, 125, 80, 20, 11, 85, 105, 123, 130, 122, 21},
    {138, 81, 52, 96, 55, 59, 106, 31, 61, 25, 47, 122, 70},
    {41, 68, 142, 78, 51, 26, 53, 32, 98, 63, 117, 140, 81, 85},
};

struct row_t { int shot, w, iters, legs, nsol, conv; char ehat[40]; };

static void to_hex(e_hat_t v, char *buf) {          /* 144 bits -> 36 hex digits, MSB first */
    for (int d = 0; d < 36; ++d) {
        int v4 = 0;
        for (int b = 0; b < 4; ++b) v4 |= (int)v[(35 - d) * 4 + b] << b;
        buf[d] = "0123456789abcdef"[v4];
    }
    buf[36] = 0;
}

int main(int argc, char **argv) {
    if (argc < 4) { printf("usage: %s out.csv first last [ref.csv]\n", argv[0]); return 2; }
    int first = atoi(argv[2]), last = atoi(argv[3]);
    if (first < 0 || last >= NSHOTS || first > last) { printf("[tb] bad shot range\n"); return 2; }

    qec_magnitude_t lambda_0[H_X_COLS];
    for (int j = 0; j < H_X_COLS; ++j) lambda_0[j] = 9;

    FILE *fo = fopen(argv[1], "w");
    if (!fo) { printf("[tb] cannot open %s\n", argv[1]); return 2; }
    fprintf(fo, "shot,weight,total_iters,legs_used,num_sol,converged,ehat_hex\n");

    row_t res[NSHOTS];
    for (int s = first; s <= last; ++s) {
        int e[H_X_COLS] = {0};
        for (int k = 0; k < shot_w[s]; ++k) e[shot_pos[s][k]] = 1;
        e_hat_t ehat = 0; int iters = 0, nsol = 0, legs = 0;
        int conv = decode_relay(compute_syndrome(e), lambda_0, &ehat, &iters, &nsol, &legs);
        row_t &r = res[s];
        r.shot = s; r.w = shot_w[s]; r.iters = iters; r.legs = legs; r.nsol = nsol; r.conv = conv;
        to_hex(ehat, r.ehat);
        fprintf(fo, "%d,%d,%d,%d,%d,%d,%s\n", s, r.w, iters, legs, nsol, conv, r.ehat);
        printf("[tb] shot %d: weight=%d total_iters=%d legs_used=%d num_sol=%d converged=%d\n",
               s, r.w, iters, legs, nsol, conv);
    }
    fclose(fo);

    if (argc < 5) return 0;
    FILE *fr = fopen(argv[4], "r");
    if (!fr) { printf("[tb] cannot open reference %s\n", argv[4]); return 1; }
    char line[256]; int mism = 0, found = 0;
    fgets(line, sizeof line, fr);                     /* header */
    while (fgets(line, sizeof line, fr)) {
        row_t q; memset(&q, 0, sizeof q);
        if (sscanf(line, "%d,%d,%d,%d,%d,%d,%39s", &q.shot, &q.w, &q.iters, &q.legs, &q.nsol, &q.conv, q.ehat) != 7) continue;
        if (q.shot < first || q.shot > last) continue;
        ++found;
        const row_t &r = res[q.shot];
        if (q.iters != r.iters || q.legs != r.legs || q.nsol != r.nsol || q.conv != r.conv || strcmp(q.ehat, r.ehat)) {
            ++mism; printf("[tb] MISMATCH shot %d\n", q.shot);
        }
    }
    fclose(fr);
    if (found != last - first + 1) { printf("[tb] reference is missing shots\n"); return 1; }
    printf("[tb] reference compare: %d mismatch(es)\n", mism);
    return mism ? 1 : 0;
}