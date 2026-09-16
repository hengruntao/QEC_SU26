#include "../cnu/cnu_int4.h"
#include "../vnu/vnu_int4.h"
#include "../generated/code_matrices.h"
#include "stdint.h"
#define CN_DEGREE 6
#define VN_DEGREE 3

int memory_strength_mult (int v, int coeff);

void xor_for_matrix_mult(const uint8_t *M, int rows, int cols, const int *v, int *out);

int decode(const int *error, int beta_int, int lambda_0_int, int max_iter, int *e_hat_out, int *iters_out, int *converged_out);

void build_neighbor_list(int cn_neighbor[H_X_ROWS][CN_DEGREE], int vn_neighbor[H_X_COLS][VN_DEGREE]);