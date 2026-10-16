"""Audit IBM matrix ordering against a pinned X-memory Stim circuit.

Derive an explicit earliest-detector ownership policy, not an author-supplied mask.
Never modify or reorder the IBM matrices or the handwritten RTL.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import numpy as np
import stim
from matrix_io import N_FAULTS, N_CHECKS, N_LOGICAL, M, sha256, sparse_entries


def decoder_blocks(circuit):
    records, groups, detectors = [], [], []
    for op in circuit.flattened():
        if op.name in ('M','MX'):
            group = len(groups)
            qubits = [t.value for t in op.targets_copy()]
            groups.append((op.name,qubits))
            records.extend((op.name,group,q) for q in qubits)
        elif op.name == 'DETECTOR':
            if any(not t.is_measurement_record_target for t in op.targets_copy()):
                raise ValueError('Non-record detector unsupported')
            detectors.append([records[len(records)+t.value] for t in op.targets_copy()])
        elif op.num_measurements:
            raise ValueError(f'Unsupported measurement: {op.name}')
    if groups[-1][0] != 'MX' or len(groups[-1][1]) != 144:
        raise ValueError('Expected X-memory final 144-qubit MX readout')
    final_qubits = set(groups[-1][1])
    by_group = defaultdict(list)
    for d,support in enumerate(detectors):
        if {x[0] for x in support} == {'MX'}:
            by_group[max(x[1] for x in support)].append(d)
    blocks = [ids for _,ids in sorted(by_group.items())]
    if len(blocks) != 13 or any(len(ids) != M for ids in blocks):
        raise ValueError('Expected 12 syndrome blocks and final-codeword block')
    anchors = []
    for block in blocks:
        row_anchors = []
        for d in block:
            ancilla = {q for _,_,q in detectors[d] if q not in final_qubits}
            if len(ancilla) != 1:
                raise ValueError('Detector lacks unique syndrome-ancilla identity')
            row_anchors.append(next(iter(ancilla)))
        anchors.append(row_anchors)
    if len(set(anchors[0])) != M or any(x != anchors[0] for x in anchors):
        raise ValueError('Row identity changes between detector blocks')
    if any(max(g for _,g,_ in detectors[d]) != len(groups)-1 for d in blocks[-1]):
        raise ValueError('Last block is not the final data-readout boundary')
    return blocks,anchors[0]


def independent_basis(rows, coefficient_offset=0, initial=None):
    basis = {} if initial is None else dict(initial)
    for i,row in enumerate(rows):
        coefficient = 1 << (coefficient_offset+i)
        while row:
            pivot = row.bit_length()-1
            if pivot not in basis:
                basis[pivot] = (row,coefficient)
                break
            old,old_coefficient = basis[pivot]
            row ^= old
            coefficient ^= old_coefficient
    return basis


def audit(data, circuit_path, c, output):
    if not 1 <= c < 12:
        raise ValueError('Initial 12-syndrome-cycle configuration requires 1 <= C < 12')
    data,output = Path(data),Path(output)
    h_path,a_path = data/'144_12_12_Hdec.npz',data/'144_12_12_Adec.npz'
    provenance = json.loads((data/'provenance.json').read_text())
    for path in (h_path,a_path):
        if sha256(path) != provenance['files'][path.name]:
            raise ValueError('IBM archive differs from pinned provenance')
    h = sparse_entries(h_path,(N_CHECKS,N_FAULTS))
    a = sparse_entries(a_path,(N_LOGICAL,N_FAULTS))
    hc,ac = [set() for _ in range(N_FAULTS)],[set() for _ in range(N_FAULTS)]
    hrows,arows = [0]*N_CHECKS,[0]*N_LOGICAL
    for r,j in h: hc[j].add(r); hrows[r] |= 1<<j
    for r,j in a: ac[j].add(r); arows[r] |= 1<<j
    nulls = [j for j in range(N_FAULTS) if not hc[j] and not ac[j]]
    empty_rows = [r for r,row in enumerate(hrows) if not row]
    if nulls != [8784] or empty_rows != list(range(936,1008)):
        raise ValueError('Unexpected dummy column or empty-row pattern')
    if any(not ds for j,ds in enumerate(hc) if j not in nulls):
        raise ValueError('Logical-only fault requires explicit ownership')
    if any(max(ds)//M-min(ds)//M > 1 for ds in hc if ds):
        raise ValueError('A fault spans more than adjacent cycles; one-cycle carry is insufficient')

    circuit = stim.Circuit.from_file(circuit_path)
    blocks,ancillas = decoder_blocks(circuit)
    row_map = {d:t*M+r for t,block in enumerate(blocks) for r,d in enumerate(block)}
    signatures = defaultdict(set)
    for op in circuit.detector_error_model(decompose_errors=False).flattened():
        if op.type != 'error': continue
        ds,ls = set(),set()
        for target in op.targets_copy():
            if target.is_separator(): raise ValueError('Unexpected decomposed error')
            if target.is_relative_detector_id() and target.val in row_map:
                ds.symmetric_difference_update([row_map[target.val]])
            elif target.is_logical_observable_id():
                ls.symmetric_difference_update([target.val])
        if ds or ls: signatures[tuple(sorted(ds))].add(tuple(sorted(ls)))
    if any(len(values) != 1 for values in signatures.values()):
        raise ValueError('Same detector signature has incompatible logical actions')
    lookup = {tuple(sorted(ds)):j for j,ds in enumerate(hc) if ds}
    if len(lookup) != 8784 or set(lookup) != set(signatures):
        raise ValueError('Stim and IBM H signatures do not match one-to-one')
    stim_a = [0]*N_LOGICAL
    for ds,values in signatures.items():
        j = lookup[ds]
        for r in next(iter(values)): stim_a[r] |= 1<<j

    # Prove A_IBM = T*A_Stim + G*H exactly, for every fault column.
    hbasis = independent_basis(hrows)
    combined = independent_basis(stim_a,N_CHECKS,hbasis)
    transforms,logical_masks = [],[]
    for r,value in enumerate(arows):
        residual,coefficient = value,0
        while residual:
            pivot = residual.bit_length()-1
            if pivot not in combined:
                raise ValueError(f'IBM logical row {r} is outside Stim logical/syndrome span')
            old,old_coefficient = combined[pivot]
            residual ^= old
            coefficient ^= old_coefficient
        logical = [i for i in range(N_LOGICAL) if coefficient>>(N_CHECKS+i)&1]
        gauge = [i for i in range(N_CHECKS) if coefficient>>i&1]
        reconstruction = 0
        for i in logical: reconstruction ^= stim_a[i]
        for i in gauge: reconstruction ^= hrows[i]
        if reconstruction != value: raise ValueError('Logical transformation proof failed')
        logical_masks.append(sum(1<<i for i in logical))
        transforms.append(dict(ibm_row=r,stim_logical_rows=logical,syndrome_gauge_rows=gauge))
    transform_rank = len(independent_basis(logical_masks))
    if transform_rank != 12:
        raise ValueError('Logical basis transform is not invertible')

    # Explicit policy: own each nonempty column at its earliest detector block.
    owners = [min(ds)//M if ds else -1 for ds in hc]
    mask = np.array([0 <= t < c for t in owners],dtype=np.uint8)
    selected = set(np.flatnonzero(mask).tolist())
    for j in selected:
        if any(r >= (c+1)*M for r in hc[j]):
            raise ValueError('Committed correction leaks beyond the carry block')
    for j in range(N_FAULTS):
        if j not in selected and any(r<c*M for r in hc[j]):
            raise ValueError('Uncommitted fault touches committed checks')
    carry_columns = sorted(j for j in selected if any(c*M <= r < (c+1)*M for r in hc[j]))
    carry_weights = [sum(j in selected for r,j in h if r==c*M+i) for i in range(M)]
    report = dict(schema=1,commit_cycles=c,detectors_per_cycle=M,
        source=dict(repository=provenance['repository'],commit=provenance['commit'],
                    H_sha256=sha256(h_path),A_sha256=sha256(a_path),
                    circuit_file=Path(circuit_path).name,circuit_sha256=sha256(circuit_path),stim_version=stim.__version__),
        active_row_blocks=[dict(block=i,row_start=i*M,row_stop=(i+1)*M,
            kind='syndrome' if i<12 else 'final_codeword_boundary',stim_detector_ids=block) for i,block in enumerate(blocks)],
        syndrome_ancilla_order=ancillas,empty_rows=empty_rows,null_fault_columns=nulls,
        ownership_rule='m_com[j]=1 iff H column j touches a row < C*M (earliest-detector ownership)',
        ownership_status='Derived and algebraically checked policy; not an author-exported commit mask',
        fault_owner_counts=dict(sorted(Counter(owners).items())),
        committed_faults=len(selected),carry_unique_columns=len(carry_columns),
        carry_columns=carry_columns,carry_row_weights=carry_weights,
        frame_row_weights=[sum(j in selected for rr,j in a if rr==r) for r in range(12)],
        H_stim_exact_signature_matches=len(lookup),H_rank=len(hbasis),
        logical_transform_rank=transform_rank,logical_transform=transforms,
        logical_equivalence='A_IBM = T*A_Stim + G*H, T invertible; raw frame labels are not interchangeable',
        integration_warning='The matching circuit is finite memory with a final readout. Bulk/startup reuse and window-to-window logical gauge must be validated separately; not proof of a continuous decoder.')
    output.mkdir(parents=True,exist_ok=True)
    np.save(output/'commit_mask.npy',mask)
    report['commit_mask_sha256'] = sha256(output/'commit_mask.npy')
    (output/'mapping_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS H: {len(lookup)} Stim signatures; 13 active blocks, one empty block, one null fault')
    print('PASS A: exact invertible logical-basis/syndrome-gauge relation; IBM A preserved')
    print(f'C={c}: {len(selected)} committed faults; {len(carry_columns)} carry columns; row weights {sorted(set(carry_weights))}')
    print('Derived ownership policy, not author mask or continuous-window verification.')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=Path(__file__).parent/'data/ibm')
    parser.add_argument('--circuit',type=Path,required=True)
    parser.add_argument('--commit-cycles',type=int,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'configuration/c8')
    args=parser.parse_args()
    audit(args.data,args.circuit,args.commit_cycles,args.output)
