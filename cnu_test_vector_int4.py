from cnu_int4 import cnu_hardware_int4

"""
CNU Test Vector Generator — int4.2.8 format
=============================================
Generates test vectors for RTL verification of the Check Node Unit.

"""

import csv
import random

# ============================================================
#  Corner case definitions
# ============================================================

def build_corner_cases():
    """
    Returns a list of (description, vnu_messages, sigma_i, t) tuples.
    """
    cases = []

    # --------------------------------------------------------
    #  Category 1: Sign path (XOR tree + exclusive sign)
    # --------------------------------------------------------

    # 1a. All positive, syndrome=0
    cases.append((
        "sign: all_pos, syn=0",
        [3, 5, 1, 7, 2, 4], 0, 1
    ))
    # 1b. All positive, syndrome=1
    cases.append((
        "sign: all_pos, syn=1",
        [3, 5, 1, 7, 2, 4], 1, 1
    ))
    # 1c. All negative, syndrome=0
    cases.append((
        "sign: all_neg, syn=0",
        [-3, -5, -1, -7, -2, -4], 0, 1
    ))
    # 1d. All negative, syndrome=1
    cases.append((
        "sign: all_neg, syn=1",
        [-3, -5, -1, -7, -2, -4], 1, 1
    ))
    # 1e. Single negative at different edge positions
    for edge_pos in [0, 3, 5]:
        msgs = [3, 5, 1, 7, 2, 4]
        msgs[edge_pos] = -msgs[edge_pos]
        cases.append((
            f"sign: single_neg_at_edge{edge_pos}, syn=0",
            msgs, 0, 1
        ))
        msgs2 = [3, 5, 1, 7, 2, 4]
        msgs2[edge_pos] = -msgs2[edge_pos]
        cases.append((
            f"sign: single_neg_at_edge{edge_pos}, syn=1",
            msgs2, 1, 1
        ))
    # 1f. Alternating signs
    cases.append((
        "sign: alternating +-+-+-, syn=0",
        [3, -5, 1, -7, 2, -4], 0, 1
    ))
    cases.append((
        "sign: alternating +-+-+-, syn=1",
        [3, -5, 1, -7, 2, -4], 1, 1
    ))

    # --------------------------------------------------------
    #  Category 2: Magnitude path (min-find + selector)
    # --------------------------------------------------------

    # 2a. All distinct magnitudes, min at different positions
    cases.append((
        "mag: all_distinct, min_at_edge4",
        [3, 5, 2, 7, 1, 4], 0, 1    # min1=1 at edge4, min2=2 at edge2
    ))
    cases.append((
        "mag: all_distinct, min_at_edge0",
        [1, 5, 2, 7, 3, 4], 0, 1    # min1=1 at edge0, min2=2 at edge2
    ))
    cases.append((
        "mag: all_distinct, min_at_edge5",
        [3, 5, 2, 7, 4, 1], 0, 1    # min1=1 at edge5, min2=2 at edge2
    ))
    # 2b. Two tied minimums — both selectors should be 1
    cases.append((
        "mag: two_tied_min (edge0,2)",
        [3, 5, 3, 7, 6, 4], 0, 1    # min1=3, min2=3, selector[0]=1, selector[2]=1
    ))
    cases.append((
        "mag: two_tied_min (edge1,4)",
        [5, 2, 7, 6, 2, 4], 0, 1    # min1=2, min2=2, selector[1]=1, selector[4]=1
    ))
    # 2c. Three tied minimums
    cases.append((
        "mag: three_tied_min (edge0,2,4)",
        [2, 5, 2, 7, 2, 4], 0, 1    # min1=2, min2=2, three selectors=1
    ))
    # 2d. All equal
    cases.append((
        "mag: all_equal_4",
        [4, 4, 4, 4, 4, 4], 0, 1    # min1=min2=4, all selectors=1
    ))
    cases.append((
        "mag: all_equal_1",
        [1, 1, 1, 1, 1, 1], 0, 1
    ))
    # 2e. All zero
    cases.append((
        "mag: all_zero",
        [0, 0, 0, 0, 0, 0], 0, 1    # min1=min2=0, all selectors=1
    ))
    # 2f. All maximum
    cases.append((
        "mag: all_max_7",
        [7, 7, 7, 7, 7, 7], 0, 1    # min1=min2=7, all selectors=1
    ))
    # 2g. One zero among large values
    cases.append((
        "mag: one_zero_rest_large",
        [7, 6, 5, 0, 4, 3], 0, 1    # min1=0, min2=3
    ))
    # 2h. min1=0, min2=1 (smallest possible nonzero gap)
    cases.append((
        "mag: min_0_min2_1",
        [5, 0, 7, 1, 6, 3], 0, 1
    ))

    # --------------------------------------------------------
    #  Category 3: Alpha scaling (integer shift-subtract)
    #  Exhaustive over all magnitude values 0-7, for t=1,2,3
    # --------------------------------------------------------

    # Use inputs where min1 = target value, min2 = 7 (max)
    # so we test the scaling on a specific min1 value.
    for t in [1, 2, 3]:
        for min_val in range(8):  # 0 through 7
            # Place min_val at edge 0, fill rest with 7
            msgs = [min_val, 7, 7, 7, 7, 7]
            cases.append((
                f"alpha: t={t}, min1={min_val}",
                msgs, 0, t
            ))

    return cases


# ============================================================
#  Random case generation
# ============================================================

def build_random_cases(n=300, seed=42):
    """
    Generate n random test cases.
    Each: 6 signed integers in [-7, +7], syndrome in {0,1}, t in {1,2,3}.
    """
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        msgs = [rng.randint(-7, 7) for _ in range(6)]
        syn = rng.randint(0, 1)
        t = rng.randint(1, 3)
        cases.append((f"random_{i:03d}", msgs, syn, t))
    return cases


# ============================================================
#  Run all cases and write CSV
# ============================================================

def run_and_write_csv(filename="cnu_test_vectors_int4.csv"):
    corner_cases = build_corner_cases()
    random_cases = build_random_cases(n=300, seed=42)
    all_cases = corner_cases + random_cases

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "test_id", "description",
            # Inputs
            "in_msg0", "in_msg1", "in_msg2", "in_msg3", "in_msg4", "in_msg5",
            "in_syndrome", "in_t",
            # Outputs (6 edges × 4 fields)
            "out_sign0", "out_c0", "out_sign1", "out_c1",
            "out_sign2", "out_c2", "out_sign3", "out_c3",
            "out_sign4", "out_c4", "out_sign5", "out_c5",
            "out_min1_scaled", "out_min2_scaled"
        ])

        for idx, (desc, msgs, syn, t) in enumerate(all_cases):
            result = cnu_hardware_int4(msgs, syn, t)

            row = [idx, desc]
            # Inputs: 6 messages + syndrome + t
            row.extend(msgs)
            row.append(syn)
            row.append(t)
            # Outputs: per-edge (sign, c) × 6, then global (min1, min2)
            for j in range(6):
                row.append(result["signs"][j])
                row.append(result["selectors"][j])
            row.append(result["min1_scaled"])
            row.append(result["min2_scaled"])

            writer.writerow(row)

    return len(all_cases)


# ============================================================
#  Main
# ============================================================

if __name__ == "__main__":
    total = run_and_write_csv()

    # Print summary
    print(f"Generated {total} test vectors -> cnu_test_vectors_int4.csv")
    print()

    # Quick sanity check: print first few corner cases
    print("=== First 5 corner cases (sanity check) ===")
    corner_cases = build_corner_cases()
    for desc, msgs, syn, t in corner_cases[:5]:
        result = cnu_hardware_int4(msgs, syn, t)
        print(f"\n[{desc}]")
        print(f"  Input:  msgs={msgs}  syn={syn}  t={t}")
        print(f"  Output: min1={result['min1_scaled']}  min2={result['min2_scaled']}")
        for j in range(6):
            print(f"    edge {j}: sign={result['signs'][j]}  c={result['selectors'][j]}  "
                  f"min1={result['min1_scaled']}  min2={result['min2_scaled']}")