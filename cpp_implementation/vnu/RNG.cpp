#include "RNG.h"

/* ---- 单步:左移 Fibonacci LFSR ---- */
static uint32_t lfsr_step(uint32_t s){
    uint32_t fb = ((s >> 31) ^ (s >> 21) ^ (s >> 1) ^ s) & 1u;
    return (s << 1) | fb;
}

int rng_beta_int(uint32_t *state){
    uint32_t s = *state;
    int k;
    if (s == 0u) s = 1u;              /* 用 rng_seed_all 之后永远不会触发 */
    for (k = 0; k < 3; k++) s = lfsr_step(s);
    *state = s;
    return 3 + (int)(s & 0x7u);       /* 3 + {0..7} = [3,10] */
}

/* ----------------------------------------------------------------
   Leap-ahead。LFSR 单步是 GF(2) 上的线性映射,可以写成 32x32 矩阵。
   这里用"基向量的像"来存:A[i] = 映射作用在 e_i = (1<<i) 上的结果。
   于是 apply(A, s) = XOR_{ s 第 i 位为 1 } A[i]。
   矩阵的 k 次幂用快速幂算,32 次平方就够,常数时间。
   ---------------------------------------------------------------- */

static uint32_t lin_apply(const uint32_t A[32], uint32_t s){
    uint32_t r = 0u;
    int i;
    for (i = 0; i < 32; i++) if ((s >> i) & 1u) r ^= A[i];
    return r;
}

/* C = A ∘ B,即 C(s) = A(B(s));允许 C 与 A/B 重叠 */
static void lin_compose(uint32_t C[32], const uint32_t A[32], const uint32_t B[32]){
    uint32_t tmp[32];
    int i;
    for (i = 0; i < 32; i++) tmp[i] = lin_apply(A, B[i]);
    for (i = 0; i < 32; i++) C[i]   = tmp[i];
}

/* A = (单步映射)^k */
static void lfsr_jump_matrix(uint32_t A[32], uint32_t k){
    uint32_t base[32], res[32];
    int i;
    for (i = 0; i < 32; i++){
        base[i] = lfsr_step(1u << i);   /* 单步矩阵 */
        res[i]  = 1u << i;              /* 单位矩阵 */
    }
    while (k){
        if (k & 1u) lin_compose(res, base, res);
        lin_compose(base, base, base);
        k >>= 1;
    }
    for (i = 0; i < 32; i++) A[i] = res[i];
}

void rng_seed_all(uint32_t *states, int n, uint32_t global_seed){
    uint32_t jump[32];
    uint32_t s = (global_seed == 0u) ? 0x1234ABCDu : global_seed;
    uint32_t stride;
    int j;

    if (n <= 0) return;

    stride = 0xFFFFFFFFu / (uint32_t)n;   /* n=144 -> 29826161 步 */
    lfsr_jump_matrix(jump, stride);

    for (j = 0; j < n; j++){
        states[j] = s;
        s = lin_apply(jump, s);
    }
}