"""
VNU Test Vector Generator for RTL Hardware Verification
========================================================
Target: [[144,12,12]] BB code, d_v = 3, int4 precision (4-bit unsigned magnitude + 1-bit sign)

Generates test vectors for Aman's SystemVerilog VNU testbench.

Reference:
  - Maurer et al. (arXiv:2510.21600) Fig 3b/3c
  - Valls et al. (2021) Fig 4
  - Python vnu_hardware() implementation (Hengrun)

Output files:
  1. vnu_test_vectors_int4.csv          -- human-readable CSV
  2. vnu_test_vectors_int4_input.hex    -- $readmemh for input stimulus
  3. vnu_test_vectors_int4_output.hex   -- $readmemh for expected output
"""

import csv
import random

from vnu_int4 import vnu_hardware


# ============================================================
# Helpers
# ============================================================
D_V = 3       # variable node degree for [[144,12,12]]
MAX_VAL = 15  # int4 unsigned magnitude max

def make_edge(sign, selector, min1, min2):
    """Create one CNU→VNU message dict."""
    return {'sign': sign, 'selector': selector,
            'min1_scaled': min1, 'min2_scaled': min2}

def make_uniform_edges(sign, selector, min1, min2):
    """All 3 edges identical."""
    return [make_edge(sign, selector, min1, min2)] * D_V

def signed_to_sm(val):
    """Signed integer → (sign_bit, magnitude) for int4 encoding.
       sign=0 → non-negative, sign=1 → negative."""
    if val < 0:
        return (1, min(abs(val), MAX_VAL))
    else:
        return (0, min(val, MAX_VAL))

# ============================================================
# Structured corner cases
# ============================================================
def generate_structured():
    cases = []

    def add(category, edges, lam):
        cases.append((category, edges, lam))

    # ---- Category 1: Zero / trivial ----
    add("zero_all",
        make_uniform_edges(0, 0, 0, 0), 0)
    add("zero_edges_lam_pos",
        make_uniform_edges(0, 0, 0, 0), 7)
    add("zero_edges_lam_max",
        make_uniform_edges(0, 0, 0, 0), 15)
    add("zero_edges_lam_1",
        make_uniform_edges(0, 0, 0, 0), 1)

    # ---- Category 2: Selector MUX logic ----
    # min1 != min2 so selector choice is observable
    # selector=0 → use min1=3, selector=1 → use min2=7
    add("sel_all0",
        [make_edge(0, 0, 3, 7)] * 3, 5)
    add("sel_all1",
        [make_edge(0, 1, 3, 7)] * 3, 5)
    add("sel_010",
        [make_edge(0, 0, 3, 7), make_edge(0, 1, 3, 7), make_edge(0, 0, 3, 7)], 5)
    add("sel_101",
        [make_edge(0, 1, 3, 7), make_edge(0, 0, 3, 7), make_edge(0, 1, 3, 7)], 5)
    add("sel_001",
        [make_edge(0, 0, 3, 7), make_edge(0, 0, 3, 7), make_edge(0, 1, 3, 7)], 5)
    add("sel_110",
        [make_edge(0, 1, 3, 7), make_edge(0, 1, 3, 7), make_edge(0, 0, 3, 7)], 5)

    # Selector with min1 == min2 (tie) → selector doesn't matter
    add("sel_tie",
        [make_edge(0, 0, 5, 5), make_edge(0, 1, 5, 5), make_edge(0, 0, 5, 5)], 4)

    # ---- Category 3: Sign path ----
    add("sign_all0",
        [make_edge(0, 0, 4, 6)] * 3, 10)
    add("sign_all1",
        [make_edge(1, 0, 4, 6)] * 3, 10)
    add("sign_010",
        [make_edge(0, 0, 4, 6), make_edge(1, 0, 4, 6), make_edge(0, 0, 4, 6)], 10)
    add("sign_101",
        [make_edge(1, 0, 4, 6), make_edge(0, 0, 4, 6), make_edge(1, 0, 4, 6)], 10)
    add("sign_001",
        [make_edge(0, 0, 4, 6), make_edge(0, 0, 4, 6), make_edge(1, 0, 4, 6)], 10)

    # sign=1 with magnitude=0 → miu should be 0, NOT -0
    add("sign1_mag0",
        [make_edge(1, 0, 0, 5), make_edge(0, 0, 3, 5), make_edge(1, 1, 2, 0)], 6)

    # ---- Category 4: Hard decision boundary ----
    # Target: marginal = 0 → HD = 1
    # miu = [+3, +3, +3], lambda = -9 → marginal = -9+9 = 0
    # ... but lambda physically >= 0. Instead:
    # miu = [-5, -3, -2], lambda = 10 → marginal = 10-5-3-2 = 0
    add("hd_marginal_zero",
        [make_edge(1, 0, 5, 8), make_edge(1, 0, 3, 6), make_edge(1, 0, 2, 4)], 10)

    # marginal = +1 → HD = 0
    add("hd_marginal_plus1",
        [make_edge(1, 0, 5, 8), make_edge(1, 0, 3, 6), make_edge(1, 0, 2, 4)], 11)

    # marginal = -1 → HD = 1
    add("hd_marginal_minus1",
        [make_edge(1, 0, 5, 8), make_edge(1, 0, 3, 6), make_edge(1, 0, 2, 4)], 9)

    # marginal large negative → HD = 1, marginal clamps
    add("hd_large_neg",
        [make_edge(1, 0, 15, 15)] * 3, 0)
    # marginal = 0 - 15 - 15 - 15 = -45, clamped to -15, HD = 1

    # marginal large positive → HD = 0, marginal clamps
    add("hd_large_pos",
        [make_edge(0, 0, 15, 15)] * 3, 15)
    # marginal = 15 + 15 + 15 + 15 = 60, clamped to 15, HD = 0

    # ---- Category 5: Saturation / overflow ----
    # VNU message positive overflow
    # marginal = 15+5+5+5 = 30, miu[0] = -5 → vnu[0] = 30-(-5) = 35 → clamp 15
    add("sat_vnu_pos_overflow",
        [make_edge(1, 0, 5, 8), make_edge(0, 0, 5, 8), make_edge(0, 0, 5, 8)], 15)

    # VNU message negative overflow
    # marginal = 0 -15 -15 +3 = -27, miu[2] = +3 → vnu[2] = -27-3 = -30 → clamp -15
    add("sat_vnu_neg_overflow",
        [make_edge(1, 0, 15, 15), make_edge(1, 0, 15, 15), make_edge(0, 0, 3, 5)], 0)

    # Marginal clamps but VNU messages don't (or vice versa)
    # marginal = 0 - 10 - 10 - 10 = -30 → clamps to -15
    # vnu[0] = -30 - (-10) = -20 → clamps to -15
    # vnu[1] = -30 - (-10) = -20 → clamps to -15
    # vnu[2] = -30 - (-10) = -20 → clamps to -15
    add("sat_both_clamp",
        [make_edge(1, 0, 10, 12)] * 3, 0)

    # Near-boundary: marginal exactly at +15 (no clamping needed)
    # miu = [+5, +5, +5], lambda = 0 → marginal = 15
    add("sat_marginal_exact_max",
        [make_edge(0, 0, 5, 8)] * 3, 0)

    # Near-boundary: marginal exactly at -15
    # miu = [-5, -5, -5], lambda = 0 → marginal = -15
    add("sat_marginal_exact_neg_max",
        [make_edge(1, 0, 5, 8)] * 3, 0)

    # One edge saturates, others don't
    add("sat_one_edge",
        [make_edge(1, 0, 15, 15), make_edge(0, 0, 1, 2), make_edge(0, 0, 1, 2)], 10)

    # ---- Category 6: min1 == min2 (tie) ----
    add("tie_min_zero",
        [make_edge(0, 0, 0, 0), make_edge(0, 1, 0, 0), make_edge(1, 0, 0, 0)], 5)
    add("tie_min_max",
        [make_edge(0, 0, 15, 15), make_edge(1, 1, 15, 15), make_edge(0, 0, 15, 15)], 8)
    add("tie_min_mid",
        [make_edge(1, 0, 7, 7), make_edge(0, 1, 7, 7), make_edge(1, 1, 7, 7)], 12)

    # ---- Category 7: Typical physical values ----
    # p=0.003 → lambda ≈ 12, small CNU magnitudes (error is rare)
    add("typical_no_error",
        [make_edge(0, 0, 2, 4), make_edge(0, 0, 1, 3), make_edge(0, 0, 3, 5)], 12)
    add("typical_one_neg",
        [make_edge(0, 0, 2, 4), make_edge(1, 0, 1, 3), make_edge(0, 1, 3, 5)], 12)
    add("typical_two_neg",
        [make_edge(1, 0, 2, 4), make_edge(1, 0, 1, 3), make_edge(0, 1, 3, 5)], 12)
    add("typical_all_neg",
        [make_edge(1, 0, 2, 4), make_edge(1, 0, 1, 3), make_edge(1, 1, 3, 5)], 12)

    # p=0.01 → lambda ≈ 9
    add("typical_p01_clean",
        [make_edge(0, 0, 3, 5), make_edge(0, 0, 2, 4), make_edge(0, 0, 4, 6)], 9)
    add("typical_p01_error",
        [make_edge(1, 0, 3, 5), make_edge(1, 1, 2, 4), make_edge(1, 0, 4, 6)], 9)

    # ---- Category 8: Mixed selector + sign combinations ----
    add("mixed_sel0_sign0_sel1_sign1",
        [make_edge(0, 0, 2, 8), make_edge(1, 1, 3, 6), make_edge(0, 0, 4, 9)], 7)
    add("mixed_all_different",
        [make_edge(0, 0, 1, 10), make_edge(1, 1, 5, 12), make_edge(0, 1, 3, 8)], 11)
    add("mixed_extreme_spread",
        [make_edge(0, 0, 0, 15), make_edge(1, 1, 0, 15), make_edge(0, 0, 15, 15)], 8)

    # ---- Category 9: Single-edge isolation ----
    # Only one edge has non-zero magnitude; isolate per-edge behavior
    add("isolate_edge0",
        [make_edge(1, 0, 7, 10), make_edge(0, 0, 0, 0), make_edge(0, 0, 0, 0)], 5)
    add("isolate_edge1",
        [make_edge(0, 0, 0, 0), make_edge(1, 1, 4, 9), make_edge(0, 0, 0, 0)], 5)
    add("isolate_edge2",
        [make_edge(0, 0, 0, 0), make_edge(0, 0, 0, 0), make_edge(0, 1, 6, 11)], 5)

    # ---- Category 10: VNU message sign flip ----
    # VNU message changes sign depending on which edge is excluded
    # miu = [-8, +3, +3], lambda = 2 → marginal = 2-8+3+3 = 0
    # vnu[0] = 0-(-8) = 8, vnu[1] = 0-3 = -3, vnu[2] = 0-3 = -3
    add("vnu_sign_flip",
        [make_edge(1, 0, 8, 10), make_edge(0, 0, 3, 5), make_edge(0, 0, 3, 5)], 2)

    return cases


# ============================================================
# Random vectors
# ============================================================
def generate_random(n=300, seed=42):
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        edges = []
        for _ in range(D_V):
            min1 = rng.randint(0, MAX_VAL)
            min2 = rng.randint(min1, MAX_VAL)  # CNU guarantees min2 >= min1
            edges.append(make_edge(
                sign=rng.randint(0, 1),
                selector=rng.randint(0, 1),
                min1=min1,
                min2=min2,
            ))
        lam = rng.randint(0, MAX_VAL)  # channel prior always >= 0
        cases.append(("random", edges, lam))
    return cases


# ============================================================
# Bit packing for $readmemh
# ============================================================
"""
INPUT word: 35 bits (padded to 36 = 9 hex digits)

  Bit [35]    = 0 (pad)
  Bit [34]    = lambda_sign      (0=non-negative, 1=negative)
  Bit [33:30] = lambda_mag[3:0]
  Bit [29]    = sign_2
  Bit [28]    = selector_2
  Bit [27:24] = min1_scaled_2[3:0]
  Bit [23:20] = min2_scaled_2[3:0]
  Bit [19]    = sign_1
  Bit [18]    = selector_1
  Bit [17:14] = min1_scaled_1[3:0]
  Bit [13:10] = min2_scaled_1[3:0]
  Bit [9]     = sign_0
  Bit [8]     = selector_0
  Bit [7:4]   = min1_scaled_0[3:0]
  Bit [3:0]   = min2_scaled_0[3:0]

OUTPUT word: 21 bits (padded to 24 = 6 hex digits)

  Bit [23:21] = 0 (pad)
  Bit [20]    = hard_decision
  Bit [19]    = marginal_sign
  Bit [18:15] = marginal_mag[3:0]
  Bit [14]    = vnu_msg_2_sign
  Bit [13:10] = vnu_msg_2_mag[3:0]
  Bit [9]     = vnu_msg_1_sign
  Bit [8:5]   = vnu_msg_1_mag[3:0]
  Bit [4]     = vnu_msg_0_sign
  Bit [3:0]   = vnu_msg_0_mag[3:0]
"""

def pack_input(edges, lambda_j):
    """Pack VNU inputs into a 36-bit integer."""
    lam_sign, lam_mag = signed_to_sm(lambda_j)
    word = 0
    # pad bit [35] = 0
    word |= (lam_sign & 1) << 34
    word |= (lam_mag & 0xF) << 30
    for k in range(D_V):
        base = (D_V - 1 - k) * 10   # edge2 at [29:20], edge1 at [19:10], edge0 at [9:0]
        # Actually let's do edge0 at bottom
        base = k * 10   # edge0 at [9:0], edge1 at [19:10], edge2 at [29:20]
        # Wait, let me just be explicit:
        pass

    # Explicit packing (clearer):
    word = 0
    word |= (lam_sign & 1) << 34
    word |= (lam_mag & 0xF) << 30

    # Edge 2: bits [29:20]
    word |= (edges[2]['sign'] & 1) << 29
    word |= (edges[2]['selector'] & 1) << 28
    word |= (edges[2]['min1_scaled'] & 0xF) << 24
    word |= (edges[2]['min2_scaled'] & 0xF) << 20

    # Edge 1: bits [19:10]
    word |= (edges[1]['sign'] & 1) << 19
    word |= (edges[1]['selector'] & 1) << 18
    word |= (edges[1]['min1_scaled'] & 0xF) << 14
    word |= (edges[1]['min2_scaled'] & 0xF) << 10

    # Edge 0: bits [9:0]
    word |= (edges[0]['sign'] & 1) << 9
    word |= (edges[0]['selector'] & 1) << 8
    word |= (edges[0]['min1_scaled'] & 0xF) << 4
    word |= (edges[0]['min2_scaled'] & 0xF) << 0

    return word


def pack_output(result):
    """Pack VNU outputs into a 24-bit integer."""
    hd = result['hard_decision']
    m_sign, m_mag = signed_to_sm(result['marginal'])
    vnu_msgs = result['vnu_messages']

    word = 0
    # pad bits [23:21] = 0
    word |= (hd & 1) << 20

    word |= (m_sign & 1) << 19
    word |= (m_mag & 0xF) << 15

    # VNU msg 2: bits [14:10]
    v2_sign, v2_mag = signed_to_sm(vnu_msgs[2])
    word |= (v2_sign & 1) << 14
    word |= (v2_mag & 0xF) << 10

    # VNU msg 1: bits [9:5]
    v1_sign, v1_mag = signed_to_sm(vnu_msgs[1])
    word |= (v1_sign & 1) << 9
    word |= (v1_mag & 0xF) << 5

    # VNU msg 0: bits [4:0]
    v0_sign, v0_mag = signed_to_sm(vnu_msgs[0])
    word |= (v0_sign & 1) << 4
    word |= (v0_mag & 0xF) << 0

    return word


# ============================================================
# Main: generate, compute, write
# ============================================================
def main():
    structured = generate_structured()
    randoms = generate_random(n=300, seed=42)
    all_cases = structured + randoms

    print(f"Structured corner cases: {len(structured)}")
    print(f"Random vectors:          {len(randoms)}")
    print(f"Total:                   {len(all_cases)}")

    # ---- Compute golden outputs ----
    rows = []
    for test_id, (category, edges, lam) in enumerate(all_cases):
        result = vnu_hardware(edges, lam)
        row = {
            'test_id': test_id,
            'category': category,
            'lambda_j': lam,
        }
        for k in range(D_V):
            row[f'sign_{k}'] = edges[k]['sign']
            row[f'selector_{k}'] = edges[k]['selector']
            row[f'min1_scaled_{k}'] = edges[k]['min1_scaled']
            row[f'min2_scaled_{k}'] = edges[k]['min2_scaled']
        for k in range(D_V):
            row[f'vnu_msg_{k}'] = result['vnu_messages'][k]
        row['marginal'] = result['marginal']
        row['hard_decision'] = result['hard_decision']
        rows.append((row, edges, lam, result))

    # ---- Write CSV ----
    csv_path = 'vnu_test_vectors_int4.csv'
    fieldnames = ['test_id', 'category', 'lambda_j']
    for k in range(D_V):
        fieldnames += [f'sign_{k}', f'selector_{k}', f'min1_scaled_{k}', f'min2_scaled_{k}']
    fieldnames += [f'vnu_msg_{k}' for k in range(D_V)]
    fieldnames += ['marginal', 'hard_decision']

    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (row, _, _, _) in rows:
            writer.writerow(row)
    print(f"\nCSV written: {csv_path}")

    # ---- Write hex files ----
    input_hex_path = 'vnu_test_vectors_int4_input.hex'
    output_hex_path = 'vnu_test_vectors_int4_output.hex'

    with open(input_hex_path, 'w') as fi, open(output_hex_path, 'w') as fo:
        for (row, edges, lam, result) in rows:
            in_word = pack_input(edges, lam)
            out_word = pack_output(result)
            fi.write(f"{in_word:09X}\n")   # 36 bits → 9 hex chars
            fo.write(f"{out_word:06X}\n")  # 24 bits → 6 hex chars

    print(f"Input  hex: {input_hex_path}")
    print(f"Output hex: {output_hex_path}")

    # ---- Verification: print first 10 structured ----
    print("\n" + "=" * 80)
    print("First 10 structured cases (verification):")
    print("=" * 80)
    for (row, edges, lam, result) in rows[:10]:
        miu = []
        for k in range(D_V):
            e = edges[k]
            exc_min = e['min2_scaled'] if e['selector'] == 1 else e['min1_scaled']
            miu.append(((-1) ** e['sign']) * exc_min)
        unclamped_marginal = lam + sum(miu)

        print(f"\n[{row['test_id']:3d}] {row['category']}")
        print(f"  lambda = {lam}")
        for k in range(D_V):
            e = edges[k]
            print(f"  edge{k}: sign={e['sign']} sel={e['selector']} "
                  f"min1={e['min1_scaled']:2d} min2={e['min2_scaled']:2d} → miu={miu[k]:+d}")
        print(f"  unclamped marginal = {unclamped_marginal}")
        print(f"  clamped   marginal = {result['marginal']}")
        print(f"  vnu_msgs = {result['vnu_messages']}")
        print(f"  hard_decision = {result['hard_decision']}")
        in_w = pack_input(edges, lam)
        out_w = pack_output(result)
        print(f"  hex: IN={in_w:09X}  OUT={out_w:06X}")


if __name__ == '__main__':
    main()