import numpy as np

# Difference between cnu_fl64: third input variable changed from "alpha" to "t"
def cnu_hardware_int4(vnu_messages, sigma_i, t): 
    """
    CNU: processes one check node (one row of H)
    input as "v", output as "miu"
    
    Inputs:
        vnu_messages : list/array of int, range [-7, +7] for int4.2.8
                        Incoming messages v_{j→i} from neighboring variable nodes.
        sigma_i      : int (0 or 1) 1 means parity check detects an odd number of errors
                        Syndrome/detector bit for this check node. (message from QPU)
        t            : int (>= 1), BP iteration index.
                        Determines α = 1 - 2^(-t).
    IMPORTANT concept:
        sigma_i is the ONLY ground truth (message from the stabilizer in QPU)
        vnu_messages are ONLY guesses!!

    Returns:
        dict with keys:
            'min1_scaled'  : int, α × min1 (shared across all edges)
            'min2_scaled'  : int, α × min2 (shared across all edges)
            'signs'        : list of int (0 or 1), per-edge output sign bits
            'selectors'    : list of int (0 or 1), per-edge selector bits
    """
    vnu_message = np.array(vnu_messages, dtype=int)
    num_vnu_message = len(vnu_message)
    
    # ---- Step 1: Decompose into sign bits and magnitudes ----
    # Convention: sign bit 0 = positive (or zero), 1 = negative
    
    # vnu < 0 compares each element with 0; if smaller, True; if larger, False; astype transforms True to 1, False to 0
    sign_bits = (vnu_message < 0).astype(int)   # vnu < 0 means MSB is 1 -> IS error; MSB is 0 -> NO error
    magnitudes = np.abs(vnu_message)
    #   e.g.:
    #   vnu_message  = [ 3, -5,  2, -7,  1, -4]
    #   sign_bits    = [ 0,  1,  0,  1,  0,  1]
    #   magnitudes   = [ 3,  5,  2,  7,  1,  4]


    # ---- Step 2: Compute full parity ----
    # full_parity = s_0 ⊕ s_1 ⊕ ... ⊕ s_{d_c-1} ⊕ σ_i

    # 2 sources of info:
    #   1. sigma_i, syndrom bit from QPU (info from stabilizer)
    #   2. sign_bits, guesses from other VNU nodes
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
            # argmin_idx = i
        elif (temp_val < min2):
            min2 = temp_val


    # ---- Step 4: Per-edge sign and selector ----
    # sign_out_j = full_parity ⊕ s_j
    # selector_j = 1 if j == argmin_idx, else 0 (to choose from min1 & min2)
    # sign = 0 means positive -> likely NO error; sign = 1 means negative -> likely IS error

    signs_per_edge = []
    selectors_per_edge = []
    for j in range (num_vnu_message):
        signs_per_edge.append(int(full_parity ^ sign_bits[j]))
        # if (j == argmin_idx):
        if (magnitudes[j] == min1):
            selectors_per_edge.append(1)
        else:
            selectors_per_edge.append(0)
        
    # ---- Step 5: Alpha scaling and return ----
    # α is the scaling factor for CNU hardware, it's not the original component of Equ (1) in FPGA paper
    min1_scaled = int (min1 - (min1 >> t))
    min2_scaled = int (min2 - (min2 >> t))


    return {
        'min1_scaled':  min1_scaled,
        'min2_scaled':  min2_scaled,
        'signs':        signs_per_edge,
        'selectors':    selectors_per_edge,
    }

# Testing
result = cnu_hardware_int4([3, -5, 2, -7, 1, -4], sigma_i=1, t=1)
print(result)
# Expectation:
# min1_scaled = 1,  min2_scaled = 1
# signs     = [0, 1, 0, 1, 0, 1]
# selectors = [0, 0, 0, 0, 1, 0]