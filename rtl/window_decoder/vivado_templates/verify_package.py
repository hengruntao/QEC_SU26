"""Validate packaged hashes, adjacency, priors, effects and portable test vectors."""
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return [int(word,16) for word in path.read_text().split()]


def verify(root):
    manifest=json.loads((root/'manifest.json').read_text())
    for relative,expected in manifest['files'].items():
        path=root/relative
        assert path.is_file(), f'Missing package file: {relative}'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected, f'Changed package file: {relative}'
    for relative,source in manifest['canonical_rtl'].items():
        assert manifest['files'][relative]==source['sha256'], f'RTL snapshot mismatch: {relative}'
        canonical=root.parent.parent/source['canonical']
        if canonical.is_file():
            assert hashlib.sha256(canonical.read_bytes()).hexdigest()==source['sha256'], f'Canonical RTL changed: {canonical}; regenerate package'
    for sector,info in manifest['sectors'].items():
        rom=root/'rom'/sector; refs=root/'sim/data'/sector
        provenance=root/'provenance'/sector
        columns=json.loads((provenance/'columns.json').read_text())
        profiles=json.loads((provenance/'profiles.json').read_text())
        dims=info['dimensions']; w,c,m,k,v,dc,dv=[dims[n] for n in ('W','C','M','K','N_ERRORS','CN_DEG','VN_DEG')]
        assert len(columns)==v
        idx,port=read(rom/'cnu_to_vnu_idx.mem'),read(rom/'cnu_to_vnu_port.mem')
        assert len(idx)==len(port)==w*m*dc
        recovered=[[] for _ in columns]; variable_ports=[[] for _ in columns]; owned=set()
        for e,(j,p) in enumerate(zip(idx,port)):
            assert 0<=j<=v and 0<=p<dv
            if j==v:
                assert p==0
                continue
            assert (j,p) not in owned, 'Duplicate variable-port owner'
            owned.add((j,p)); recovered[j].append(e//dc); variable_ports[j].append(p)
        assert recovered==[sorted(col['detectors']) for col in columns]
        for j,col in enumerate(columns):
            assert sorted(variable_ports[j])==list(range(len(col['detectors'])))
        for profile,data in profiles.items():
            active=int(data['active_mask_hex'],16)
            assert read(rom/(profile+'_active_mask.mem'))==[active]
            priors=read(rom/(profile+'_prior.mem'))
            assert len(priors)==len(data['priors'])==v and active>>v==0
            for j,(p,value) in enumerate(zip(data['priors'],priors)):
                assert 0<=value<=15
                if (active>>j)&1:
                    assert 0<p<0.5 and value==min(round(2*math.log((1-p)/p)),15)
                else:
                    assert p==0 and value==0
        h=[sum(1<<j for j,col in enumerate(columns) if r in col['detectors']) for r in range(w*m)]
        a=[sum(1<<j for j,col in enumerate(columns) if r in col['logicals']) for r in range(k)]
        commit=sum(1<<j for j,col in enumerate(columns) if col['cycle']<c)
        assert read(rom/'commit_mask.mem')==read(refs/'commit_reference.mem')==[commit]
        assert read(rom/'convergence_mask.mem')==[(1<<(c*m))-1]
        assert read(refs/'h_reference.mem')==h and read(refs/'a_reference.mem')==a
        assert read(rom/'frame_rows.mem')==[row&commit for row in a]
        assert read(rom/'carry_rows.mem')==read(refs/'carry_reference.mem')==[row&commit for row in h[c*m:(c+1)*m]]
        fixture=json.loads((refs/'fixture.json').read_text()); raw=[0]*(w+2*c)
        col=columns[fixture['source_column']]
        for offset in fixture['injection_offsets']:
            for r in col['detectors']+col['boundary_detectors']:
                cycle,bit=divmod(offset*m+r,m)
                if cycle<len(raw): raw[cycle]^=1<<bit
        assert read(refs/'detectors.mem')==raw
        assert read(refs/'raw_windows.mem')==[sum(raw[n*c+r]<<(r*m) for r in range(w)) for n in range(3)]
        assert read(refs/'expected_window_start.mem')==[c,2*c,3*c]
        assert read(refs/'expected_success.mem')==[1,1,1]
        print(f'PASS {sector}: graph, priors, effects, vectors; {v} faults, max degrees {dc}/{dv}')
    print(f'PASS package: {len(manifest["files"])} hashed files, {len(manifest["canonical_rtl"])} exact canonical RTL copies')
    return manifest


if __name__=='__main__':
    verify(Path(__file__).resolve().parent)
