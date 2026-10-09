"""Local package checks. Verilator runs the exact packaged RTL and benches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from verify_package import verify

ROOT=Path(__file__).resolve().parent
CORE=['cnu_pkg.sv','cnu.sv','vnu.sv','relay_bp_top.sv']
ALL=CORE+['relay_window_adapter.sv','window_decoder_ctrl.sv','window_effects.sv',
          'window_decoder_top.sv','window_relay_top.sv','window_decoder_vivado_top.sv']


def compile_bench(work,top,names):
    work.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'rtl'/name for name in names]+[ROOT/'sim'/(top+'.sv'),ROOT/'config/qec_paths.svh']
    fingerprint=hashlib.sha256(b''.join(p.read_bytes() for p in paths)).hexdigest()
    cache=work/'fingerprint.txt'; executable=work/'simulator'
    if executable.exists() and cache.exists() and cache.read_text()==fingerprint: return executable
    # GNU Make rejects spaces in its build directory; retain only final outputs here.
    command=['verilator','--binary','--timing','--Wno-fatal','-j','2','--Mdir','obj',
             '--top-module',top,'-o','simulator','--output-split','12000',
             '--replication-limit','16384','-I.']
    command += [p.name for p in paths[:-1]]
    with tempfile.TemporaryDirectory(prefix='qec-vivado-',dir='/tmp') as scratch:
        scratch=Path(scratch)
        for path in paths: shutil.copy2(path,scratch/path.name)
        with (work/'build.log').open('w') as log:
            result=subprocess.run(command,cwd=scratch,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode==0: shutil.copy2(scratch/'obj/simulator',executable)
    if result.returncode:
        raise RuntimeError('Compile failed: '+str(work/'build.log')+'\n'+(work/'build.log').read_text()[-6000:])
    cache.write_text(fingerprint)
    return executable


def simulate(work,top,names,data):
    exe=compile_bench(work,top,names)
    for directory in data:
        for path in directory.glob('*.mem'): shutil.copy2(path,work/path.name)
    result=subprocess.run([str(exe)],cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    print(result.stdout,end='')
    if result.returncode or 'PASS ' not in result.stdout: raise RuntimeError(f'Simulation failed: {work}')


def tcl_check(work):
    work.mkdir(parents=True,exist_ok=True)
    harness=work/'mock_vivado.tcl'
    harness.write_text('''set script [lindex $argv 0]
set argv [lrange $argv 1 end]
proc create_project {name path args} {file mkdir $path}
proc current_project {} {return project}
proc get_filesets {name} {return $name}
proc set_property {args} {}
proc add_files {args} {
 set paths [lindex $args end]
 if {[file isfile $paths]} {return}
 foreach path $paths {if {![file isfile $path]} {error "Missing added file: $path"}}
}
proc update_compile_order {args} {}
proc launch_simulation {args} {puts {MOCK_SIM}}
proc launch_runs {args} {puts {MOCK_SYNTH}}
proc wait_on_run {args} {}
proc get_runs {args} {return synth_1}
proc get_property {args} {return 100%}
proc open_run {args} {}
proc report_utilization {args} {}
proc report_timing_summary {args} {}
proc write_checkpoint {args} {}
source $script
''')
    for sector in ('x_checks','z_checks'):
        for bench in ('window','beta'):
            for action in ('create','sim'):
                project=work/(sector+' '+bench+' '+action)
                command=['tclsh',str(harness),str(ROOT/'create_project.tcl'),'--sector',sector,
                         '--bench',bench,'--action',action,'--out',str(project),'--clock-period-ns','12.5']
                result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                assert result.returncode==0,result.stdout
                header=(project/'generated/qec_paths.svh').read_text()
                assert str(ROOT/'rom'/sector) in header and str(ROOT/'sim/data'/sector) in header
                assert '12.5' in (project/'generated/clock.xdc').read_text()
                repeated=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                assert repeated.returncode!=0 and 'Output already exists' in repeated.stdout
    project=work/'synth'
    result=subprocess.run(['tclsh',str(harness),str(ROOT/'create_project.tcl'),'--action','synth','--out',str(project)],
                          text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert result.returncode==0 and 'MOCK_SYNTH' in result.stdout,result.stdout
    for options in [('--sector','bad'),('--clock-period-ns','0'),('--action','bad')]:
        result=subprocess.run(['tclsh',str(harness),str(ROOT/'create_project.tcl'),*options],
                              text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        assert result.returncode!=0
    print('PASS Tcl syntax/options/path handling with mocked Vivado API (not a Vivado execution)')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['verify','tcl','beta','window','all'],default='all')
    parser.add_argument('--build',type=Path,default=ROOT/'build/local')
    args=parser.parse_args(); build=args.build.resolve()
    verify(ROOT)
    if args.mode in ('tcl','all'): tcl_check(build/'tcl')
    if args.mode in ('beta','all'): simulate(build/'beta','beta_resampling_tb',CORE,[ROOT/'sim/beta'])
    if args.mode in ('window','all'):
        for sector in ('x_checks','z_checks'):
            print('Running packaged window bench:',sector,flush=True)
            simulate(build/'window','window_relay_tb',ALL,[ROOT/'rom'/sector,ROOT/'sim/data'/sector])
