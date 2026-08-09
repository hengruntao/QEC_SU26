# https://github.com/qLDPCOrg/qLDPC/tree/main/src/qldpc/codes L634
# https://github.com/qLDPCOrg/qLDPC/blob/main/examples/bivariate_bicycle_codes.ipynb

import numpy as np
from sympy.abc import x, y
from qldpc import codes

orders = {x: 12, y: 6}
poly_a = x**3 + y + y**2
poly_b = y**3 + x + x**2
code = codes.BBCode(orders, poly_a, poly_b)

def get_H_x():
    H_x = np.array(code.matrix_x)
    return H_x

def get_H_z():
    H_z = np.array(code.matrix_z)
    return H_z