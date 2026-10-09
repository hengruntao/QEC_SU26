"""Verify reuse of the established RTL, not a second BP arithmetic model."""
import argparse
import json
from pathlib import Path
import subprocess
from export_relay_graph import export

ROOT = Path(__file__).resolve().parent
CORE = ROOT.parent/'IBM_OSS_decoder.srcs/sources_1/new'
BASE = '840d6c451bdca80842135cdbbfe5ff89871c26a6'
CORE_FILES = [CORE/n for n in ('cnu_pkg.sv','cnu.sv','vnu.sv','relay_bp_top.sv')]
WINDOW_FILES = [ROOT/n for n in ('relay_window_adapter.sv','window_decoder_ctrl.sv',
                               'window_effects.sv','window_decoder_top.sv','window_relay_top.sv')]


def simulate(directory,source,files):
    directory.mkdir(parents=True,exist_ok=True)
    tb=directory/'tb.sv'
    executable=directory/'obj/Vtb'
    reusable=(tb.exists() and executable.exists() and tb.read_text()==source and
              executable.stat().st_mtime >= max(p.stat().st_mtime for p in files+[tb]))
    if reusable:
        subprocess.run([str(executable)],cwd=directory,check=True,timeout=180)
        return
    tb.write_text(source)
    log=directory/'build.log'
    with log.open('w') as output:
        result=subprocess.run(['verilator','--binary','--timing','--Wno-fatal','-j','2',
            '--top-module','tb','--Mdir',str(directory/'obj'),'--output-split','12000',
            '--replication-limit','16384', *map(str,files),str(tb)],stdout=output,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Compile failed; see {log}\n'+log.read_text()[-6000:])
    subprocess.run([str(directory/'obj/Vtb')],cwd=directory,check=True,timeout=180)


def baseline(repo,name,out):
    content=subprocess.check_output(['git','-C',str(repo),'show',
        f'{BASE}:rtl/IBM_OSS_decoder.srcs/sources_1/new/{name}.sv'],text=True)
    # Rename only module identifiers so both versions can run side by side.
    import re
    for old,new in [('relay_bp_top','baseline_top'),('vnu','baseline_vnu')]:
        content=re.sub(r'\b'+old+r'\b',new,content)
    path=out/('baseline_'+name+'.sv'); path.write_text(content)
    return path


def equivalence(out,repo):
    out.mkdir(parents=True,exist_ok=True)
    old_vnu=baseline(repo,'vnu',out)
    old_top=baseline(repo,'relay_bp_top',out)
    columns=[{'detectors':[]} for _ in range(144)]
    for r in range(72):
        for p in range(6): columns[(2*r+p)%144]['detectors'].append(r)
    export(columns,72,out)
    simulate(out,'''`timescale 1ns/1ps
module tb;
logic clk=0; always #5 clk=~clk;
logic rst_n=0,init=0,en=0,new_leg=0;
logic [3:0] lambda_0=7;
logic [9:0] mu3[3],mu6[6];
wire [4:0] old_nu[3],new_nu[3],wide_nu[6];
wire [4:0] old_m,new_m,wide_m;
wire old_e,new_e,wide_e;
baseline_vnu #(.LFSR_SEED(8'hA5)) original(.clk,.rst_n,.init,.en,.new_leg,.lambda_0,.mu_in(mu3),.nu_out(old_nu),.marginal(old_m),.e_hat(old_e));
vnu #(.LFSR_SEED(8'hA5)) adapted(.clk,.rst_n,.init,.en,.new_leg,.lambda_0,.mu_in(mu3),.nu_out(new_nu),.marginal(new_m),.e_hat(new_e));
vnu #(.DEG(6),.LFSR_SEED(8'hA5)) padded(.clk,.rst_n,.init,.en,.new_leg,.lambda_0,.mu_in(mu6),.nu_out(wide_nu),.marginal(wide_m),.e_hat(wide_e));
logic top_reset=0;
logic [71:0] syndrome=0;
logic [3:0] priors[144];
wire [143:0] old_errors,new_errors;
wire old_done,new_done,old_ok,new_ok;
wire [6:0] old_iter,new_iter;
wire [9:0] old_leg,new_leg_count;
baseline_top #(.T0(3),.Tr(2),.MAX_LEGS(0),.NUM_SOL(3)) legacy(
 .clk,.rst_n(top_reset),.syndrome,.lambda_0(priors),.e_hat(old_errors),.done(old_done),.converged(old_ok),.iter_count(old_iter),.leg_count(old_leg));
relay_bp_top #(.T0(3),.Tr(2),.MAX_LEGS(0),.NUM_SOL(3)) current(
 .clk,.rst_n(top_reset),.syndrome,.lambda_0(priors),.convergence_mask('1),.active_mask('1),
 .e_hat(new_errors),.done(new_done),.converged(new_ok),.iter_count(new_iter),.leg_count(new_leg_count));
initial begin
 for(int j=0;j<144;j++) priors[j]=7;
 for(int p=0;p<3;p++) mu3[p]=0;
 for(int p=0;p<6;p++) mu6[p]=0;
 repeat(2) @(negedge clk); rst_n=1;
 for(int n=0;n<512;n++) begin
  // Compare unchanged behavior; boundary-only sampling is tested separately.
  @(negedge clk); init=n%41==0; en=n%3!=0; new_leg=(n%7==0)&&en; lambda_0=4'($urandom);
  for(int p=0;p<3;p++) begin mu3[p]=10'($urandom); mu6[p]=mu3[p]; end
  @(negedge clk);
  if({old_m,old_e}!=={new_m,new_e} || {old_m,old_e}!=={wide_m,wide_e}) $fatal(1,"VNU output mismatch");
  if(original.lfsr!==adapted.lfsr || original.beta_int!==adapted.beta_int || original.M_j!==adapted.M_j) $fatal(1,"VNU state mismatch");
  if(original.lfsr!==padded.lfsr || original.beta_int!==padded.beta_int || original.M_j!==padded.M_j) $fatal(1,"padded VNU state mismatch");
  for(int p=0;p<3;p++) if(old_nu[p]!==new_nu[p] || old_nu[p]!==wide_nu[p]) $fatal(1,"VNU message mismatch");
 end
 @(negedge clk); init=1; lambda_0=7;
 for(int p=0;p<3;p++) mu6[p]=0;
 for(int p=3;p<6;p++) mu6[p]=10'h055;
 #1; if(padded.M_j_next!==8'sd22) $fatal(1,"extra VN ports ignored");
 for(int n=0;n<8;n++) begin
  top_reset=0; repeat(2) @(negedge clk);
  syndrome=n==0 ? 72'd0 : {8'($urandom),$urandom,$urandom};
  top_reset=1;
  for(int t=0;t<500;t++) begin
   @(negedge clk);
   if({old_errors,old_done,old_ok,old_iter,old_leg}!=={new_errors,new_done,new_ok,new_iter,new_leg_count}) $fatal(1,"top changed at case %d cycle %d",n,t);
  end
 end
 $display("PASS established RTL equivalence: 512 VNU cases, 8 x 500 first-leg core cycles"); $finish;
end
endmodule
''',CORE_FILES+[old_vnu,old_top])


def adapter_test(out):
    columns=[{'detectors':[0]},{'detectors':[1]},{'detectors':[1,2]},
             {'detectors':[2]},{'detectors':[2]}]
    dc,dv=export(columns,4,out)
    for name,value in [('startup',7),('bulk',6)]:
        (out/(name+'.mem')).write_text((f'{value:x}\n')*5)
    simulate(out,f'''`timescale 1ns/1ps
module tb;
logic clk=0; always #5 clk=~clk;
logic rst_n=0,req_valid=0,req_ready,rsp_valid,rsp_ready=0,success,startup_profile=1;
logic [3:0] detectors=0,convergence_mask=7;
logic [4:0] active_mask=31,errors;
logic [6:0] iter_count; logic [9:0] leg_count;
relay_window_adapter #(.D(4),.V(5),.DC({dc}),.DV({dv}),.T0(4),.TR(3),.MAX_LEGS(1),.NUM_SOL(1),
 .IDX_FILE("{out}/cnu_to_vnu_idx.mem"),.PORT_FILE("{out}/cnu_to_vnu_port.mem"),
 .START_PRIOR_FILE("{out}/startup.mem"),.BULK_PRIOR_FILE("{out}/bulk.mem")) dut(.*);
task request(input logic [3:0] s,m,input logic [4:0] a,input logic expected);
begin
 @(negedge clk); detectors=s; convergence_mask=m; active_mask=a; req_valid=1;
 while(!req_ready) @(negedge clk);
 @(negedge clk); req_valid=0; detectors='1; convergence_mask=0; active_mask=0;
 wait(rsp_valid); @(negedge clk);
 if(success!==expected || (errors & ~a)!=0) $fatal(1,"adapter result");
 if(success && ((((errors[0]^s[0])&m[0]) | ((errors[1]^errors[2]^s[1])&m[1]) |
     ((errors[2]^errors[3]^errors[4]^s[2])&m[2]) | (s[3]&m[3])))) $fatal(1,"returned candidate fails requested checks");
 if(success && s==1 && errors!=1) $fatal(1,"single fault not corrected");
 begin
 logic [4:0] held; held=errors;
 repeat(4) begin @(negedge clk); if(!rsp_valid || req_ready || errors!==held || success!==expected) $fatal(1,"held result changed"); end
 end
 rsp_ready=1; @(negedge clk); rsp_ready=0;
end endtask
initial begin
 repeat(2) @(negedge clk); rst_n=1;
 request(0,7,31,1); request(1,7,31,1);
 startup_profile=0; request(0,7,30,1); request(1,7,30,0);
 request(8,15,31,0); request(8,7,31,1);
 @(negedge clk); req_valid=1; @(negedge clk); req_valid=0;
 repeat(3) @(negedge clk); rst_n=0; @(negedge clk); rst_n=1;
 request(1,7,31,1);
 $display("PASS established core adapter: success, failure, masks, inactive columns, backpressure, reset/reuse"); $finish;
end
initial begin #1000000; $fatal(1,"timeout"); end
endmodule
''',CORE_FILES+[ROOT/'relay_window_adapter.sv'])


def pipeline_test(out,full=False,sector='x_checks'):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if full:
        hardware=ROOT/'matrices/generated'/sector/'hardware'
        columns=json.loads((hardware/'columns.json').read_text())
        w,c,m,k=12,8,72,12
    else:
        columns=[{'cycle':0,'detectors':[0,2],'logicals':[0]},
                 {'cycle':0,'detectors':[1],'logicals':[1]},
                 {'cycle':1,'detectors':[2,4],'logicals':[0]},
                 {'cycle':1,'detectors':[3],'logicals':[1]},
                 {'cycle':2,'detectors':[4],'logicals':[0]},
                 {'cycle':2,'detectors':[5],'logicals':[1]}]
        w,c,m,k=3,1,2,2
    v=len(columns); d=w*m
    dc,dv=export(columns,d,out)
    def mem(name,values):
        (out/(name+'.mem')).write_text(''.join(f'{x:x}\n' for x in values))
    cm=sum(1<<j for j,col in enumerate(columns) if col['cycle']<c)
    h=[sum(1<<j for j,col in enumerate(columns) if r in col['detectors']) for r in range(d)]
    a=[sum(1<<j for j,col in enumerate(columns) if r in col['logicals']) for r in range(k)]
    mem('carry',[row&cm for row in h[c*m:(c+1)*m]])
    mem('frame',[row&cm for row in a]); mem('commit',[cm]); mem('convergence',[(1<<(c*m))-1])
    if full:
        for profile in ['startup','bulk']:
            mem(profile+'_active',[int((hardware/(profile+'_active_mask.mem')).read_text(),16)])
    else:
        mem('startup_active',[(1<<v)-1]); mem('bulk_active',[(1<<v)-1])
    mem('h',h)
    # Uniform integer priors are explicit test stimuli, NOT a paper quantizer.
    mem('startup',[7]*v); mem('bulk',[6]*v)
    raw=[0]*(w+2*c)
    for cycle in [0,c]:
        for r in columns[0]['detectors']:
            if cycle+r//m<len(raw): raw[cycle+r//m]^=1<<(r%m)
    mem('raw',raw)
    params=','.join(f'.{param}_FILE("{out}/{name}.mem")' for param,name in
        [('IDX','cnu_to_vnu_idx'),('PORT','cnu_to_vnu_port'),('START_PRIOR','startup'),('BULK_PRIOR','bulk'),
         ('CARRY','carry'),('FRAME','frame'),('COMMIT','commit'),('CONVERGENCE','convergence'),
         ('STARTUP_ACTIVE','startup_active'),('BULK_ACTIVE','bulk_active')])
    simulate(out,f'''`timescale 1ns/1ps
module tb;
localparam W={w},C={c},M={m},V={v},D={d},K={k};
logic clk=0; always #5 clk=~clk;
logic rst_n=0,detector_valid=0,detector_ready,commit_valid,commit_ready=0,commit_success,busy,failed;
logic [M-1:0] detector_data=0,raw[W+2*C],carry=0,next_carry;
logic [K-1:0] commit_frame,logical_frame,frame=0,delta;
logic [31:0] window_start;
logic [6:0] iter_count; logic [9:0] leg_count;
logic [V-1:0] h[D],a[K],carry_rows[M],committed,cm[1];
logic [D-1:0] expected_window;
integer requests=0,nonzero=0;
window_relay_top #(.W(W),.C(C),.M(M),.K(K),.N_ERRORS(V),.DC({dc}),.DV({dv}),
 .T0(8),.TR(6),.MAX_LEGS(1),.NUM_SOL(1),{params}) dut(.*);
always @(posedge clk) if(rst_n && dut.decode_req_valid && dut.decode_req_ready) begin
 expected_window='0;
 for(int r=0;r<W;r++) expected_window[r*M+:M]=raw[requests*C+r];
 expected_window[0+:M]^=carry;
 if(dut.decode_detectors!==expected_window) $fatal(1,"window/carry request mismatch");
 if(dut.startup_profile !== (requests==0)) $fatal(1,"profile transition");
 requests++;
end
initial begin
 $readmemh("{out}/raw.mem",raw); $readmemh("{out}/h.mem",h);
 $readmemh("{out}/frame.mem",a); $readmemh("{out}/carry.mem",carry_rows); $readmemh("{out}/commit.mem",cm);
 repeat(2) @(negedge clk); rst_n=1;
 for(int win=0;win<3;win++) begin
  for(int r=(win==0 ? 0 : W+(win-1)*C);r<W+win*C;r++) begin
   @(negedge clk); detector_data=raw[r]; detector_valid=1;
   while(!detector_ready) @(negedge clk);
   @(negedge clk); detector_valid=0;
  end
  wait(dut.decode_rsp_valid); @(negedge clk);
  if(!dut.decode_success) $fatal(1,"integration fixture failed decoding win %d",win);
  for(int r=0;r<C*M;r++) if((^(h[r]&dut.decode_errors))!==expected_window[r]) $fatal(1,"correction fails checks");
  if(dut.decode_errors!=0) nonzero++;
  committed=dut.decode_errors & cm[0]; delta=0; next_carry=0;
  for(int r=0;r<K;r++) delta[r]=^(a[r]&committed);
  for(int r=0;r<M;r++) next_carry[r]=^(carry_rows[r]&committed);
  frame^=delta;
  wait(commit_valid); @(negedge clk);
  repeat(4) begin
   if(!commit_valid || !commit_success || commit_frame!==frame) $fatal(1,"commit mismatch");
   @(negedge clk);
  end
  commit_ready=1; @(negedge clk); commit_ready=0; carry=next_carry;
  if(window_start!=(win+1)*C || logical_frame!==frame || failed) $fatal(1,"window advance mismatch");
 end
 if(nonzero==0) $fatal(1,"no nonzero correction exercised");
 $display("PASS connected established core: V=%d, three windows, corrections/frame/carry, held commits",V); $finish;
end
initial begin #100000000; $fatal(1,"timeout"); end
endmodule
''',CORE_FILES+WINDOW_FILES)


def beta_test(out):
    out.mkdir(parents=True,exist_ok=True)
    (out/'cnu_to_vnu_idx.mem').write_text('0\n1\n')
    (out/'cnu_to_vnu_port.mem').write_text('0\n0\n')
    # Keep the focused bench usable in both Verilator and Vivado.
    bench=(ROOT/'beta_resampling_tb.sv').read_text().replace('module beta_resampling_tb;', 'module tb;')
    simulate(out,bench,CORE_FILES)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',type=Path,default=Path('/tmp/qec-established-tests'))
    parser.add_argument('--baseline-repo',type=Path,default=ROOT.parent.parent)
    parser.add_argument('--only',choices=['equivalence','beta','adapter','pipeline','full'])
    args=parser.parse_args()
    args.build=args.build.resolve()
    if args.only in [None,'equivalence']: equivalence(args.build/'equivalence',args.baseline_repo)
    if args.only in [None,'beta']: beta_test(args.build/'beta')
    if args.only in [None,'adapter']: adapter_test(args.build/'adapter')
    if args.only in [None,'pipeline']: pipeline_test(args.build/'pipeline')
    if args.only=='full':
        for sector in ['x_checks','z_checks']:
            print('Testing full established hierarchy:',sector,flush=True)
            pipeline_test(args.build/'full',full=True,sector=sector)


if __name__=='__main__': main()
