"""Golden transaction vectors; RTL bench implementation is deliberately pending."""
import argparse
import json
import random
from pathlib import Path
import numpy as np
from matrix_io import N_FAULTS, packed
from window_effects_golden import EffectsGolden


def generate(data,mask,c,output,count=128,seed=2026,relay=None):
    model=EffectsGolden(data,mask,c)
    rng=random.Random(seed)
    zero=np.zeros(N_FAULTS,dtype=np.uint8)
    cases=[dict(e_hat=zero.copy(),converged=True,reset=True,kind='zero'),
           dict(e_hat=np.ones(N_FAULTS,dtype=np.uint8),converged=True,kind='all'),
           dict(e_hat=np.ones(N_FAULTS,dtype=np.uint8),converged=False,kind='failure'),
           dict(e_hat=zero.copy(),converged=True,valid=False,kind='invalid')]
    for j in (0,71,72,N_FAULTS-1):
        one=zero.copy(); one[j]=1
        cases.append(dict(e_hat=one,converged=True,kind='onehot'))
    for n in range(count):
        value=rng.getrandbits(N_FAULTS)
        e=np.array([(value>>j)&1 for j in range(N_FAULTS)],dtype=np.uint8)
        cases.append(dict(e_hat=e,converged=n%7!=0,valid=n%11!=0,reset=n%31==0,kind='random'))
    relay_count=0
    if relay:
        document=json.loads(Path(relay).read_text())
        if document['source_hashes'] != model.hashes:
            raise ValueError('Relay captures must use identical matrices, ordering and commit mask')
        if not document.get('provenance'):
            raise ValueError('Relay capture provenance is required')
        for row in document['transactions']:
            value=int(row['e_hat_hex'],16)
            if value<0 or value>>N_FAULTS:
                raise ValueError('Relay e_hat must fit 8785 bits; no padding a 144-bit core result')
            if type(row['converged']) is not bool:
                raise ValueError('converged must be a JSON boolean')
            e=np.array([(value>>j)&1 for j in range(N_FAULTS)],dtype=np.uint8)
            cases.append(dict(e_hat=e,converged=row['converged'],reset=row.get('reset',False),kind='relay'))
            relay_count+=1
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for case in cases:
        if case.get('reset',False): model.reset()
        result=model.step(case['e_hat'],case['converged'],case.get('valid',True))
        rows.append(dict(kind=case['kind'],reset=bool(case.get('reset',False)),
                         input_valid=bool(case.get('valid',True)),converged=bool(case['converged']),
                         e_hat_hex=f"{packed(case['e_hat']):x}",
                         output_valid=result['valid'],success=result['success'],
                         frame_hex=f"{packed(result['frame']):x}",carry_hex=f"{packed(result['carry']):x}"))
    output.joinpath('transactions.json').write_text(json.dumps(dict(source_hashes=model.hashes,seed=seed,
        relay_transactions=relay_count,transactions=rows),indent=2)+'\n')
    # One transaction per line: reset,valid,converged,e_hat,expected-valid,success,carry,frame.
    output.joinpath('transactions.txt').write_text(''.join(
        f"{int(r['reset'])} {int(r['input_valid'])} {int(r['converged'])} {r['e_hat_hex']} "
        f"{int(r['output_valid'])} {int(r['success'])} {r['carry_hex']} {r['frame_hex']}\n" for r in rows))
    print(f'Generated {len(rows)} transactions; {relay_count} supplied Relay-format captures (review provenance)')
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path(__file__).parent/'data/ibm')
    p.add_argument('--mask',type=Path,required=True)
    p.add_argument('--commit-cycles',type=int,required=True)
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'vectors')
    p.add_argument('--random-count',type=int,default=128)
    p.add_argument('--seed',type=int,default=2026)
    p.add_argument('--relay-captures',type=Path)
    args=p.parse_args()
    if args.random_count<0: p.error('random count must be nonnegative')
    generate(args.data,args.mask,args.commit_cycles,args.output,args.random_count,args.seed,args.relay_captures)
