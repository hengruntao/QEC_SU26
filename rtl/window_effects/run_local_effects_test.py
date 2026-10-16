"""Reproduce finite-graph effects-unit simulation; no Relay or timing claim."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from check_effects_constants import check
from generate_effects_vectors import generate

ROOT=Path(__file__).resolve().parent


def run(c,mask,build):
    package=ROOT/'generated/window_effects_pkg.sv'
    dut=ROOT/'window_effects.sv'
    bench=ROOT/'tb_window_effects.sv'
    if not bench.exists(): bench=ROOT/'reference/tb_window_effects.sv'
    check(ROOT/'data/ibm',mask,package,c)
    build.mkdir(parents=True,exist_ok=True)
    generate(ROOT/'data/ibm',mask,c,build/'vectors')
    # GNU Make cannot build in a path containing spaces, so use transient scratch.
    with tempfile.TemporaryDirectory(prefix='qec-effects-',dir='/tmp') as tmp:
        scratch=Path(tmp)
        for path in (package,dut,bench): shutil.copy2(path,scratch/path.name)
        shutil.copy2(build/'vectors/transactions.txt',scratch/'transactions.txt')
        command=['verilator','--binary','--timing','--Wno-fatal','--replication-limit','16384',
                 '--top-module','tb_window_effects','-j','2',package.name,dut.name,bench.name]
        with (build/'compile.log').open('w') as log:
            result=subprocess.run(command,cwd=scratch,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode: raise RuntimeError(f'Compilation failed; see {build/"compile.log"}')
        simulation=subprocess.run([str(scratch/'obj_dir/Vtb_window_effects')],cwd=scratch,
            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (build/'simulation.log').write_text(simulation.stdout)
        print(simulation.stdout,end='')
        if simulation.returncode or 'PASS effects:' not in simulation.stdout:
            raise RuntimeError('Effects test failed')
    evidence=dict(configuration='Finite IBM graph with explicit derived commit mask',
        commit_cycles=c,real_relay_captures=0,timing_verified=False,
        hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (package,dut,bench)},
        mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),simulation=simulation.stdout)
    (build/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--commit-cycles',type=int,default=8)
    p.add_argument('--mask',type=Path,default=ROOT/'configuration/c8/commit_mask.npy')
    p.add_argument('--build',type=Path,default=ROOT/'build/local_c8')
    args=p.parse_args()
    run(args.commit_cycles,args.mask.resolve(),args.build.resolve())
