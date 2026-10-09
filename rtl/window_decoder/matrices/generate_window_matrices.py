"""Generate split-sector window matrices from the checked Relay gross circuits.

This uses Stim DEM mechanisms, merged only when their sector detector AND
logical signatures agree. It is an independent construction of Algorithm 2's
inputs, not an export of the paper authors' private FPGA configuration.
"""

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import stim


def parity_set(values):
    result = set()
    for value in values:
        result.symmetric_difference_update((value,))
    return tuple(sorted(result))


def packed(indices):
    return sum(1 << i for i in indices)


def parse_readout(circuit, basis):
    """Use measurement-record dependencies, not coordinates, to identify cycles."""
    records, detectors, observables = [], [], defaultdict(list)
    measurement_groups = []
    for instruction in circuit.flattened():
        if instruction.name in ("M", "MX"):
            group = len(measurement_groups)
            qubits = [t.value for t in instruction.targets_copy()]
            measurement_groups.append((instruction.name, qubits))
            records.extend((instruction.name, group, q) for q in qubits)
        elif instruction.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            targets = instruction.targets_copy()
            if any(not t.is_measurement_record_target for t in targets):
                raise ValueError("Unsupported non-record detector/observable target")
            support = [records[len(records) + t.value] for t in targets]
            if instruction.name == "DETECTOR":
                detectors.append(support)
            else:
                observables[int(instruction.gate_args_copy()[0])].extend(support)
        elif instruction.num_measurements:
            raise ValueError(f"Unsupported measurement operation: {instruction.name}")

    expected_basis = "MX" if basis == "X" else "M"
    final_group = len(measurement_groups) - 1
    if measurement_groups[final_group][0] != expected_basis:
        raise ValueError("Final readout basis does not match requested sector")
    data_qubits = sorted(measurement_groups[final_group][1])
    if len(data_qubits) != 144 or len(set(data_qubits)) != 144:
        raise ValueError("Expected 144 distinct final data-qubit measurements")
    data_index = {q: i for i, q in enumerate(data_qubits)}
    groups = defaultdict(list)
    for detector_id, support in enumerate(detectors):
        bases = {b for b, _, _ in support}
        if len(bases) != 1:
            raise ValueError("Cannot split a detector with mixed measurement bases")
        if bases != {expected_basis}:
            continue
        latest = max(g for _, g, _ in support)
        groups[latest].append(detector_id)
    blocks = [ids for _, ids in sorted(groups.items())]
    if len(blocks) < 4 or any(len(ids) != 72 for ids in blocks):
        raise ValueError("Expected uniform 72-detector sector cycles")

    # Verify row identity across cycles via their syndrome-ancilla qubit.
    anchors = []
    for ids in blocks:
        anchor = []
        for detector_id in ids:
            ancillas = {q for _, _, q in detectors[detector_id] if q not in data_index}
            if len(ancillas) != 1:
                raise ValueError("Detector must reference one syndrome ancilla")
            anchor.append(next(iter(ancillas)))
        anchors.append(anchor)
    if len(set(anchors[0])) != 72 or any(a != anchors[0] for a in anchors):
        raise ValueError("Syndrome row ordering changes across rounds")
    if any(max(g for _, g, _ in detectors[d]) != final_group for d in blocks[-1]):
        raise ValueError("Last sector block is not final-codeword boundary")

    h_hat = []
    for detector_id in blocks[-1]:
        support = detectors[detector_id]
        h_hat.append(parity_set(data_index[q] for _, g, q in support if g == final_group))
    logical_readout = []
    for observable in range(circuit.num_observables):
        support = observables[observable]
        if any(g != final_group for _, g, _ in support):
            raise ValueError("Logical readout involves non-final measurements")
        logical_readout.append(parity_set(data_index[q] for _, _, q in support))
    if circuit.num_observables != 12 or any(len(row) != 6 for row in h_hat):
        raise ValueError("Expected gross-code check weights and logical count")
    return {
        "blocks": blocks, "data_qubits": data_qubits,
        "final_measurement_qubits": measurement_groups[final_group][1],
        "syndrome_ancillas": anchors[0], "h_hat": h_hat,
        "logical_readout": logical_readout,
    }


def extract_templates(circuit, readout):
    row_map = {d: t * 72 + i for t, ids in enumerate(readout["blocks"])
               for i, d in enumerate(ids)}
    templates = defaultdict(dict)
    raw_mapping = {}
    dem = circuit.detector_error_model(decompose_errors=False).flattened()
    error_id = 0
    for instruction in dem:
        if instruction.type != "error":
            continue
        targets = instruction.targets_copy()
        if any(t.is_separator() for t in targets):
            raise ValueError("Expected undecomposed DEM mechanisms")
        ds = parity_set(row_map[t.val] for t in targets
                        if t.is_relative_detector_id() and t.val in row_map)
        ls = parity_set(t.val for t in targets if t.is_logical_observable_id())
        if not ds:
            if ls:
                raise ValueError("Undetectable logical mechanism needs explicit window ownership")
            error_id += 1
            continue
        cycle = ds[0] // 72
        relative_ds = tuple(d - cycle * 72 for d in ds)
        if relative_ds[-1] >= 144:
            raise ValueError("Fault spans more than adjacent cycles: one-cycle carry insufficient")
        key = (relative_ds, ls)
        probability = instruction.args_copy()[0]
        if not 0 <= probability <= 1:
            raise ValueError("Invalid error prior")
        entry = templates[cycle].setdefault(key, {"probability": 0.0, "source_errors": []})
        # XOR of independent equivalent DEM mechanisms, not a sum of priors.
        old = entry["probability"]
        entry["probability"] = old + probability - 2 * old * probability
        entry["source_errors"].append(error_id)
        raw_mapping[error_id] = (cycle, key)
        error_id += 1

    # A finite memory circuit has initialization and final-readout boundaries.
    # Infer a bulk template only if all non-boundary anchor cycles agree.
    last_regular = len(readout["blocks"]) - 2
    bulk = templates[1]
    for cycle in range(2, last_regular):
        candidate = templates[cycle]
        if candidate.keys() != bulk.keys() or any(
            not math.isclose(v["probability"], candidate[k]["probability"],
                             rel_tol=1e-12, abs_tol=1e-15)
            for k, v in bulk.items()
        ):
            raise ValueError(f"Circuit is not stationary in interior cycle {cycle}")
    return dem, templates, raw_mapping, last_regular


def build_window(templates, width, profile):
    columns = []
    for cycle in range(width):
        template_cycle = cycle if profile == "startup" else 1
        for template_column, ((ds, ls), entry) in enumerate(sorted(templates[template_cycle].items())):
            full_ds = [cycle * 72 + d for d in ds]
            columns.append({
                "cycle": cycle, "template_cycle": template_cycle,
                "template_column": template_column,
                "detectors": [d for d in full_ds if d < width * 72],
                "boundary_detectors": [d for d in full_ds if d >= width * 72],
                "logicals": list(ls), "probability": entry["probability"],
            })
    if any(not col["detectors"] for col in columns):
        raise ValueError("Unexpected column invisible inside window")
    return columns


def matrix_rows(columns, field, count):
    rows = [0] * count
    for j, column in enumerate(columns):
        for i in column[field]:
            rows[i] |= 1 << j
    return rows


def masks(columns, width, commit):
    if not 1 <= commit < width:
        raise ValueError("Commit width must satisfy 1 <= C < W")
    commit_mask = packed(j for j, col in enumerate(columns) if col["cycle"] < commit)
    convergence_mask = (1 << (commit * 72)) - 1
    for j, col in enumerate(columns):
        touches_committed = any(d < commit * 72 for d in col["detectors"])
        if touches_committed != bool(commit_mask & (1 << j)):
            raise ValueError("Commit mask does not cover exactly the committed detector region")
        if touches_committed and any(d >= (commit + 1) * 72
                                     for d in col["detectors"] + col["boundary_detectors"]):
            raise ValueError("Committed correction leaks beyond the single carry cycle")
    return commit_mask, convergence_mask


def write_mem(path, values, bits):
    digits = (bits + 3) // 4
    path.write_text("".join(f"{value:0{digits}x}\n" for value in values), encoding="ascii")


def export_profile(destination, circuit_path, circuit, readout, templates, width, commit, profile, basis):
    columns = build_window(templates, width, profile)
    h = matrix_rows(columns, "detectors", width * 72)
    a = matrix_rows(columns, "logicals", 12)
    cm, cvg = masks(columns, width, commit)
    destination.mkdir(parents=True, exist_ok=True)
    n = len(columns)
    write_mem(destination / "h_tilde_rows.mem", h, n)
    write_mem(destination / "a_tilde_rows.mem", a, n)
    write_mem(destination / "carry_rows.mem", [r & cm for r in h[commit*72:(commit+1)*72]], n)
    write_mem(destination / "frame_rows.mem", [r & cm for r in a], n)
    write_mem(destination / "h_hat_rows.mem", [packed(r) for r in readout["h_hat"]], 144)
    write_mem(destination / "logical_readout_rows.mem", [packed(r) for r in readout["logical_readout"]], 144)
    write_mem(destination / "commit_mask.mem", [cm], n)
    write_mem(destination / "convergence_mask.mem", [cvg], width * 72)
    all_masks = {}
    for stride in range(1, width):
        error_mask, detector_mask = masks(columns, width, stride)
        all_masks[str(stride)] = {"commit_mask_hex": format(error_mask, "x"),
                                  "convergence_mask_hex": format(detector_mask, "x")}
    manifest = {
        "schema_version": 1, "status": "circuit_derived_reference_not_author_export",
        "sector": "X_checks_Z_errors" if basis == "X" else "Z_checks_X_errors",
        "profile": profile, "W": width, "C": commit, "M": 72, "K": 12,
        "N_ERRORS": n, "N_QUBITS": 144, "stim_version": stim.__version__,
        "source_circuit": circuit_path.name,
        "source_sha256": hashlib.sha256(circuit_path.read_bytes()).hexdigest(),
        "source_full_detectors": circuit.num_detectors,
        "detector_blocks_source_ids": readout["blocks"],
        "data_qubits": readout["data_qubits"], "syndrome_ancillas": readout["syndrome_ancillas"],
        "mask_policy": "commit columns whose earliest detector cycle < C; converge first C*M rows",
        "right_boundary": "omit detector rows >= W*M; retain columns and record omitted support",
        "all_commit_widths": all_masks,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "columns.json").write_text(json.dumps(columns, separators=(",", ":")) + "\n")
    used_templates = sorted({col["template_cycle"] for col in columns})
    lineage = {str(t): [{"detectors": ds, "logicals": ls, **entry}
                         for (ds, ls), entry in sorted(templates[t].items())] for t in used_templates}
    (destination / "templates.json").write_text(json.dumps(lineage, separators=(",", ":")) + "\n")
    constants = {"W": width, "C": commit, "M": 72, "K": 12, "N_ERRORS": n, "N_QUBITS": 144}
    (destination / "window_dimensions.svh").write_text(
        "// Generated reference configuration. Include inside a module.\n" +
        "".join(f"localparam integer WINDOW_{name} = {value};\n" for name, value in constants.items()))
    return manifest


def export_common(root):
    """Embed reference profiles in one graph; absent columns are explicitly inactive."""
    profiles = {name: json.loads((root / name / "columns.json").read_text())
                for name in ("startup", "bulk")}
    def signature(col):
        return (col["cycle"], tuple(col["detectors"] + col["boundary_detectors"]),
                tuple(col["logicals"]))
    keys = sorted({signature(col) for columns in profiles.values() for col in columns})
    indices = {key: j for j, key in enumerate(keys)}
    manifest = json.loads((root / "bulk" / "manifest.json").read_text())
    width, commit = manifest["W"], manifest["C"]
    columns = [{"cycle": cycle, "detectors": [d for d in ds if d < width*72],
                "boundary_detectors": [d for d in ds if d >= width*72], "logicals": list(ls)}
               for cycle, ds, ls in keys]
    config = {}
    for name, source in profiles.items():
        mapping = [indices[signature(col)] for col in source]
        if len(mapping) != len(set(mapping)):
            raise ValueError("Duplicate signatures within reference profile")
        priors = [0.0] * len(columns)
        for old, new in enumerate(mapping):
            priors[new] = source[old]["probability"]
        config[name] = {"old_to_common": mapping, "priors": priors,
                        "active_mask_hex": format(packed(mapping), "x")}
    destination = root / "hardware"
    destination.mkdir(parents=True, exist_ok=True)
    n = len(columns)
    h = matrix_rows(columns, "detectors", width*72)
    a = matrix_rows(columns, "logicals", 12)
    cm, cvg = masks(columns, width, commit)
    for filename, rows, bits in (
        ("h_tilde_rows.mem", h, n), ("a_tilde_rows.mem", a, n),
        ("carry_rows.mem", [r & cm for r in h[commit*72:(commit+1)*72]], n),
        ("frame_rows.mem", [r & cm for r in a], n),
        ("commit_mask.mem", [cm], n), ("convergence_mask.mem", [cvg], width*72),
    ):
        write_mem(destination / filename, rows, bits)
    for name in config:
        write_mem(destination / f"{name}_active_mask.mem", [int(config[name]["active_mask_hex"], 16)], n)
    for filename in ("h_hat_rows.mem", "logical_readout_rows.mem"):
        (destination / filename).write_bytes((root / "bulk" / filename).read_bytes())
    manifest.update(profile="shared_hardware", N_ERRORS=n)
    manifest["all_commit_widths"] = {
        str(c): {"commit_mask_hex": format(masks(columns, width, c)[0], "x"),
                 "convergence_mask_hex": format(masks(columns, width, c)[1], "x")}
        for c in range(1, width)
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "columns.json").write_text(json.dumps(columns, separators=(",", ":")) + "\n")
    (destination / "profiles.json").write_text(json.dumps(config, separators=(",", ":")) + "\n")
    (destination / "window_dimensions.svh").write_text(
        "// Shared graph; decoder must honor the selected profile's active mask.\n" +
        "".join(f"localparam integer WINDOW_{name} = {value};\n" for name, value in
                {"W": width, "C": commit, "M": 72, "K": 12, "N_ERRORS": n, "N_QUBITS": 144}.items()))
    print(f"Shared hardware: {n} columns; startup active={len(config['startup']['old_to_common'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit", type=Path, required=True)
    parser.add_argument("--basis", choices=("X", "Z"), required=True,
                        help="check/readout basis, not the physical-error Pauli")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--commit", type=int, default=8,
                        help="example stride; every 1 <= C < W is also exported")
    args = parser.parse_args()
    if not 1 <= args.commit < args.width:
        parser.error("require 1 <= commit < width")
    circuit = stim.Circuit.from_file(args.circuit)
    readout = parse_readout(circuit, args.basis)
    _, templates, _, last_regular = extract_templates(circuit, readout)
    if args.width > last_regular + 1:
        parser.error("startup reference width exceeds available regular rounds")
    for profile in ("startup", "bulk"):
        manifest = export_profile(args.output / profile, args.circuit, circuit, readout,
                                  templates, args.width, args.commit, profile, args.basis)
        print(f"{args.basis} {profile}: H={args.width*72}x{manifest['N_ERRORS']}, "
              f"A=12x{manifest['N_ERRORS']}, C={args.commit}")
    export_common(args.output)


if __name__ == "__main__":
    main()
