"""Independent dense reconstruction of IBM NPZ matrices versus emitted SV."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np


def dense(path):
    with np.load(path, allow_pickle=False) as z:
        shape = tuple(z['shape'])
        result = np.zeros(shape, dtype=np.uint8)
        fmt = z['format'].item()
        if isinstance(fmt, bytes):
            fmt = fmt.decode()
        if fmt not in ('csr', 'csc'):
            raise ValueError('Unsupported sparse format')
        for major in range(len(z['indptr'])-1):
            start, stop = z['indptr'][major:major+2]
            for k in range(int(start), int(stop)):
                minor = int(z['indices'][k])
                r, c = (major, minor) if fmt == 'csr' else (minor, major)
                if z['data'][k] not in (0, 1):
                    raise ValueError('Matrix must be binary')
                result[r, c] ^= int(z['data'][k])
    return result


def check(data, mask_path, package, commit_cycles):
    h = dense(Path(data)/'144_12_12_Hdec.npz')
    a = dense(Path(data)/'144_12_12_Adec.npz')
    mask = np.load(mask_path, allow_pickle=False)
    if h.shape != (1008,8785) or a.shape != (12,8785) or mask.shape != (8785,):
        raise ValueError('Full-size matrix/mask dimensions do not match')
    if not 1 <= commit_cycles < 14 or np.any((mask != 0) & (mask != 1)):
        raise ValueError('Invalid carry cycle or binary mask')
    text = Path(package).read_text()
    if re.search(r'\$readmem[hb]', text):
        raise ValueError('Runtime matrix loading is forbidden')
    constants = re.findall(r"localparam logic \[N_FAULTS-1:0\] (\w+) = (\d+)'h([0-9a-fA-F]+);", text)
    expected = {'COMMIT_MASK': mask}
    expected.update({f'FRAME_ROW_{r}': a[r] & mask for r in range(12)})
    expected.update({f'CARRY_ROW_{r}': h[commit_cycles*72+r] & mask for r in range(72)})
    if len(constants) != len(expected) or {n for n,_,_ in constants} != set(expected):
        raise ValueError('Missing, duplicate or unexpected constants')
    for name, width, digits in constants:
        value = int(digits,16)
        reference = expected[name]
        if int(width) != 8785 or value >> 8785:
            raise ValueError(f'{name}: incorrect packed width')
        for j in range(8785):
            if ((value >> j) & 1) != int(reference[j]):
                raise ValueError(f'{name}: column {j} mismatch')
    for name, value in dict(N_FAULTS=8785,N_CHECKS=1008,N_LOGICAL=12,M=72,C=commit_cycles).items():
        if not re.search(rf'localparam int {name} = {value};',text):
            raise ValueError(f'Configuration mismatch: {name}')
    table = re.findall(r'localparam logic \[M-1:0\]\[N_FAULTS-1:0\] CARRY_ROWS = \{([^}]+)\};',text)
    if len(table) != 1 or [x.strip() for x in table[0].split(',')] != [f'CARRY_ROW_{r}' for r in range(71,-1,-1)]:
        raise ValueError('Carry row table is missing or has incorrect index order')
    manifest = json.loads(Path(package).with_suffix('.json').read_text())
    sources = {'H':Path(data)/'144_12_12_Hdec.npz','A':Path(data)/'144_12_12_Adec.npz','mask':Path(mask_path)}
    for name,path in sources.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['source_hashes'][name]:
            raise ValueError(f'Source hash mismatch: {name}')
    columns = np.flatnonzero(np.any(h[commit_cycles*72:(commit_cycles+1)*72] & mask,axis=0)).tolist()
    if columns != manifest['carry_committed_columns'] or len(columns) != manifest['carry_unique_columns']:
        raise ValueError('Carry support manifest mismatch')
    print(f'PASS independent constants check: all 85 masks/rows; carry touches {len(columns)} committed columns')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path(__file__).parent/'data/ibm')
    p.add_argument('--mask',type=Path,required=True)
    p.add_argument('--package',type=Path,default=Path(__file__).parent/'generated/window_effects_pkg.sv')
    p.add_argument('--commit-cycles',type=int,required=True)
    args=p.parse_args()
    check(args.data,args.mask,args.package,args.commit_cycles)
