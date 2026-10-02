/* run_vectors2.cpp -- harness: run YOUR decode_relay() against the reference vectors.
 *
 * Build (from cpp_implementation/):
 *   clang++ -O2 -I. -Irelay_tv2/include \
 *       relay_tv2/test/run_vectors2.cpp relay_tv2/src/relay_tv2_data.c \
 *       Relay_BP/relay_decoder.cpp DMem_BP/dmem_bp.cpp \
 *       vnu/vnu_int4.cpp vnu/RNG.cpp cnu/cnu_int4.cpp -o run_vectors2
 *
 * Run:
 *   ./run_vectors2                    # auto-picks the config matching your #defines
 *   ./run_vectors2 paper_R600_S5      # force a config by name
 *   ./run_vectors2 hw_R8_S5 --csv out.csv
 *   ./run_vectors2 --list
 *
 * The harness never reads your decoder's internals; it only calls decode_relay().
 */
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <string>

#include "relay_tv2.h"
#include "Relay_BP/relay_decoder.h"   /* brings in code_matrices.h via dmem_bp.h */

/* ------------------------------------------------------------------ adapter */
/* The only place that knows your decoder's signature.  Edit here if it changes. */
struct dut_out {
    int converged;
    int iterations;
    int legs_used;
    int num_sol;
    std::vector<int> ehat;   /* length TV2_N, 0/1 */
};

static dut_out tv_dut_decode(const int error_vec[TV2_N], int lambda0_int, unsigned seed)
{
    dut_out o;
    o.ehat.assign(TV2_N, 0);
    int iters = 0, nsol = 0, legs = 0;
    qec_magnitude_t lambda_0[TV2_N];
    for (int j = 0; j < TV2_N; j++) lambda_0[j] = lambda0_int;
    e_hat_t ehat_packed = 0;
    o.converged = decode_relay(compute_syndrome(error_vec), lambda_0, (uint32_t)seed,
                               &ehat_packed, &iters, &nsol, &legs);
    for (int j = 0; j < TV2_N; j++) o.ehat[j] = ehat_packed[j];
    o.iterations = iters;
    o.num_sol    = nsol;
    o.legs_used  = legs;
    return o;
}
/* -------------------------------------------------------------- end adapter */

static void expand(const short *sup, int w, int n, int *dst)
{
    for (int i = 0; i < n; i++) dst[i] = 0;
    for (int i = 0; i < w; i++) dst[sup[i]] = 1;
}

/* s = H_X . v  (mod 2), using the vectors' own copy of H_X */
static void syndrome_of(const int *v, int *s)
{
    for (int r = 0; r < TV2_M; r++) {
        int acc = 0;
        for (int c = 0; c < TV2_N; c++) acc ^= (tv2_H_X[r * TV2_N + c] & v[c]);
        s[r] = acc & 1;
    }
}

int main(int argc, char **argv)
{
    const char *want = 0;
    const char *csv  = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--list")) {
            for (int g = 0; g < TV2_NUM_CONFIGS; g++)
                printf("  %-16s T0=%d Tr=%d R=%d S=%d seed=%u\n",
                       tv2_configs[g].name, tv2_configs[g].t0, tv2_configs[g].tr,
                       tv2_configs[g].r, tv2_configs[g].s, tv2_configs[g].seed);
            return 0;
        } else if (!strcmp(argv[i], "--csv") && i + 1 < argc) {
            csv = argv[++i];
        } else {
            want = argv[i];
        }
    }

    /* ---- 0. H_X consistency: the vectors and your decoder must share a matrix */
    {
        long diff = 0;
        if (H_X_ROWS != TV2_M || H_X_COLS != TV2_N) {
            printf("FATAL: dimension mismatch, your H_X is %dx%d, vectors are %dx%d\n",
                   H_X_ROWS, H_X_COLS, TV2_M, TV2_N);
            return 2;
        }
        for (int r = 0; r < TV2_M; r++)
            for (int c = 0; c < TV2_N; c++)
                if ((int)H_X_AT(r, c) != (int)tv2_H_X[r * TV2_N + c]) diff++;
        if (diff) {
            printf("FATAL: your H_X differs from the vectors' H_X in %ld entries.\n"
                   "       Every result below would be meaningless. Regenerate one side.\n", diff);
            return 2;
        }
        printf("H_X consistency ......... OK (%dx%d identical)\n", TV2_M, TV2_N);
    }

    /* ---- 1. pick the config that matches your compile-time budget */
    int g = -1;
    if (want) {
        for (int i = 0; i < TV2_NUM_CONFIGS; i++)
            if (!strcmp(tv2_configs[i].name, want)) g = i;
        if (g < 0) { printf("FATAL: no config named '%s' (try --list)\n", want); return 2; }
    } else {
        for (int i = 0; i < TV2_NUM_CONFIGS; i++)
            if (tv2_configs[i].t0 == RELAY_T0 && tv2_configs[i].tr == RELAY_TR &&
                tv2_configs[i].r  == RELAY_R  && tv2_configs[i].s  == RELAY_S) g = i;
        if (g < 0) {
            printf("FATAL: your build is T0=%d Tr=%d R=%d S=%d; no vector set matches.\n"
                   "       Either recompile to match one of these, or name one explicitly:\n",
                   RELAY_T0, RELAY_TR, RELAY_R, RELAY_S);
            for (int i = 0; i < TV2_NUM_CONFIGS; i++)
                printf("         %-16s T0=%d Tr=%d R=%d S=%d\n", tv2_configs[i].name,
                       tv2_configs[i].t0, tv2_configs[i].tr, tv2_configs[i].r, tv2_configs[i].s);
            return 2;
        }
    }
    const tv2_config_type &cf = tv2_configs[g];
    printf("config .................. %s  (T0=%d Tr=%d R=%d S=%d)\n",
           cf.name, cf.t0, cf.tr, cf.r, cf.s);
    printf("your build .............. T0=%d Tr=%d R=%d S=%d\n\n",
           RELAY_T0, RELAY_TR, RELAY_R, RELAY_S);

    FILE *fp = csv ? fopen(csv, "w") : 0;
    if (fp) fprintf(fp, "case,p,lambda0,err_w,synd_w,ref_conv,ref_iters,ref_w,"
                        "dut_conv,dut_iters,dut_legs,dut_w,valid,exact\n");

    int n_run = 0;
    int false_pos = 0;          /* claims success but H.e_hat != s  -- the critical one */
    int conv_agree = 0;
    int dut_conv_only = 0, ref_conv_only = 0;
    int w_better = 0, w_equal = 0, w_worse = 0;
    int exact = 0;
    std::vector<std::string> fp_list, worse_list, refonly_list;

    int err_vec[TV2_N], ehat_ref[TV2_N], s_exp[TV2_M], s_got[TV2_M];

    for (int i = 0; i < TV2_NUM_CASES; i++) {
        const tv2_case_type   &tc = tv2_cases[i];
        const tv2_expect_type &ex = tv2_expect[g][i];

        expand(tc.err,  tc.err_w,  TV2_N, err_vec);
        expand(ex.ehat, ex.ehat_w, TV2_N, ehat_ref);
        expand(tc.synd, tc.synd_w, TV2_M, s_exp);

        dut_out o = tv_dut_decode(err_vec, tc.lambda0_int, cf.seed);
        n_run++;

        int dut_w = 0;
        for (int j = 0; j < TV2_N; j++) dut_w += o.ehat[j];
        syndrome_of(o.ehat.data(), s_got);
        int valid = 1;
        for (int r = 0; r < TV2_M; r++) if (s_got[r] != s_exp[r]) { valid = 0; break; }

        int is_exact = 1;
        for (int j = 0; j < TV2_N; j++) if (o.ehat[j] != ehat_ref[j]) { is_exact = 0; break; }

        if (o.converged && !valid) { false_pos++; if (fp_list.size() < 12) fp_list.push_back(tc.id); }
        if ((o.converged != 0) == (ex.converged != 0)) conv_agree++;
        else if (o.converged) dut_conv_only++;
        else { ref_conv_only++; if (refonly_list.size() < 12) refonly_list.push_back(tc.id); }

        if (o.converged && ex.converged) {
            if (is_exact) exact++;
            if (dut_w < ex.ehat_w) w_better++;
            else if (dut_w == ex.ehat_w) w_equal++;
            else { w_worse++; if (worse_list.size() < 12) worse_list.push_back(tc.id); }
        }

        if (fp) fprintf(fp, "%s,%g,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                        tc.id, tc.p, tc.lambda0_int, tc.err_w, tc.synd_w,
                        ex.converged, ex.iterations, ex.ehat_w,
                        o.converged, o.iterations, o.legs_used, dut_w, valid, is_exact);
    }
    if (fp) fclose(fp);

    printf("cases run ............................. %d\n", n_run);
    printf("FALSE POSITIVES (claimed success, H.e != s) %d      <-- must be 0\n", false_pos);
    printf("converged flag agrees with reference .. %d / %d\n", conv_agree, n_run);
    printf("   reference converged, yours did not . %d\n", ref_conv_only);
    printf("   yours converged, reference did not . %d\n", dut_conv_only);
    printf("solution weight (both converged) ...... better %d / equal %d / worse %d\n",
           w_better, w_equal, w_worse);
    printf("bit-identical e_hat (both converged) .. %d\n", exact);

    if (!fp_list.empty()) {
        printf("\nfalse-positive cases: ");
        for (size_t k = 0; k < fp_list.size(); k++) printf("%s ", fp_list[k].c_str());
        printf("\n");
    }
    if (!refonly_list.empty()) {
        printf("\nreference converged / you did not: ");
        for (size_t k = 0; k < refonly_list.size(); k++) printf("%s ", refonly_list[k].c_str());
        printf("\n");
    }
    if (!worse_list.empty()) {
        printf("\nheavier-than-reference solutions: ");
        for (size_t k = 0; k < worse_list.size(); k++) printf("%s ", worse_list[k].c_str());
        printf("\n");
    }
    if (csv) printf("\nper-case CSV written to %s\n", csv);

    return false_pos ? 1 : 0;
}
