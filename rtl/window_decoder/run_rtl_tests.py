"""Test the real matrix-effects RTL against independent sparse-column parity."""
import argparse
import json
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parent


def bits(indices):
    value = 0
    for i in indices:
        value ^= 1 << i
    return value


def write_mem(path, values, width):
    with path.open('w') as output:
        for value in values:
            output.write(f'{value:0{(width+3)//4}x}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, default=Path('/tmp/qec-window-effects'))
    args = parser.parse_args()
    for sector in ('x_checks', 'z_checks'):
        source = ROOT / 'matrices/generated' / sector / 'hardware'
        directory = (args.build / sector).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        columns = json.loads((source / 'columns.json').read_text())
        n = len(columns)
        stride = 8
        commit = bits(j for j,c in enumerate(columns) if c['cycle'] < stride)
        for name, exported in [('carry', 'carry_rows'), ('frame', 'frame_rows')]:
            (directory / (name+'.mem')).write_text((source / (exported+'.mem')).read_text())
        rng = random.Random(2071+stride)
        vectors = [1 << j for j in range(n)] + [0, (1 << n)-1]
        vectors += [rng.getrandbits(n) for _ in range(64)]
        carries, frames = [], []
        for vector in vectors:
            carry = frame = 0
            remaining = vector & commit
            while remaining:
                bit = remaining & -remaining
                col = columns[bit.bit_length()-1]
                carry ^= bits(d-stride*72 for d in col['detectors'] if stride*72 <= d < (stride+1)*72)
                frame ^= bits(col['logicals'])
                remaining ^= bit
            carries.append(carry)
            frames.append(frame)
        for name, values, width in [('errors',vectors,n), ('carry',carries,72), ('frame',frames,12)]:
            write_mem(directory / ('unit_'+name+'.mem'), values, width)
        top = 'window_effects_tb'
        subprocess.run(['iverilog','-g2012','-s',top,'-o',str(directory/top),
                        f'-P{top}.DIR="{directory}"', f'-P{top}.E={n}', f'-P{top}.COUNT={len(vectors)}',
                        str(ROOT/'window_effects.sv'),str(ROOT/'window_effects_tb.sv')], check=True)
        subprocess.run(['vvp',str(directory/top)], cwd=directory, check=True, timeout=180)
    print('PASS real matrix-effects tests (both sectors)', flush=True)


if __name__ == '__main__':
    main()
