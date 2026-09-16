# ---- intro ----
# this file generates check matrix (H) and logical action matrix (A)
# NOTICE: parameters are hardcoded for gross code [[144,12,12]]
# See math in paper arXiv:2308.07915v2

import numpy as np
from sympy.abc import x, y
from qldpc import codes

# Here we use gross code [[144,12,12]] ([[n,k,d]])
# l = 12, m = 6
orders = {x: 12, y: 6}
poly_a = x**3 + y + y**2
poly_b = y**3 + x + x**2
code = codes.BBCode(orders, poly_a, poly_b)

# Z-type physical error <-> H_x <-> A_x (X-type logical operator)

# ---- get check matrix H ----
    # H_x for Z-type error
    # H_z for X-type error

    # https://github.com/qLDPCOrg/qLDPC/tree/main/src/qldpc/codes L634
    # https://github.com/qLDPCOrg/qLDPC/blob/main/examples/bivariate_bicycle_codes.ipynb

def get_H_x():
    H_x = np.array(code.matrix_x)
    return H_x

def get_H_z():
    H_z = np.array(code.matrix_z)
    return H_z

# ---- get logical matrix A ----
    # A for X_type logical operator -> row:[0,k]; col:[0,n]
    # A for Z_type logical operator -> row:[k,2k]; col:[n,2n]

    # https://github.com/qLDPCOrg/qLDPC/blob/main/src/qldpc/codes/common.py L1150

A_full = np.array(code.get_logical_ops())

def get_A_x():
    A_x = A_full[:12, :144]
    return A_x

def get_A_z():
    A_z = A_full[12:24, 144:288]
    return A_z

def validate():
    H_x = get_H_x()
    H_z = get_H_z()
    A_x = get_A_x()
    A_z = get_A_z()

    assert H_x.shape == (72, 144)
    assert np.all(H_x.sum(axis=1) == 6)
    assert np.all(H_x.sum(axis=0) == 3)

    assert H_z.shape == (72, 144)
    assert np.all(H_z.sum(axis=1) == 6)
    assert np.all(H_z.sum(axis=0) == 3)

    assert np.all((H_x @ H_z.T) % 2 == 0)

    assert A_full.shape == (24, 288)
    assert A_x.shape == (12, 144)
    assert A_z.shape == (12, 144)
    print("All assertions passed.")

if __name__ == "__main__":
    validate()