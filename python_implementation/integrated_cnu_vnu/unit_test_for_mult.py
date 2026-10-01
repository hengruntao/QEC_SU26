# Intro:
# This is the unit test for function memory_strength_mult()
# This function is used in DMem-BP to implement the optimized multiplication described in the FPGA paper

import numpy as np
import math

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

# ---- unit test: FPGA paper Appendix C, Table 2 (M=8, coeff=7) ----
print(memory_strength_mult(15, 7) == 88/8)    # 88 / 8
print(memory_strength_mult(8,  7) == 56/8)    # 56 / 8
print(memory_strength_mult(4,  7) == 24/8)    # 24 / 8
print(memory_strength_mult(2,  7) == 8/8)     # 8 / 8
print(memory_strength_mult(1,  7) == 0/8)     # 0 / 8

# ---- γ=0: DMem-BP degenerates to BP (coeff=M) ----
    # Λ_j(t) = Λ_j(0), without any difference!!!
is_same = True
for v in range (-15,16):    # v is Λ_j(0), and Λ_j(0) is [-15,15] for int4 precision
    if(memory_strength_mult(v, 8) != v):
        is_same = False
print(f"Memory strength scaling does NOT affect pure BP: {is_same}")