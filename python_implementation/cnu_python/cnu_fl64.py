import numpy as np

def cnu_hardware(vnu_messages, sigma_i, alpha): 
    """
    Cnu: processes one check node (one row of H).
    
    Inputs:
        vnu_messages : list/array of float
                        Incoming messages v_{j→i} from neighboring variable nodes.
        sigma_i      : int (0 or 1) 1 means parity check detects an odd number of errors
                        Syndrome/detector bit for this check node.
        alpha        : float
                        Min-sum scaling factor (typically 1 - 2^{-t}).
    
    Returns:
        dict with keys:
            'min1_scaled'  : float, α × min1 (shared across all edges)
            'min2_scaled'  : float, α × min2 (shared across all edges)
            'signs'        : list of int (0 or 1), per-edge output sign bits
            'selectors'    : list of int (0 or 1), per-edge selector bits
    """
    vnu_message = np.array(vnu_messages, dtype=float)
    num_vnu_message = len(vnu_message)
    
    # ---- Step 1: Decompose into sign bits and magnitudes ----
    # Convention: sign bit 0 = positive (or zero), 1 = negative
    
    # vnu < 0 compares each element with 0; if smaller, True; if larger, False; astype transforms True to 1, False to 0
    sign_bits = (vnu_message < 0).astype(int)   # vnu < 0 means MSB is 1
    magnitudes = np.abs(vnu_message)
    
    # ---- Step 2: Compute full parity ----
    # full_parity = s_0 ⊕ s_1 ⊕ ... ⊕ s_{d_c-1} ⊕ σ_i
    full_parity = sigma_i
    for s in sign_bits:
        full_parity = full_parity ^ s   # parity = 0 -> even number of "1" (even number of "-")
    
    # ---- Step 3: Compute min1, min2, argmin_idx ----
    # min1: minimum of all magnitude
    # min2: 2nd minimum of all magnitude
    # argmin_idx: index of the first min1 -> if min1 repeats, only the first one is recorded

    min1 = float('inf')
    min2 = float('inf') #initialized to +infinity
    argmin_idx = 0
    for i in range (num_vnu_message):
        temp_val = magnitudes[i]
        if (temp_val < min1):
            min2 = min1
            min1 = temp_val
            argmin_idx = i
        elif (temp_val < min2):
            min2 = temp_val


    # ---- Step 4: Per-edge sign and selector ----
    # sign_out_j = full_parity ⊕ s_j
    # selector_j = 1 if j == argmin_idx, else 0 (to choose from min1 & min2)

    signs_per_edge = []
    selectors_per_edge = []
    for j in range (num_vnu_message):
        signs_per_edge.append(int(full_parity ^ sign_bits[j]))
        if (j == argmin_idx):
            selectors_per_edge.append(1)
        else:
            selectors_per_edge.append(0)
        
    # ---- Step 5: Alpha scaling and return ----
    # α is the scaling factor for VNU hardware, it's not the original component of Equ (1) in FPGA paper
    min1_scaled = alpha * min1
    min2_scaled = alpha * min2


    return {
        'min1_scaled':  float(min1_scaled),
        'min2_scaled':  float(min2_scaled),
        'signs':        signs_per_edge,
        'selectors':    selectors_per_edge,
    }

# Testing
result = cnu_hardware([2.5, -1.3, 0.0, -4.7], sigma_i=0, alpha=0.5)
print(result)
# min1 = 0.0, min2 = 1.3
# Expectation:
# 'min1_scaled':  0.0    (0.5 × 0.0)
# 'min2_scaled':  0.65   (0.5 × 1.3)
# 'signs':        [0, 1, 0, 1]
# 'selectors':    [0, 0, 1, 0]