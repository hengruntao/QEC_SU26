#include "dmem_bp.h"



// int mem_strength_scale_factor = 8;  // the 8 in Int4.2.8
                 // /8 = right shift by 3
// float gamma_0 = 0.125;              // memory strength; value from FPGA paper, fig7
// int beta_int = 7;                   // β_int = ⌊β·M⌉ = round(0.875 * 8)
//                                     // β = β_int / M ... 0.875 = 7/8
// int gamma_int = 1;                  // γ_int = ⌊γ·M⌉ = round(0.125 * 8)
//                                     // γ = γ_int / M ... 0.125 = 1/8




/*
    In certain parts, need to use matrix multiplication. This can be done using an XOR tree
    for all values being 0/1. This helper function implements this XOR tree to help with optimization for FPGA

    out[i] = (M · v) mod 2。M is a flat, row-major 0/1 matrix
*/
void xor_for_matrix_mult(const uint8_t *M, int rows, int cols,
                       const int *v, int *out)
{
    int i, j;
    for (i = 0; i < rows; i++) {
        int acc = 0;
        for (j = 0; j < cols; j++) {
            if (M[i * cols + j]) acc ^= (v[j] & 1);
        }
        out[i] = acc;
    }
}


/* ---- build neighbor list (wrap as a function, easier to debug) ---- */

void build_neighbor_list(int cn_neighbor[H_X_ROWS][CN_DEGREE], int vn_neighbor[H_X_COLS][VN_DEGREE]){
    int i, j, count;

    /* ---- get check node's neighbor list ---- */
    for (i = 0; i < H_X_ROWS; i++){
        count = 0;
        for (j = 0; j < H_X_COLS; j++){
            if (h_x[i * H_X_COLS + j]) cn_neighbor[i][count++] = j;
        }
    }
    /* ---- get variable node's neighbor list ---- */
    for (i = 0; i < H_X_COLS; i++){
        count = 0;
        for (j = 0; j < H_X_ROWS; j++){
            if (h_x[j * H_X_COLS + i]) vn_neighbor[i][count++] = j;
        }
    }
}

int decode(const int *error, int beta_int, int gamma_int,
           int lambda_0_int, int max_iter,
           int *e_hat_out, int *iters_out, int *converged_out){
    /*
    ---- define check matrix ----
        see check_matrix_generator_for_c.py for .get_H_x() & .get_H_z()
    */
    int i, j, k;
    /*
    ---- get check node & variable node's neighbor list ----
    */
    int cn_neighbor[H_X_ROWS][CN_DEGREE];
    int vn_neighbor[H_X_COLS][VN_DEGREE];
    build_neighbor_list(cn_neighbor, vn_neighbor);

    /*
    ---- initializing vnu_message for first iteration ----
    */
    int syndrome[H_X_ROWS];
    xor_for_matrix_mult(h_x, H_X_ROWS, H_X_COLS, error, syndrome);
    int error_prior[H_X_COLS];  // Λ_j(t), will be updated every iteration. initialized to Λ_j(0)
    for (i = 0; i < H_X_COLS; i++) {
        error_prior[i] = lambda_0_int;
    }   

    // vnu_message stores the message from vnu_i to all of its neighbors
    // vnu_message is a 2D array
    int vnu_message[H_X_COLS][VN_DEGREE];

    for (i = 0; i < H_X_COLS; i++){
        for (j = 0; j < VN_DEGREE; j++){
            vnu_message[i][j] = lambda_0_int;
        }
    }

    // iteration begins
    int t;
    int converged = 0;
    int e_hat[H_X_COLS];
    for (t = 1; t <= max_iter; t++){

        /*  
        ---- CNU phase ----
        first iteration. t = 1 & v = lambda
        other iterations. t = n & v = vnu_message

        alpha = 1 - 2 ** (-t)
        1. ---- input for CNU ----
           vnu_message gives the message of a "column"
           but now needs messages of a "row" --> need to transform from the column message to row message
        */
        int cnu_inputs[H_X_ROWS][CN_DEGREE];
        int idx;
        for (i = 0; i < H_X_ROWS; i++){
            idx = 0;
            for (j = 0; j < H_X_COLS; j++){
                for (k = 0; k < VN_DEGREE; k++){
                    if (vn_neighbor[j][k] == i){
                        cnu_inputs[i][idx] = vnu_message[j][k];
                        idx++;
                    }
                }
            }
        }

        /* 2. ---- CNU processing ---- */
        cnu_result_type cnu_results[H_X_ROWS];
        for (i = 0; i < H_X_ROWS; i++){
            cnu_hardware_int4(cnu_inputs[i], CN_DEGREE, syndrome[i], t, &cnu_results[i]);
        }
        
        /* 3. ---- CNU output to VNU input ---- */
        cnu_message_type vnu_inputs[H_X_COLS][VN_DEGREE];
        for (i = 0; i < H_X_COLS; i++){
            for (j = 0; j < VN_DEGREE; j++){
                int idx_of_cnu = vn_neighbor[i][j]; // which cnu is connected to vnu_i
                int idx_of_vnu = -1;
                for (k = 0; k < CN_DEGREE; k++){
                    if (cn_neighbor[idx_of_cnu][k] == i){
                        idx_of_vnu = k;
                    }
                }
                vnu_inputs[i][j].min1_scaled = cnu_results[idx_of_cnu].min1_scaled;
                vnu_inputs[i][j].min2_scaled = cnu_results[idx_of_cnu].min2_scaled;
                vnu_inputs[i][j].selector = cnu_results[idx_of_cnu].selectors_per_edge[idx_of_vnu];
                vnu_inputs[i][j].sign = cnu_results[idx_of_cnu].signs_per_edge[idx_of_vnu];
            }
        }

        /* ---- VNU phase ---- */
        vnu_result_type vnu_results[H_X_COLS];
        for (i = 0; i < H_X_COLS; i++){
            vnu_hardware_int4(vnu_inputs[i], VN_DEGREE, lambda_0_int, t, &vnu_results[i]);
        }

        /* ---- update vnu_message ---- */
        for (i = 0; i < H_X_COLS; i++){
            for (j = 0; j < VN_DEGREE; j++){
                vnu_message[i][j] = vnu_results[i].vnu_messages[j];
            }
        }

        /* ---- Convergence check ---- */
        
        // extract hard decisions from VNU, and computes estimated error vector e_hat (array of HDs)
        for (i = 0; i < H_X_COLS; i++){
            e_hat[i] = vnu_results[i].hard_decision;
        }

        // check if H·ê mod 2 == σ
        int syndrome_check[H_X_ROWS];
        xor_for_matrix_mult(h_x, H_X_ROWS, H_X_COLS, e_hat, syndrome_check);
        converged = 1;
        for (i = 0; i < H_X_ROWS; i++){
            if (syndrome[i] != syndrome_check[i]) converged = 0;
        }

        if (converged){
            break;
        }
    }

    /* ---- output ---- */
    *converged_out = converged;
    *iters_out = (converged) ? t : max_iter;
    for (i = 0; i < H_X_COLS; i++){
        e_hat_out[i] = e_hat[i];
    }

    return 0;
}