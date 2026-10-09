"""Build a self-contained Vivado artifact from the established RTL and matrices."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from export_relay_graph import export

ROOT=Path(__file__).resolve().parent
CORE=ROOT.parent/'IBM_OSS_decoder.srcs/sources_1/new'
TEMPLATES=ROOT/'vivado_templates'
CORE_NAMES=('cnu_pkg.sv','cnu.sv','vnu.sv','relay_bp_top.sv')
WINDOW_NAMES=('relay_window_adapter.sv','window_decoder_ctrl.sv','window_effects.sv',
              'window_decoder_top.sv','window_relay_top.sv')
EFFECT_NAMES=('carry_rows','frame_rows','commit_mask','convergence_mask',
              'startup_active_mask','bulk_active_mask')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mem(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(f'{int(value):x}\n' for value in values))


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def quantize(probability,active):
    if not active:
        if probability!=0: raise ValueError('Inactive fault has a nonzero probability')
        return 0
    if not 0<probability<0.5: raise ValueError('Active prior must have 0 < p < 0.5')
    # Same scale, Python round behavior and saturation as iterations_bp.py.
    return min(round(2*math.log((1-probability)/probability)),15)


def build(output):
    if output.exists(): raise ValueError(f'Output already exists: {output}; use verify_package.py to check it, or choose a fresh --output')
    output.mkdir(parents=True)
    sources={}
    for directory,names,relative in [(CORE,CORE_NAMES,'rtl/IBM_OSS_decoder.srcs/sources_1/new'),
                                     (ROOT,WINDOW_NAMES,'rtl/window_decoder')]:
        for name in names:
            dest=output/'rtl'/name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(directory/name,dest)
            sources[str(dest.relative_to(output))]={'canonical':relative+'/'+name,'sha256':digest(directory/name)}
    mapping={'window_decoder_vivado_top.sv':'rtl/window_decoder_vivado_top.sv',
             'qec_paths.svh':'config/qec_paths.svh','window_relay_tb.sv':'sim/window_relay_tb.sv',
             'create_project.tcl':'create_project.tcl','README.md':'README.md',
             'verify_package.py':'verify_package.py','test_package.py':'test_package.py'}
    for name,relative in mapping.items():
        dest=output/relative; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(TEMPLATES/name,dest)
    beta=(ROOT/'beta_resampling_tb.sv').read_text()
    beta=beta.replace('`timescale 1ns/1ps','`timescale 1ns/1ps\n`include "qec_paths.svh"',1)
    beta=beta.replace('.VN_DEG(1),.WINDOW_MODE(1))',
        '.VN_DEG(1),.WINDOW_MODE(1),\n        .IDX_FILE({`QEC_BETA_DIR,"/cnu_to_vnu_idx.mem"}),\n        .PORT_FILE({`QEC_BETA_DIR,"/cnu_to_vnu_port.mem"}))')
    (output/'sim/beta_resampling_tb.sv').write_text(beta)
    mem(output/'sim/beta/cnu_to_vnu_idx.mem',[0,1]); mem(output/'sim/beta/cnu_to_vnu_port.mem',[0,0])
    (output/'constraints').mkdir()
    (output/'constraints/clock.xdc').write_text('# Starter 100 MHz target; project script generates the selected period.\ncreate_clock -name clk -period 10.0 [get_ports clk]\n')
    sectors={}
    for sector in ('x_checks','z_checks'):
        hardware=ROOT/'matrices/generated'/sector/'hardware'
        columns=json.loads((hardware/'columns.json').read_text())
        profiles=json.loads((hardware/'profiles.json').read_text())
        matrix_manifest=json.loads((hardware/'manifest.json').read_text())
        w,c,m,k,v=[matrix_manifest[key] for key in ('W','C','M','K','N_ERRORS')]
        if (w,c,m,k,v)!=(12,8,72,12,8640): raise ValueError('Package wrapper requires the documented default dimensions')
        rom=output/'rom'/sector; dc,dv=export(columns,w*m,rom)
        if (dc,dv)!=(35,6): raise ValueError('Unexpected graph degrees')
        for name in EFFECT_NAMES: shutil.copy2(hardware/(name+'.mem'),rom/(name+'.mem'))
        stats={}
        for profile,data in profiles.items():
            active=int(data['active_mask_hex'],16)
            probabilities=data['priors']
            if len(probabilities)!=v or active>>v: raise ValueError('Prior dimensions do not match graph')
            table=[quantize(p,bool((active>>j)&1)) for j,p in enumerate(probabilities)]
            mem(rom/(profile+'_prior.mem'),table)
            values=[table[j] for j in range(v) if (active>>j)&1]
            stats[profile]={'active_faults':len(values),'min':min(values),'max':max(values),
                            'counts':{str(value):values.count(value) for value in sorted(set(values))}}
        provenance=output/'provenance'/sector; provenance.mkdir(parents=True)
        for source,dest in [('columns.json','columns.json'),('profiles.json','profiles.json'),('manifest.json','matrix_manifest.json')]:
            shutil.copy2(hardware/source,provenance/dest)
        # Independent sparse-column reference products for the packaged bench.
        h=[sum(1<<j for j,col in enumerate(columns) if r in col['detectors']) for r in range(w*m)]
        a=[sum(1<<j for j,col in enumerate(columns) if r in col['logicals']) for r in range(k)]
        commit=sum(1<<j for j,col in enumerate(columns) if col['cycle']<c)
        refs=output/'sim/data'/sector
        mem(refs/'h_reference.mem',h); mem(refs/'a_reference.mem',a)
        mem(refs/'carry_reference.mem',[row&commit for row in h[c*m:(c+1)*m]])
        mem(refs/'commit_reference.mem',[commit])
        # Select a real startup mechanism. Inject it twice in the retained stream.
        active=int(profiles['startup']['active_mask_hex'],16)
        j=next(j for j,col in enumerate(columns) if col['cycle']==0 and col['detectors'] and (active>>j)&1)
        raw=[0]*(w+2*c)
        for offset in (0,c):
            for detector in columns[j]['detectors']+columns[j]['boundary_detectors']:
                cycle,bit=divmod(offset*m+detector,m)
                if cycle<len(raw): raw[cycle]^=1<<bit
        mem(refs/'detectors.mem',raw)
        mem(refs/'raw_windows.mem',[sum(raw[n*c+r]<<(r*m) for r in range(w)) for n in range(3)])
        mem(refs/'expected_success.mem',[1]*3)
        mem(refs/'expected_window_start.mem',[(n+1)*c for n in range(3)])
        dump(refs/'fixture.json',{'windows':3,'source_column':j,'injection_offsets':[0,c],
             'detector_support':columns[j]['detectors'],'note':'Sparse directed smoke test, not an error-rate benchmark; decoded faults may be degenerate.'})
        sectors[sector]={'dimensions':dict(W=w,C=c,M=m,K=k,N_ERRORS=v,CN_DEG=dc,VN_DEG=dv),
                         'prior_statistics':stats,'matrix_status':matrix_manifest['status'],
                         'source_circuit':matrix_manifest['source_circuit'],'source_sha256':matrix_manifest['source_sha256']}
    parts={option.get('Val') for option in ET.parse(ROOT.parent/'IBM_OSS_decoder.xpr').iter('Option') if option.get('Name')=='Part'}
    if len(parts)!=1: raise ValueError('Existing project part is ambiguous')
    part=parts.pop()
    script=output/'create_project.tcl'
    script.write_text(script.read_text().replace('xc7s50csga324-1',part))
    (output/'.gitignore').write_text('build/\n__pycache__/\n.Xil/\n*.jou\n*.log\n')
    manifest={'schema_version':1,'generator':'QEC_SU26/rtl/window_decoder/build_vivado_package.py',
        'rtl_top':'window_decoder_vivado_top','simulation_top':'window_relay_tb',
        'default_part':part,'part_source':'rtl/IBM_OSS_decoder.xpr',
        'clock_period_ns':10.0,'clock_status':'starter target; no existing board clock constraint was found',
        'hardware_budgets':dict(T0=80,TR=60,MAX_LEGS=600,NUM_SOL=5),
        'smoke_budgets':dict(T0=8,TR=6,MAX_LEGS=1,NUM_SOL=3),
        'prior_rule':'min(round(2*log((1-p)/p)),15); Python round; inactive -> 0',
        'prior_rule_source':'python_implementation/integrated_cnu_vnu/iterations_bp.py:52',
        'sectors':sectors,'canonical_rtl':sources,
        'limitations':['No final-codeword/END/FIFO handling','Inherited seed wrapping/zero seeds and solution-count stop convention are unchanged','No FPGA fit or timing claim; no Vivado execution on this host'],
        'files':{str(path.relative_to(output)):digest(path) for path in sorted(output.rglob('*')) if path.is_file()}}
    dump(output/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT.parent.parent/'vivado/window_decoder')
    args=parser.parse_args()
    result=build(args.output.resolve())
    print('Created:',args.output.resolve())
    for name,data in result['sectors'].items(): print(name,data['prior_statistics'])
