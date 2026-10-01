/* 前置检查:memory_strength_mult 单测 + neighbor list 自洽性 */
#include <stdio.h>
#include "./integrated/dmem_bp.h"

static int fails = 0;

static void check(const char *label, int got, int want){
    if (got != want){ printf("  FAIL  %-34s got %d, want %d\n", label, got, want); fails++; }
    else              printf("  ok    %-34s = %d\n", label, got);
}

/* ---------- 检查 1:memory_strength_mult ---------- */
static void test_mult(void){
    int v, id_ok = 1, zero_ok = 1;
    printf("[1] memory_strength_mult\n");
    check("mult(15, 7)",  memory_strength_mult( 15, 7),  11);
    check("mult( 8, 7)",  memory_strength_mult(  8, 7),   7);
    check("mult( 4, 7)",  memory_strength_mult(  4, 7),   3);
    check("mult( 2, 7)",  memory_strength_mult(  2, 7),   1);
    check("mult( 0, 7)",  memory_strength_mult(  0, 7),   0);
    check("mult(-15,7)",  memory_strength_mult(-15, 7), -11);
    check("mult(15, 1)",  memory_strength_mult( 15, 1),   1);

    /* coeff=8 必须是恒等,coeff=0 必须恒为 0
       —— 这是 "BP == DMem-BP(beta=8, gamma=0)" 的依据 */
    for (v = -15; v <= 15; v++){
        if (memory_strength_mult(v, 8) != v) id_ok   = 0;
        if (memory_strength_mult(v, 0) != 0) zero_ok = 0;
    }
    check("mult(v,8)==v  for v in [-15,15]", id_ok,   1);
    check("mult(v,0)==0  for v in [-15,15]", zero_ok, 1);
}

/* ---------- 检查 2:neighbor list ---------- */
static int cn_neighbor[H_X_ROWS][CN_DEGREE];
static int vn_neighbor[H_X_COLS][VN_DEGREE];

static void test_neighbors(void){
    int i, j, p, q, ones = 0, mono = 1, fwd = 1, bwd = 1, inH = 1;
    FILE *f;

    build_neighbor_list(cn_neighbor, vn_neighbor);
    printf("[2] neighbor lists\n");

    /* (a) H 里 1 的总数 = 边数 */
    for (i = 0; i < H_X_ROWS * H_X_COLS; i++) ones += h_x[i];
    check("nnz(H) == 72*6",  ones, H_X_ROWS * CN_DEGREE);
    check("nnz(H) == 144*3", ones, H_X_COLS * VN_DEGREE);

    /* (b) 每行严格递增 —— 少写/重复写会在这里暴露 */
    for (i = 0; i < H_X_ROWS; i++)
        for (p = 1; p < CN_DEGREE; p++)
            if (cn_neighbor[i][p] <= cn_neighbor[i][p-1]) mono = 0;
    for (i = 0; i < H_X_COLS; i++)
        for (p = 1; p < VN_DEGREE; p++)
            if (vn_neighbor[i][p] <= vn_neighbor[i][p-1]) mono = 0;
    check("both tables strictly increasing", mono, 1);

    /* (c) 表里每条边在 H 里必须是 1 */
    for (i = 0; i < H_X_ROWS; i++)
        for (p = 0; p < CN_DEGREE; p++){
            j = cn_neighbor[i][p];
            if (j < 0 || j >= H_X_COLS || !h_x[i * H_X_COLS + j]) inH = 0;
        }
    check("every table edge is 1 in H", inH, 1);

    /* (d) 两张表互为镜像 */
    for (i = 0; i < H_X_ROWS; i++)
        for (p = 0; p < CN_DEGREE; p++){
            int found = 0;
            j = cn_neighbor[i][p];
            if (j < 0 || j >= H_X_COLS) { fwd = 0; continue; }
            for (q = 0; q < VN_DEGREE; q++) if (vn_neighbor[j][q] == i) found = 1;
            if (!found) fwd = 0;
        }
    for (j = 0; j < H_X_COLS; j++)
        for (q = 0; q < VN_DEGREE; q++){
            int found = 0;
            i = vn_neighbor[j][q];
            if (i < 0 || i >= H_X_ROWS) { bwd = 0; continue; }
            for (p = 0; p < CN_DEGREE; p++) if (cn_neighbor[i][p] == j) found = 1;
            if (!found) bwd = 0;
        }
    check("CN edge -> present in VN table", fwd, 1);
    check("VN edge -> present in CN table", bwd, 1);

    /* (e) 全量导出,给 Step 3 做 diff */
    f = fopen("neighbors_c.txt", "w");
    for (i = 0; i < H_X_ROWS; i++){
        fprintf(f, "CN %d:", i);
        for (p = 0; p < CN_DEGREE; p++) fprintf(f, " %d", cn_neighbor[i][p]);
        fprintf(f, "\n");
    }
    for (j = 0; j < H_X_COLS; j++){
        fprintf(f, "VN %d:", j);
        for (q = 0; q < VN_DEGREE; q++) fprintf(f, " %d", vn_neighbor[j][q]);
        fprintf(f, "\n");
    }
    fclose(f);
    printf("  wrote neighbors_c.txt\n");
}

int main(void){
    test_mult();
    test_neighbors();
    printf("\n%s (%d failure%s)\n", fails ? "FAILED" : "ALL PASS",
           fails, fails == 1 ? "" : "s");
    return fails != 0;
}