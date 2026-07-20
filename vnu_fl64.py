def vnu_hardware(cnu_messages, lambda_j):
    """
    VNU: processes one variable node (one column of H).
    
    Inputs:
        cnu_messages : list of dict, length = i
                      Each dict from a neighboring CNU i has keys:
                        'sign'        : int (0 or 1)
                        'selector'    : int (0 or 1)
                        'min1_scaled' : float
                        'min2_scaled' : float
        lambda_j    : float
                      Error prior Λ_j = log((1-p_j)/p_j)
    
    Returns:
        dict with keys:
            'vnu_messages'   : list of float, ν_{j→i} for each edge
            'hard_decision' : int (0 or 1), ê_j
            'margin'        : float, M_j
    """
    num_cnu_message = len(cnu_messages)
    
    # ---- Step 1: Resolve CNU outputs to μ values ----
    # CNU deferred the exclusive minimum to VNU.
    # selector == 1 means this edge was the argmin → use min2
    # selector == 0 means this edge was NOT the argmin → use min1
    miu_values = []
    for i in range(num_cnu_message):
        cnu_i_message = cnu_messages[i]
        if (cnu_i_message['selector'] == 1):
            exclusive_minimum = cnu_i_message['min2_scaled']
        else:
            exclusive_minimum = cnu_i_message['min1_scaled']

        cnu_i_sign = cnu_i_message['sign']
        miu_values.append((-1)**cnu_i_sign * exclusive_minimum)
    

    # ---- Step 2: Compute margin M_j (Equ 3) ----
    marginal_j = lambda_j
    for miu in miu_values:
        marginal_j += miu


    # ---- Step 3: Per-edge exclusive sum (Equ 2) ----
    # full sum - self = exclusive sum
    vnu_messages = []
    for i in range(num_cnu_message):
        vnu_messages.append(marginal_j - miu_values[i])

    # ---- Step 4: Hard decision ----
    # ê_j = 1 if M_j ≤ 0 (判定有 error), 0 otherwise
    if (marginal_j <= 0):
        hard_decision = 1
    else:
        hard_decision = 0

    return {
        'vnu_messages': vnu_messages,
        'hard_decision': hard_decision,
        'marginal': marginal_j,
    }




# margin = 5.0 + 2.0 + (-4.0) + 0.5 = 3.5
# 期望: margin = 3.5