# Generates 4 .mem files for DMem-BP top-level connectivity tables.
# Run once, drop outputs into the Vivado sim directory.

import numpy as np
from matrix_generator import get_H_x

H_x = get_H_x()
NUM_CHECK = 72
NUM_VAR   = 144
CHECK_DEG = 6
VAR_DEG   = 3

assert H_x.shape == (NUM_CHECK, NUM_VAR)
assert np.all(H_x.sum(axis=1) == CHECK_DEG)
assert np.all(H_x.sum(axis=0) == VAR_DEG)

# Neighbor lists (same convention as iterations_dmem_bp.py)
check_node_neighbor = [
    [j for j in range(NUM_VAR) if H_x[i][j] == 1]
    for i in range(NUM_CHECK)
]
variable_node_neighbor = [
    [i for i in range(NUM_CHECK) if H_x[i][j] == 1]
    for j in range(NUM_VAR)
]

# Port convention:
#   CNU i's port p connects to VNU check_node_neighbor[i][p]
#   VNU j's port k connects to CNU variable_node_neighbor[j][k]

# Table 1: for each (j, k), which CNU does VNU j's port k feed
with open("vnu_to_cnu_idx.mem", "w") as f:
    for j in range(NUM_VAR):
        for k in range(VAR_DEG):
            cnu_idx = variable_node_neighbor[j][k]
            f.write(f"{cnu_idx:02x}\n")

# Table 2: for each (j, k), which port of that CNU it lands on
with open("vnu_to_cnu_port.mem", "w") as f:
    for j in range(NUM_VAR):
        for k in range(VAR_DEG):
            cnu_idx = variable_node_neighbor[j][k]
            port = check_node_neighbor[cnu_idx].index(j)
            f.write(f"{port:01x}\n")

# Table 3: for each (i, p), which VNU does CNU i's port p feed
with open("cnu_to_vnu_idx.mem", "w") as f:
    for i in range(NUM_CHECK):
        for p in range(CHECK_DEG):
            vnu_idx = check_node_neighbor[i][p]
            f.write(f"{vnu_idx:02x}\n")

# Table 4: for each (i, p), which port of that VNU it lands on
with open("cnu_to_vnu_port.mem", "w") as f:
    for i in range(NUM_CHECK):
        for p in range(CHECK_DEG):
            vnu_idx = check_node_neighbor[i][p]
            port = variable_node_neighbor[vnu_idx].index(i)
            f.write(f"{port:01x}\n")

print("Generated 4 .mem files:")
print(f"  vnu_to_cnu_idx.mem  ({NUM_VAR * VAR_DEG} entries)")
print(f"  vnu_to_cnu_port.mem ({NUM_VAR * VAR_DEG} entries)")
print(f"  cnu_to_vnu_idx.mem  ({NUM_CHECK * CHECK_DEG} entries)")
print(f"  cnu_to_vnu_port.mem ({NUM_CHECK * CHECK_DEG} entries)")