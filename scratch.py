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
            print(f"regarding cnu{ii}, vnu{jj}'s neighbors are: {variable_node_neighbor[jj]}")
            index = variable_node_neighbor[jj].index(ii)    # the position of CNU_ii in the neighboring list of VNU_jj
            message_for_cnu_ii.append(vnu_message[jj][index])   # use the index to get the message from all VNUs to the specific CNU{ii}
            print(f"the message for cnu{ii} from vnu{jj} is: {message_for_cnu_ii}")
            
        cnu_inputs.append(message_for_cnu_ii)