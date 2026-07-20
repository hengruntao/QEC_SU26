import numpy as np
import math
from CNU import cnu_hardware
from VNU import vnu_hardware

# ---- define check matrix ----
H = np.array([
    [1, 1, 0],
    [0, 1, 1]
])

num_check_node, num_variable_node = H.shape

# ---- get neighbor list (which check node is connected to which variable node) ----
check_node_neighbor = []
for i in range (num_check_node):
    connected_variable_node = []
    for j in range (num_variable_node):
        if (H[i][j] == 1):
            connected_variable_node.append(j)
    check_node_neighbor.append(connected_variable_node)

# ---- get neighbor list (which variable node is connected to which check node) ----
variable_node_neighbor = []
for i in range (num_variable_node):
    connected_check_node = []
    for j in range (num_check_node):
        if (H[j][i] == 1):
            connected_check_node.append(j)
    variable_node_neighbor.append(connected_check_node)

# ---- test check matrix ----
error = [0, 1, 0]
syndrom = H @ error
p = 0.1
error_prior = [np.log((1-p)/p)] * num_variable_node

lambdas_for_all_check_nodes = []
for k in range (num_check_node):
    lambdas_for_each_check_node = []
    for t in check_node_neighbor[k]:    # k^th check node is connected to t^th variable node
        lambdas_for_each_check_node.append(error_prior[t])
    lambdas_for_all_check_nodes.append(lambdas_for_each_check_node)

# ---- CNU phase ----
# first iteration. t = 1 & v = lambda
t = 1
alpha = 1 - 2 ** (-t)
cnu_results = []
for ii in range (num_check_node):
    single_cnu_results = cnu_hardware(lambdas_for_all_check_nodes[ii], syndrom[ii], alpha)
    cnu_results.append(single_cnu_results)

# ---- CNU output to VNU input ----
vnu_inputs = []
# print("vn neighbor: ", variable_node_neighbor)
# print("cn neighbor: ", check_node_neighbor)
for jj in range (num_variable_node):    # jj遍历所有variable node (也就是H的所有column)
    message_for_vnu_jj = []
    for neighbor_cn_of_vn in variable_node_neighbor[jj]:    # 遍历第jj个variable node的所有neighboring check node
        vn_idx_in_neighbor_cn = check_node_neighbor[neighbor_cn_of_vn].index(jj)
        # check_node_neighbor[neighbor_cn_of_vn]提取出当前找到的check node的所有neighboring variable node
        # .index[jj]寻找当前第jj个variable node在这个check node的neighboring variabl node中的index
        message_for_vnu_jj_from_single_cn = {
            "min1_scaled": cnu_results[neighbor_cn_of_vn]["min1_scaled"],
            "min2_scaled": cnu_results[neighbor_cn_of_vn]["min2_scaled"],
            "sign": cnu_results[neighbor_cn_of_vn]["signs"][vn_idx_in_neighbor_cn],
            "selector": cnu_results[neighbor_cn_of_vn]["selectors"][vn_idx_in_neighbor_cn]
        }
        message_for_vnu_jj.append(message_for_vnu_jj_from_single_cn)
    vnu_inputs.append(message_for_vnu_jj)

        #大概是这样的分层
        # vnu_inputs = [
        #     [msg_for_vnu0_from_cnu0],                          # VNU 0 的消息
        #     [msg_for_vnu1_from_cnu0, msg_for_vnu1_from_cnu1],  # VNU 1 的消息
        #     [msg_for_vnu2_from_cnu1],                           # VNU 2 的消息
        # ]


# ---- VNU phase ----
vnu_results = []
for kk in range(num_variable_node):
    result = vnu_hardware(vnu_inputs[kk], error_prior[kk])
    vnu_results.append(result)


# ---- Convergence check ----
# 从 VNU 结果中提取 hard decisions，组成 estimated error vector ê
e_hat = []
for jj in range(num_variable_node):
    e_hat.append(vnu_results[jj]['hard_decision'])

# 验证 H·ê mod 2 == σ
syndrome_check = (H @ np.array(e_hat)) % 2
converged = np.array_equal(syndrome_check, syndrom)

print(f"e_hat:          {e_hat}")
print(f"H·ê mod 2:      {syndrome_check}")
print(f"syndrome:       {syndrom}")
print(f"converged:      {converged}")

# 期望:
# e_hat:     [0, 1, 0]
# H·ê mod 2: [1, 1]
# syndrome:  [1, 1]
# converged: True