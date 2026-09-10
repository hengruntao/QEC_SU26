#include "dmem_bp.h"


int mem_strength_scale_factor = 8;  // the 8 in Int4.2.8
int num_shift = 3;                  // /8 = right shift by 3
float gamma_0 = 0.125;              // memory strength; value from FPGA paper, fig7
int beta_int = 7;                   // β_int = ⌊β·M⌉ = round(0.875 * 8)
                                    // β = β_int / M ... 0.875 = 7/8
int gamma_int = 1;                  // γ_int = ⌊γ·M⌉ = round(0.125 * 8)
                                    // γ = γ_int / M ... 0.125 = 1/8

/*
This is used for the bias update for DMem-BP

# From FPGA paper (optimization of multiplication)
# We further reduce the logic requirements by simplifying the multiplication:
# Instead of implementing a full multiplier for µ_int β_int,
# we expand each bit of the bitwise representation of µ_int to β_int, shift right by m places,
# then null all effective factional bits before summing resulting values for the total result.
*/


int memory_strength_mult (int v, int coeff) {
    // define sign, so later can use the abs value
    int sign = (v < 0) ? -1:1;
    int abs_v = (v < 0) ? -v:v;
    int sum_val = 0;
    int value = 0;
    int k =0;   // k is the bit position, initialize to 0 (LSB)
    while (abs_v > 0){ 
        if(abs_v & 1){ // if the kth bit is 1
            value = 1 << k; // decimal value of the kth bit (2^k)
            value = value * coeff;  // value * coeff ... (beta_int OR gamma_int)
            sum_val += value >> num_shift;  // value / 8
        }
        abs_v = abs_v >> 1; // get rid of the LSB, and get ready for the next iteration
        k++;
    }

    return sign * sum_val;
}



/*
    In certain parts, need to use matrix multiplication. This can be done using an XOR tree
    for all values being 0/1. This helper function implements this XOR tree to help with optimization for FPGA

    out[i] = (M · v) mod 2。M is a flat, row-major 0/1 matrix
*/
static void xor_for_matrix_mult(const uint8_t *M, int rows, int cols,
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



int decode(const int *error, int beta_int, int gamma_int,
           int lambda_0_int, int max_iter,
           int *e_hat_out, int *iters_out, int *converged_out){
    /*
    ---- define check matrix ----
        see check_matrix_generator_for_c.py for .get_H_x() & .get_H_z()
    */
    int num_check_node = H_X_ROWS;
    int num_variable_node = H_X_COLS;

    /*
    ---- get check node's neighbor list ----
    */
    int cn_neighbor[H_X_ROWS][6];
    int i, j, k;
    int count;
    for (i = 0; i < num_check_node; i++){
        count = 0;
        for (j = 0; j < num_variable_node; j++){
            if (h_x[i * H_X_COLS + j]) cn_neighbor[i][count++] = j;
        }
    }
    /*
    ---- get variable node's neighbor list ----
    */
    int vn_neighbor[H_X_COLS][3];
    for (i = 0; i < num_variable_node; i++){
        count = 0;
        for (j = 0; j < num_check_node; j++){
            if (h_x[j * H_X_COLS + i]) vn_neighbor[i][count] = j;
        }
    }

    /*
    ---- initializing vnu_message for first iteration ----
    */
    int syndrome[H_X_ROWS];
    xor_for_matrix_mult(h_x, H_X_ROWS, H_X_COLS, error, syndrome);
    int error_prior[num_variable_node];  // Λ_j(t), will be updated every iteration. initialized to Λ_j(0)
    for (i = 0; i < num_variable_node; i++) {
        error_prior[i] = lambda_0_int;
    }   

    // vnu_message stores the message from vnu_i to all of its neighbors
    // vnu_message is a 2D array
    int vnu_message[144][3];

    for (i = 0; i < num_variable_node; i++){
        for (j = 0; j < 3; j++){
            vnu_message[i][j] = lambda_0_int;
        }
    }

    // iteration begins
    int t, e_hat[144], converged;
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
        int cnu_inputs[72][6];
        int idx;
        for (i = 0; i < num_check_node; i++){
            idx = 0;
            for (j = 0; j < num_variable_node; j++){
                for (k = 0; k < 3; k++){
                    if (vn_neighbor[j][k] == i){
                        cnu_inputs[i][idx] = vnu_message[j][k];
                        idx++;
                    }
                }
            }
        }

        /* 2. ---- CNU processing ---- */
        cnu_result_type cnu_results[72];
        for (i = 0; i < num_check_node; i++){
            cnu_hardware_int4(cnu_inputs[i], 6, syndrome[i], t, &cnu_results[i]);
        }
        
        /* 3. ---- CNU output to VNU input ---- */
        cnu_message_type vnu_inputs[144][3];
        for (i = 0; i < num_variable_node; i++){
            for (j = 0; j < 3; j++){
                int idx_of_cnu = vn_neighbor[i][j]; // which cnu is connected to vnu_i
                int idx_of_vnu;
                for (k = 0; k < 6; k++){
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
        vnu_result_type vnu_results[144];
        for (i = 0; i < num_variable_node; i++){
            vnu_hardware_int4(vnu_inputs[i], 3, error_prior[i], &vnu_results[i]);
        }

        /* ---- Convergence check ---- */
        
        // extract hard decisions from VNU, and computes estimated error vector e_hat (array of HDs)
        for (i = 0; i < num_variable_node; i++){
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

        /* ---- For DMem-BP: error_prior update  Λ_j(t) = (1-γ)·Λ_j(0) + γ·M_j(t-1) ---- */
        for (i = 0; i < num_variable_node; i++){
            error_prior[i] = memory_strength_mult(lambda_0_int, beta_int) + memory_strength_mult(vnu_results[i].marginal, gamma_int);
        }

    }

    return 0;
}