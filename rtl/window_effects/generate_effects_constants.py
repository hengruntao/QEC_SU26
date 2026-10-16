"""Emit constant masks/rows, never runtime matrix initialization."""
import argparse
import json
from pathlib import Path
from matrix_io import N_FAULTS, N_CHECKS, N_LOGICAL, M, load_inputs, packed


def generate(data, mask_path, commit_cycles, output, mask_source):
    h, a, mask, hashes = load_inputs(data, mask_path, commit_cycles)
    frame = [0]*N_LOGICAL
    carry = [0]*M
    for r, j in a:
        if mask[j]:
            frame[r] |= 1 << j
    touched = set()
    for r, j in h:
        if commit_cycles*M <= r < (commit_cycles+1)*M and mask[j]:
            carry[r-commit_cycles*M] |= 1 << j
            touched.add(j)
    def literal(name, row):
        return f"    localparam logic [N_FAULTS-1:0] {name} = {N_FAULTS}'h{row:x};"
    lines = ['// Generated; column j is packed bit j. Do not hand edit.',
             'package window_effects_pkg;', f'    localparam int N_FAULTS = {N_FAULTS};',
             f'    localparam int N_CHECKS = {N_CHECKS};', f'    localparam int N_LOGICAL = {N_LOGICAL};',
             f'    localparam int M = {M};', f'    localparam int C = {commit_cycles};',
             literal('COMMIT_MASK', packed(mask))]
    lines += [literal(f'FRAME_ROW_{r}', row) for r, row in enumerate(frame)]
    lines += [literal(f'CARRY_ROW_{r}', row) for r, row in enumerate(carry)]
    # Packed row r occupies slice r, hence descending concatenation order.
    lines += ['    localparam logic [M-1:0][N_FAULTS-1:0] CARRY_ROWS = {',
              '        '+', '.join(f'CARRY_ROW_{r}' for r in reversed(range(M))),
              '    };']
    lines += ['endpackage', '']
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines))
    manifest = {'schema': 1, 'source_hashes': hashes, 'commit_mask_source': mask_source,
                'dimensions': {'faults': N_FAULTS, 'checks': N_CHECKS, 'logical': N_LOGICAL, 'M': M, 'C': commit_cycles},
                'carry_committed_columns': sorted(touched), 'carry_unique_columns': len(touched),
                'carry_row_weights': [bin(x).count('1') for x in carry],
                'frame_row_weights': [bin(x).count('1') for x in frame],
                'note': 'Rows pre-intersected with the fault-space commit mask; no column reorder.'}
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Generated {output}; {len(touched)} unique committed faults touch cycle C')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=Path(__file__).parent/'data/ibm')
    p.add_argument('--mask', type=Path, required=True)
    p.add_argument('--mask-source', required=True, help='Provenance/rule for the reviewed mask')
    p.add_argument('--commit-cycles', type=int, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).parent/'generated/window_effects_pkg.sv')
    args = p.parse_args()
    generate(args.data, args.mask, args.commit_cycles, args.output, args.mask_source)
