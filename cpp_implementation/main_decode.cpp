#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "integrated/dmem_bp.h"

#define MAX_ITER 60

/* Λ_0 = min(round(log((1-p)/p) * 2), 15)      ← 和 Python 同一个公式
   p = 0.10 -> round(4.394) = 4
   p = 0.01 -> round(9.190) = 9                                        */
#define LAMBDA_P10 4
#define LAMBDA_P01 9

/* (M · v) mod 2。dmem_bp.c 里那个是 static(私有),这里自带一份 */
static void gf2_matvec(const uint8_t *M, int rows, int cols,
                       const int *v, int *out)
{
    int i, j;
    for (i = 0; i < rows; i++){
        int acc = 0;
        for (j = 0; j < cols; j++) if (M[i * cols + j]) acc ^= (v[j] & 1);
        out[i] = acc;
    }
}

static int weight(const int *v, int n){
    int i, s = 0;
    for (i = 0; i < n; i++) s += v[i];
    return s;
}

static void print_support(const char *label, const int *v, int n){
    int i, first = 1;
    printf("    %-18s w=%-3d {", label, weight(v, n));
    for (i = 0; i < n; i++) if (v[i]) { printf("%s%d", first ? "" : ",", i); first = 0; }
    printf("}\n");
}

/* 跑一次 decode,返回 decode_success。verbose=0 时只算不打印 */
static int run_case(const int *error, int beta_int,
                    int lambda_0, int verbose)
{
    int e_hat[H_X_COLS], residual[H_X_COLS];
    int syndrome[H_X_ROWS], logical[A_X_ROWS];
    int iters = -1, converged = -1, i, logical_ok = 1;

    decode(error, beta_int, lambda_0, MAX_ITER, e_hat, &iters, &converged);

    for (i = 0; i < H_X_COLS; i++) residual[i] = error[i] ^ e_hat[i];
    gf2_matvec(a_x, A_X_ROWS, A_X_COLS, residual, logical);
    for (i = 0; i < A_X_ROWS; i++) if (logical[i]) logical_ok = 0;

    if (verbose){
        gf2_matvec(h_x, H_X_ROWS, H_X_COLS, error, syndrome);
        print_support("error",      error,    H_X_COLS);
        print_support("syndrome",   syndrome, H_X_ROWS);
        print_support("e_hat",      e_hat,    H_X_COLS);
        print_support("residual",   residual, H_X_COLS);
        printf("    iters=%-3d converged=%d  logical_ok=%d   -> %s\n",
               iters, converged, logical_ok,
               (converged && logical_ok) ? "SUCCESS" : "FAIL");
    }
    return converged && logical_ok;
}

static void set_error(int *e, const int *pos, int npos){
    int i;
    memset(e, 0, H_X_COLS * sizeof(int));
    for (i = 0; i < npos; i++) e[pos[i]] = 1;
}

/* 自带 LCG,不指望和 Python 的 Mersenne Twister 一致,只为 sweep 用 */
static uint32_t rng_state = 12345u;
static uint32_t rng_next(void){
    rng_state = rng_state * 1103515245u + 12345u;
    return (rng_state >> 16) & 0x7fffu;
}

static void sweep(const char *label, int permille, int lambda_0,
                  int beta_int, int trials)
{
    int e[H_X_COLS];
    int i, j, ok = 0, w_total = 0;
    rng_state = 12345u;
    for (i = 0; i < trials; i++){
        int w = 0;
        for (j = 0; j < H_X_COLS; j++){
            e[j] = (rng_next() % 1000 < (uint32_t)permille) ? 1 : 0;
            w += e[j];
        }
        w_total += w;
        ok += run_case(e, beta_int, lambda_0, 0);
    }
    printf("  %-28s success %3d/%3d   avg error weight %.1f\n",
           label, ok, trials, (double)w_total / trials);
}

int main(void){
    int e[H_X_COLS];
    const int p1[] = {0};
    const int p2[] = {7};
    const int p3[] = {100};
    const int p4[] = {0, 73};
    const int p5[] = {3, 40, 118};
    const int p6[] = {1, 2, 3, 4, 5};

    /* ---- A. 确定性低权重 case:这些必须全过 ---- */
    printf("=== A. deterministic low-weight (beta=7, gamma=1, DMem-BP) ===\n");
    printf("\n  [w=0] no error\n");
    memset(e, 0, sizeof e);            run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=1] VN 0\n");
    set_error(e, p1, 1);               run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=1] VN 7\n");
    set_error(e, p2, 1);               run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=1] VN 100\n");
    set_error(e, p3, 1);               run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=2] VN 0, 73\n");
    set_error(e, p4, 2);               run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=3] VN 3, 40, 118\n");
    set_error(e, p5, 3);               run_case(e, 7, LAMBDA_P10, 1);
    printf("\n  [w=5] VN 1..5 (clustered)\n");
    set_error(e, p6, 5);               run_case(e, 7, LAMBDA_P10, 1);

    /* ---- B. 全 144 个 weight-1 case ---- */
    printf("\n=== B. all 144 weight-1 errors ===\n");
    {
        int i, ok = 0, bad[16], nbad = 0;
        for (i = 0; i < H_X_COLS; i++){
            memset(e, 0, sizeof e);
            e[i] = 1;
            if (run_case(e, 7, LAMBDA_P10, 0)) ok++;
            else if (nbad < 16) bad[nbad++] = i;
        }
        printf("  success %d/144\n", ok);
        if (nbad){
            printf("  failing VNs:");
            for (i = 0; i < nbad; i++) printf(" %d", bad[i]);
            printf("%s\n", ok + nbad < H_X_COLS ? " (truncated)" : "");
        }
    }

    /* ---- C. 随机 sweep ---- */
    printf("\n=== C. random sweep (100 trials each) ===\n");
    sweep("p=0.01  BP      (8,0)",  10, LAMBDA_P01, 8, 100);
    sweep("p=0.01  DMem-BP (7,1)",  10, LAMBDA_P01, 7, 100);
    sweep("p=0.10  BP      (8,0)", 100, LAMBDA_P10, 8, 100);
    sweep("p=0.10  DMem-BP (7,1)", 100, LAMBDA_P10, 7, 100);

    return 0;
}