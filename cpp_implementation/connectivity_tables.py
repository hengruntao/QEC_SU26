"""
  cnu_to_vnu_idx [i][p] : CNU i 的 port p 连到哪个 VNU
  cnu_to_vnu_port[i][p] : 这条边在那个 VNU 上是第几号 port
  vnu_to_cnu_idx [j][k] : VNU j 的 port k 连到哪个 CNU
  vnu_to_cnu_port[j][k] : 这条边在那个 CNU 上是第几号 port
"""


import numpy as np

TABLE_NAMES = ("cnu_to_vnu_idx", "cnu_to_vnu_port", "vnu_to_cnu_idx", "vnu_to_cnu_port")


def build_connectivity_tables(H):
    H = np.asarray(H)
    rows, cols = H.shape
    cn = [np.flatnonzero(H[i, :]).tolist() for i in range(rows)]
    vn = [np.flatnonzero(H[:, j]).tolist() for j in range(cols)]
    return {
        "cnu_to_vnu_idx":  cn,  # this is the CNU neighborlist
        "cnu_to_vnu_port": [[vn[j].index(i) for j in cn[i]] for i in range(rows)],  # this is the idx_lut for CNU input
        "vnu_to_cnu_idx":  vn,  # this is the VNU neighborlist
        "vnu_to_cnu_port": [[cn[i].index(j) for i in vn[j]] for j in range(cols)],  # this is the idx_lut for VNU input
    }


""" 
    Idea:
    each VNU has three edges (wires leaving VNU) that connect to three different CNUs. Port number: 0, 1, 2
    each CNU has six edges (wires leaving CNU) that connect to six different VNUs. Port number: 0, 1, 2, 3, 4, 5
    vnu_to_cnu_port[i][j] means: there is a wire coming out from port_j of vnu_i; and that wire goes into a CNU; but which port of the connected CNU receives that wire.

    for example:
        vnu_to_cnu_idx[19] = {1, 18, 23}; vnu_to_cnu_port[19] = {2, 0, 1}
        So:
        vnu_19 is connected to cnu_1, with port_0 of vnu_19 and port_2 of cnu_1 connected.
        vnu_19 is connected to cnu_18, with port_1 of vnu_19 and port_0 of cnu_8 connected.
        vnu_19 is connected to cnu_23, with port_2 of vnu_19 and port_1 of cnu_23 connected.
"""