import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import numpy as np
import math
from test_vector.cnu_python.cnu_int4 import cnu_hardware_int4
from test_vector.vnu_python.vnu_int4 import vnu_hardware_int4
from matrix_generator import get_H_x, get_H_z, get_A_x, get_A_z


# ---- DMem-BP memory strength setup ----
# Λ_j(t) = (1−γ_j)*Λ_j(0) + γ_j*M_j(t−1)
# β=(1−γ) ∈ [0, 2]
# µ_int·γ → ⌊µ_int*γ_int/M⌉
# γ_int := ⌊γ·M⌉
# µ_int·γ → ⌊µ_int*(M−β_int)/M⌉
# β_int := ⌊β·M⌉
mem_strength_scale_factor = 8       # the 8 in Int4.2.8
num_shift = 3       # /8 = right shift by 3
gamma_0 = 0.125     # memory strength; value from FPGA paper, fig7
beta_int = 7        # β_int = ⌊β·M⌉ = round(0.875 * 8)
                    # β = β_int / M ... 0.875 = 7/8
gamma_int = 1       # γ_int = ⌊γ·M⌉ = round(0.125 * 8)
                    # γ = γ_int / M ... 0.125 = 1/8

# From FPGA paper (optimization of multiplication)
# We further reduce the logic requirements by simplifying the multiplication:
# Instead of implementing a full multiplier for µ_int β_int,
# we expand each bit of the bitwise representation of µ_int to β_int, shift right by m places,
# then null all effective factional bits before summing resulting values for the total result.

def memory_strength_mult(v, coeff):
    # define sign, so later can use the abs value
    if v < 0:
        sign = -1
    else:
        sign = 1

    abs_v = abs(v)
    sum_val = 0
    k = 0 # k is the bit position, initialize to 0
    while abs_v:    # while abs_v != 0 <=> still 1s in abs_v, so still need to do calculation
        if abs_v & 1:   # if the kth bit is 1
            value = 1 << k   # decimal value of the kth bit (2^k)
            value = value * coeff       # value * coeff ... (beta_int OR gamma_int)
            sum_val += value >> num_shift  # value / 8
        abs_v = abs_v >> 1  # get rid of the LSB, and get ready for the next iteration
        k+=1
    return sign * sum_val

# ---- define check matrix ----
    # see check_matrix_generator.py for .get_H_x() & .get_H_z()
H = get_H_x()

num_check_node, num_variable_node = H.shape

# ---- get check node's neighbor list (which check node is connected to which variable node) ----
check_node_neighbor = []
for i in range (num_check_node):
    connected_variable_node = []
    for j in range (num_variable_node):
        if (H[i][j] == 1):
            connected_variable_node.append(j)
    check_node_neighbor.append(connected_variable_node)

# ---- get variable node's neighbor list (which variable node is connected to which check node) ----
variable_node_neighbor = []
for i in range (num_variable_node):
    connected_check_node = []
    for j in range (num_check_node):
        if (H[j][i] == 1):
            connected_check_node.append(j)
    variable_node_neighbor.append(connected_check_node)

# ---- initializing vnu_message for first iteration ----
    # p is physical error rate
p = 0.1

    # use seed here for replication purpose
np.random.seed(21)

    # np.random.rand(num_variabl_node) generated an array of length 144, each element is some float within [0,1)
    # < p compares each float with physical error rate; if smaller return True, if larger return False. possibility of True = p
    # astype(int) transferrs boolean True/False to 1/0 --> generate error
error = (np.random.rand(num_variable_node) < p).astype(int)

syndrome = (H @ error) % 2

    # initial vnu_message = lambda_0
    # Int4.2.8 => max_value = 15; scaling factor = 2
lambda_0_float = np.log((1-p)/p)
lambda_0_int = min(round(lambda_0_float * 2), 15)     # Λ_j(0)
error_prior = [lambda_0_int] * num_variable_node    # Λ_j(t), will be updated every iteration. initialized to Λ_j(0)

    # vnu_message stores the message from vnu_i to all of its neighbors
    # vnu_message is a 2D array
vnu_message = []

for i in range(num_variable_node):
    degree_of_vnu_i = len(variable_node_neighbor[i])
    vnu_message.append([error_prior[i]] * degree_of_vnu_i);

# iteration begins
for t in range (1, 61):

    # ---- CNU phase ----
    # first iteration. t = 1 & v = lambda
    # other iterations. t = n & v = vnu_message

    # alpha = 1 - 2 ** (-t)
    # 1. ---- input for CNU ----
        # vnu_message gives the message of a "column"
        # but now needs messages of a "row" --> need to transform from the column message to row message
    cnu_inputs = []
    for ii in range (num_check_node):   # traverse all rows
        message_for_cnu_ii = [] # message for a single row (a single cnu)
        for jj in check_node_neighbor[ii]:  # CNU{ii} is connected to VNU{jj}
            index = variable_node_neighbor[jj].index(ii)    # the position of CNU_ii in the neighboring list of VNU_jj
            message_for_cnu_ii.append(vnu_message[jj][index])   # use the index to get the message from all VNUs to the specific CNU{ii}
        cnu_inputs.append(message_for_cnu_ii)

    # 2. ---- CNU processing ----
    cnu_results = []
    for ii in range (num_check_node):
        cnu_ii_results = cnu_hardware_int4(cnu_inputs[ii], syndrome[ii], t)
        cnu_results.append(cnu_ii_results)

    # ---- CNU output to VNU input ----
    vnu_inputs = []

    for jj in range (num_variable_node):    # traversing all VNU (columns of H)
        message_for_vnu_jj = []
        for neighbor_cn_of_vn in variable_node_neighbor[jj]:    # traverse all neighboring CNU of VNU{jj}
            vn_idx_in_neighbor_cn = check_node_neighbor[neighbor_cn_of_vn].index(jj)
        # check_node_neighbor[neighbor_cn_of_vn] gets all neighboring VNU of current CNU
        # .index[jj] finds the index (position) of VNU{jj} in current CNU's neighboring VNU nodes
            message_for_vnu_jj_from_single_cn = {
                "min1_scaled": cnu_results[neighbor_cn_of_vn]["min1_scaled"],
                "min2_scaled": cnu_results[neighbor_cn_of_vn]["min2_scaled"],
                "sign": cnu_results[neighbor_cn_of_vn]["signs"][vn_idx_in_neighbor_cn],
                "selector": cnu_results[neighbor_cn_of_vn]["selectors"][vn_idx_in_neighbor_cn]
            }
            message_for_vnu_jj.append(message_for_vnu_jj_from_single_cn)
        vnu_inputs.append(message_for_vnu_jj)

        # rough idea:
        # vnu_inputs = [
        #     [msg_for_vnu0_from_cnu0],                          # VNU 0 message
        #     [msg_for_vnu1_from_cnu0, msg_for_vnu1_from_cnu1],  # VNU 1 message
        #     [msg_for_vnu2_from_cnu1],                           # VNU 2 message
        # ]

    # ---- VNU phase ----
    vnu_results = []
    for kk in range(num_variable_node):
        result = vnu_hardware_int4(vnu_inputs[kk], error_prior[kk])
        vnu_results.append(result)

    # ---- update vnu_message ----
    for jj in range (num_variable_node):
        vnu_message[jj] = vnu_results[jj]["vnu_messages"]

    # ---- Convergence check ----
    # extract hard decisions from VNU, and computes estimated error vector e_hat (array of HDs)
    e_hat = []
    for jj in range(num_variable_node):
        e_hat.append(vnu_results[jj]['hard_decision'])
    e_hat = np.array(e_hat)
    
    # ---- check if H·ê mod 2 == σ ----
    syndrome_check = (H @ e_hat) % 2
    converged = np.array_equal(syndrome_check, syndrome)
        # IMPORTANT:
        # This "converged" ONLY means syndrome consistency.
        # NOT logical equivalence (Aê = Ae)

        # if converged, then break out from the loop; otherwise continue untill max_iter = 60
    if converged:
        break

    # ---- For DMem-BP: error_prior update  Λ_j(t) = (1-γ)·Λ_j(0) + γ·M_j(t-1) ----
    for jj in range(num_variable_node):
        error_prior[jj] = memory_strength_mult(lambda_0_int, beta_int) + memory_strength_mult(vnu_results[jj]["marginal"], gamma_int)

# iteration ends, now check for logical equivalence (Aê = Ae)
A_x = get_A_x()
new_e = e_hat ^ error
logical_action = (A_x @ new_e) % 2
logical_success = False
if (np.all(logical_action == 0)):
    logical_success = True

decode_success = (logical_success and converged)

print(f"check matrix:                           {H}")
print(f"physical error rate:                    {p}")
print(f"actual_error:                           {error}")
print(f"actual_error_sum:                       {sum(error)}")
print(f"e_hat (estimated_error):                {e_hat}")
print(f"e_hat_sum:                              {sum(e_hat)}")
print(f"H·ê mod 2:                              {syndrome_check}")
print(f"syndrome:                               {syndrome}")
print(f"syndrome_sum:                           {sum(syndrome)}")
print(f"t (# of iterations):                    {t}")
print(f"decode successful (logic consistent):   {decode_success}")
print(f"converged (syndrome consistent):        {converged}")