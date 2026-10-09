"""Export the established core's (variable index, variable port) connectivity.

No BP arithmetic, LFSR, beta generation or prior quantization is implemented here.
"""
import argparse
import json
from pathlib import Path


def export(columns, checks, output):
    output.mkdir(parents=True, exist_ok=True)
    rows = [[] for _ in range(checks)]
    ports = [0]*len(columns)
    for j,col in enumerate(columns):
        assert len(col['detectors']) == len(set(col['detectors']))
        for r in col['detectors']:
            assert 0 <= r < checks
            rows[r].append((j,ports[j]))
            ports[j] += 1
    dc,dv = max(map(len,rows)),max(ports)
    assert dc > 0 and dv > 0
    flat = [pair for row in rows for pair in row+[(len(columns),0)]*(dc-len(row))]
    for name,index in [('cnu_to_vnu_idx',0),('cnu_to_vnu_port',1)]:
        (output/(name+'.mem')).write_text(''.join(f'{pair[index]:x}\n' for pair in flat))
    # Reconstruct exported graph and verify both directions and unique VN ports.
    idx = [int(s,16) for s in (output/'cnu_to_vnu_idx.mem').read_text().split()]
    port = [int(s,16) for s in (output/'cnu_to_vnu_port.mem').read_text().split()]
    recovered = [[] for _ in columns]
    used = set()
    for e,(j,p) in enumerate(zip(idx,port)):
        if j == len(columns): continue
        assert (j,p) not in used
        used.add((j,p)); recovered[j].append(e//dc)
    assert recovered == [sorted(col['detectors']) for col in columns]
    dimensions = dict(N_CHECKS=checks,N_VARS=len(columns),CN_DEG=dc,VN_DEG=dv)
    (output/'dimensions.json').write_text(json.dumps(dimensions,indent=2)+'\n')
    return dc,dv


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('hardware',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    print(export(json.loads((args.hardware/'columns.json').read_text()),864,args.output))
