def vnu_hardware_int4(cnu_messages, lambda_j):
    """
    VNU: processes one variable node (one column of H).
    
    Inputs:
        cnu_messages : list of dict, length = i
                      Each dict from a neighboring CNU i has keys:
                        'sign'        : int (0 or 1)
                        'selector'    : int (0 or 1)
                        'min1_scaled' : int
                        'min2_scaled' : int
        lambda_j    : int
                      Error prior Λ_j = log((1-p_j)/p_j)
    
    IMPORTANRT:
        IT IS the CALLER's responsibility to pass in-scale lambda_j

    Returns:
        dict with keys:
            'vnu_messages'   : list of int4, ν_{j→i} for each edge
            # NOT necessary: 'marginal'        : int, M_j
            'hard_decision' : int (0 or 1), ê_j

    """
    num_cnu_message = len(cnu_messages)
    # set max value as what int4 can represent (unsigned int4)
    # reference: FPGA paper, Fig 5 table (4-bit int + sign)
    max_value = (1 << 4) - 1
    

    # Rust reference code relay/crates/relay_bp/src/bp/min_sum.rs
    #   line 590 - 614
    # Implement the bound_value function to clamp any potential overflow
    def bound_value(val):
        if val > max_value:
            return max_value
        elif val < -max_value:
            return -max_value
        return val


    # ---- Step 1: Transfer CNU outputs to μ values ----
    # CNU deferred the exclusive min to VNU
    # selector == 1: this edge was the argmin -> use min2
    # selector == 0: this edge was NOT the argmin -> use min1
    miu_values = []
    for i in range(num_cnu_message):
        cnu_i_message = cnu_messages[i]
        if (cnu_i_message['selector'] == 1):
            exclusive_minimum = cnu_i_message['min2_scaled']
        else:
            exclusive_minimum = cnu_i_message['min1_scaled']

        cnu_i_sign = cnu_i_message['sign']
        miu_values.append(((-1)**cnu_i_sign) * exclusive_minimum)
    

    # ---- Step 2: Compute margin M_j (Equ 3) ----
    marginal_j = lambda_j   # initialize to Λ_j
    for miu in miu_values:
        marginal_j += miu


    # ---- Step 3: Per-edge exclusive sum (Equ 2) as VNU message v ----
    # full sum - self = exclusive sum
    vnu_messages = []
    for i in range(num_cnu_message):
        vnu_messages.append(bound_value(marginal_j - miu_values[i]))


    # ---- Step 4: Hard decision ----
    # HD = 1/2 (1-sgn(marginal_j)); sign is 1 (positive); -1 (negative); 0 (0)
    # e_j = 1 if M_j < 0 (IS error), 0 otherwise

    # reference for the decision: marginal = 0, HD = 1:
    # relay/crates/relay_bp/src/bp/min_sum.rs
    #   line 616-622

    if (marginal_j <= 0):
        hard_decision = 1
    else:
        hard_decision = 0


    # ---- Step 5: clamp marginal_j ----
    marginal_j = bound_value(marginal_j)

    return {
        'vnu_messages': vnu_messages,
        'marginal': marginal_j,
        'hard_decision': hard_decision,
    }


    # ---- Test ----
cnu_msgs_1 = [
    {'sign': 1, 'selector': 0, 'min1_scaled': 2, 'min2_scaled': 4},
    {'sign': 1, 'selector': 0, 'min1_scaled': 1, 'min2_scaled': 3},
]

# miu = [-2, -1]
# marginal = 3 + (-2) + (-1) = 0
# vnu_message = [0-(-2), 0-(-1)] = [2, 1]
# hard_decision = 1  (<= 0)
if __name__ == "__main__":
    result = vnu_hardware_int4(cnu_msgs_1, lambda_j=3)
    print(result)