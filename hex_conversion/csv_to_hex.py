"""
Convert cnu_test_vectors_int4.csv to hex files for $readmemh.

Produces two files:
  cnu_inputs.hex   — one line per test: 6 x 4-bit messages + 4-bit t + 1-bit syndrome
  cnu_expected.hex — one line per test: 6 x (1-bit sign, 1-bit c) + 4-bit min1 + 4-bit min2

Encoding for input messages (signed int → 4-bit packed):
  bit 3 = sign (1 if negative), bits 2:0 = magnitude
  e.g. -5 → 0b1_101 = 0xD,  +3 → 0b0_011 = 0x3

Output packing (MSB first):
  cnu_expected: {sign0, c0, sign1, c1, sign2, c2, sign3, c3, sign4, c4, sign5, c5, min1[3:0], min2[3:0]}
               = 12 + 4 + 4 = 20 bits → 5 hex digits

  cnu_inputs:   {msg0[3:0], msg1[3:0], msg2[3:0], msg3[3:0], msg4[3:0], msg5[3:0], t[3:0], 000 & syndrome}
               = 24 + 4 + 4 = 32 bits → 8 hex digits
"""

import csv
import sys


def signed_to_int4(val):
    """Convert signed integer (-7..+7) to 4-bit packed: sign(1) | mag(3)."""
    v = int(val)
    sign = 1 if v < 0 else 0
    mag = abs(v) & 0x7
    return (sign << 3) | mag


def main(csv_path="cnu_test_vectors_int4.csv",
         input_hex="cnu_inputs.hex",
         expected_hex="cnu_expected.hex"):

    with open(csv_path, "r") as f_csv, \
         open(input_hex, "w") as f_in, \
         open(expected_hex, "w") as f_exp:

        reader = csv.DictReader(f_csv)

        for row in reader:
            # --- Inputs ---
            msgs = [signed_to_int4(row[f"in_msg{i}"]) for i in range(6)]
            syndrome = int(row["in_syndrome"])
            t = int(row["in_t"])

            # Pack: msg0..msg5 (4 bits each) | t (4 bits) | syndrome (4 bits, zero-padded)
            inp = 0
            for m in msgs:
                inp = (inp << 4) | m
            inp = (inp << 4) | (t & 0xF)
            inp = (inp << 4) | (syndrome & 0x1)

            f_in.write(f"{inp:08X}\n")

            # --- Expected outputs ---
            signs = [int(row[f"out_sign{i}"]) for i in range(6)]
            selectors = [int(row[f"out_c{i}"]) for i in range(6)]
            min1 = int(row["out_min1_scaled"]) & 0xF
            min2 = int(row["out_min2_scaled"]) & 0xF

            # Pack: {sign0, c0, sign1, c1, ..., sign5, c5} (12 bits) | min1 (4 bits) | min2 (4 bits)
            exp = 0
            for i in range(6):
                exp = (exp << 1) | signs[i]
                exp = (exp << 1) | selectors[i]
            exp = (exp << 4) | min1
            exp = (exp << 4) | min2

            f_exp.write(f"{exp:05X}\n")

    print(f"Wrote {input_hex} and {expected_hex}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "cnu_test_vectors_int4.csv"
    main(csv_path)
