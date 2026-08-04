import numpy as np
import math
from cnu_python import cnu_int4
from vnu_python import vnu_int4

# ---- define check matrix ----
H = np.array([
    [1, 1, 0],
    [0, 1, 1]
])

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
error = [0, 1, 0]
syndrom = H @ error
    # p is physical error rate
p = 0.1
    # initial vnu_message = lambda_0
error_prior = [np.log((1-p)/p)] * num_variable_node

vnu_message = []
    # vnu_message stores the message from vnu_i to all of its neighbors
    # vnu_message is a 2D array

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
        cnu_ii_results = cnu_int4(cnu_inputs[ii], syndrom[ii], t)
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
        result = vnu_int4(vnu_inputs[kk], error_prior[kk])
        vnu_results.append(result)

    # ---- update vnu_message ----
    for jj in range (num_variable_node):
        vnu_message[jj] = vnu_results[jj]["vnu_messages"]

    # ---- Convergence check ----
    # extract hard decisions from VNU, and computes estimated error vector e_hat
    e_hat = []
    for jj in range(num_variable_node):
        e_hat.append(vnu_results[jj]['hard_decision'])

    # ---- check if H·ê mod 2 == σ ----
    syndrome_check = (H @ np.array(e_hat)) % 2
    converged = np.array_equal(syndrome_check, syndrom)

        # if converged, then break out from the loop; otherwise continue untill max_iter = 60
    if converged:
        break

print(f"e_hat:          {e_hat}")
print(f"H·ê mod 2:      {syndrome_check}")
print(f"syndrome:       {syndrom}")
print(f"t:          {t}")
print(f"converged:      {converged}")

# Expectation:
# e_hat:     [0, 1, 0]
# H·ê mod 2: [1, 1]
# syndrome:  [1, 1]
# converged: True