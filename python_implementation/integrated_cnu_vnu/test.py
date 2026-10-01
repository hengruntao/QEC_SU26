import numpy as np
from matrix_generator import get_H_x, get_H_z, get_A_x, get_A_z

Hx, Hz = get_H_x().astype(np.int64), get_H_z().astype(np.int64)
Ax, Az = get_A_x().astype(np.int64), get_A_z().astype(np.int64)

print("A_x · H_z^T == 0 ?", np.all((Ax @ Hz.T) % 2 == 0))
print("A_x · H_x^T == 0 ?", np.all((Ax @ Hx.T) % 2 == 0))
print("A_x · A_z^T mod 2 == I ?", np.array_equal((Ax @ Az.T) % 2, np.eye(12, dtype=np.int64)))