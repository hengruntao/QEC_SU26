"""Independent Stim replay and exported-bit-order checks for window matrices."""

import argparse
import json
import math
import unittest
from pathlib import Path

import numpy as np
import stim

import generate_window_matrices as g

popcount = getattr(int, "bit_count", lambda value: bin(value).count("1"))


def read_mem(path):
    return [int(line, 16) for line in path.read_text().splitlines()]


def product(rows, errors):
    return g.packed(i for i, row in enumerate(rows) if popcount(row & errors) % 2)


def verify_dense_exports(columns, h, a):
    # Check EVERY exported bit, including repeated bulk copies and lookahead.
    for actual, field in ((h, "detectors"), (a, "logicals")):
        expected = [0] * len(actual)
        for j, column in enumerate(columns):
            for i in column[field]:
                expected[i] ^= 1 << j
        if actual != expected:
            raise AssertionError(f"Exported {field} rows disagree with sparse columns")


def rank(rows):
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
    return len(pivots)


class TinyMatrixTests(unittest.TestCase):
    def setUp(self):
        self.columns = [
            {"cycle": 0, "detectors": [0, 72], "boundary_detectors": [], "logicals": [0]},
            {"cycle": 0, "detectors": [1, 73], "boundary_detectors": [], "logicals": [0]},
            {"cycle": 1, "detectors": [72, 144], "boundary_detectors": [], "logicals": [1]},
        ]

    def test_hand_calculated_products(self):
        h = g.matrix_rows(self.columns, "detectors", 216)
        a = g.matrix_rows(self.columns, "logicals", 2)
        cm, cvg = g.masks(self.columns, 3, 1)
        self.assertEqual(cm, 3)
        self.assertEqual(cvg, (1 << 72) - 1)
        self.assertEqual(product(h, 1), (1 << 0) | (1 << 72))
        self.assertEqual(product(h[72:144], 7 & cm), 3)
        self.assertEqual(product(a, 7 & cm), 0)  # Two logical flips cancel.
        self.assertEqual(product(h, 0), 0)

    def test_invalid_stride_and_long_carry(self):
        for commit in (0, 3):
            with self.assertRaises(ValueError):
                g.masks(self.columns, 3, commit)
        self.columns[0]["detectors"].append(144)
        with self.assertRaises(ValueError):
            g.masks(self.columns, 3, 1)

    def test_uncommitted_column_mutation_is_rejected(self):
        h = g.matrix_rows(self.columns, "detectors", 216)
        a = g.matrix_rows(self.columns, "logicals", 2)
        verify_dense_exports(self.columns, h, a)
        for field in ("H", "A"):
            damaged_h, damaged_a = h.copy(), a.copy()
            (damaged_h if field == "H" else damaged_a)[0] ^= 1 << 2
            with self.assertRaises(AssertionError):
                verify_dense_exports(self.columns, damaged_h, damaged_a)


def verify_export(circuit_path, basis, root):
    circuit = stim.Circuit.from_file(circuit_path)
    readout = g.parse_readout(circuit, basis)
    dem, templates, raw_mapping, _ = g.extract_templates(circuit, readout)
    sampler = dem.compile_sampler(seed=12)
    raw_priors = [op.args_copy()[0] for op in dem if op.type == "error"]
    for entries in templates.values():
        for entry in entries.values():
            expected = (1-math.prod(1-2*raw_priors[i] for i in entry["source_errors"]))/2
            assert abs(expected-entry["probability"]) < 1e-13
    rng = np.random.default_rng(1234)
    total_replays = 0
    for profile in ("startup", "bulk"):
        path = root / profile
        manifest = json.loads((path / "manifest.json").read_text())
        columns = json.loads((path / "columns.json").read_text())
        h = read_mem(path / "h_tilde_rows.mem")
        a = read_mem(path / "a_tilde_rows.mem")
        width, commit = manifest["W"], manifest["C"]
        n = len(columns)
        assert n == manifest["N_ERRORS"]
        assert len(h) == width * 72 and len(a) == 12
        assert all(row.bit_length() <= n for row in h + a)
        verify_dense_exports(columns, h, a)
        source_detectors = [d for block in readout["blocks"][:width] for d in block]
        # Replay every raw mechanism that contributes to each used template,
        # independently through Stim. This also tests every merged column.
        template_columns = defaultdict_columns(columns)
        checks = []
        for template_cycle, indices in template_columns.items():
            entries = sorted(templates[template_cycle].items())
            for j in indices:
                col = columns[j]
                entry = entries[col["template_column"]][1]
                checks.extend((raw_id, j) for raw_id in entry["source_errors"])
        for offset in range(0, len(checks), 128):
            batch = checks[offset:offset+128]
            replay = np.zeros((len(batch), dem.num_errors), dtype=np.bool_)
            for i, (raw_id, _) in enumerate(batch):
                replay[i, raw_id] = True
            ds, ls, _ = sampler.sample(len(batch), recorded_errors_to_replay=replay)
            for i, (_, j) in enumerate(batch):
                col = columns[j]
                source_cycle = col["template_cycle"]
                source_rows = [d for ids in readout["blocks"][source_cycle:source_cycle+2] for d in ids]
                relative = np.flatnonzero(ds[i, source_rows]).tolist()
                expected = [col["cycle"]*72 + d for d in relative
                            if col["cycle"]*72 + d < width*72]
                assert expected == col["detectors"]
                assert np.flatnonzero(ls[i]).tolist() == col["logicals"]
                assert all(bool(h[d] & (1 << j)) == (d in expected) for d in range(width*72))
                assert product(a, 1 << j) == g.packed(col["logicals"])
            total_replays += len(batch)

        # Column-wise XOR is a different calculation from packed row products.
        # Test every stride and verify the single-cycle carry safety invariant.
        for stride in range(1, width):
            cm, cvg = g.masks(columns, width, stride)
            saved = manifest["all_commit_widths"][str(stride)]
            assert cm == int(saved["commit_mask_hex"], 16)
            assert cvg == int(saved["convergence_mask_hex"], 16)
            for _ in range(16):
                selected = rng.choice(n, size=40, replace=False).tolist()
                errors = g.packed(selected) & cm
                detector_bits, logical_bits = 0, 0
                for j in selected:
                    if cm & (1 << j):
                        detector_bits ^= g.packed(columns[j]["detectors"])
                        logical_bits ^= g.packed(columns[j]["logicals"])
                assert product(h, errors) == detector_bits
                assert product(a, errors) == logical_bits
                assert detector_bits >> ((stride+1)*72) == 0
                assert product(h[stride*72:(stride+1)*72], errors) == (detector_bits >> (stride*72))
        cm, cvg = g.masks(columns, width, commit)
        assert read_mem(path / "commit_mask.mem") == [cm]
        assert read_mem(path / "convergence_mask.mem") == [cvg]
        assert read_mem(path / "carry_rows.mem") == [r & cm for r in h[commit*72:(commit+1)*72]]
        assert read_mem(path / "frame_rows.mem") == [r & cm for r in a]

        # Recombine simultaneous source faults and verify full startup projection.
        if profile == "startup":
            lookup = {(col["cycle"], tuple(d-col["cycle"]*72 for d in col["detectors"] + col["boundary_detectors"]),
                       tuple(col["logicals"])): j for j, col in enumerate(columns)}
            replay = np.zeros((64, dem.num_errors), dtype=np.bool_)
            retained = [(raw_id, lookup[(cycle, *key)]) for raw_id, (cycle, key) in raw_mapping.items()
                        if cycle < width]
            error_vectors = [0]*64
            for i in range(64):
                for selected in rng.choice(len(retained), size=80, replace=False):
                    raw_id, j = retained[selected]
                    replay[i, raw_id] = True
                    error_vectors[i] ^= 1 << j
            ds, ls, _ = sampler.sample(64, recorded_errors_to_replay=replay)
            for i, vector in enumerate(error_vectors):
                assert product(h, vector) == g.packed(np.flatnonzero(ds[i, source_detectors]).tolist())
                assert product(a, vector) == g.packed(np.flatnonzero(ls[i]).tolist())

        # Check merged probabilities separately from deterministic replay.
        for col in columns:
            key = (tuple(d-col["cycle"]*72 for d in col["detectors"] + col["boundary_detectors"]),
                   tuple(col["logicals"]))
            assert col["probability"] == templates[col["template_cycle"]][key]["probability"]
        print(f"PASS {basis} {profile}: all columns, all strides, packed exports, random XOR products")

    # Arbitrary final readout bits through Stim's measurement-to-detector converter
    # independently check H_hat and L, including the interleaved readout order.
    h_hat = read_mem(root / "bulk" / "h_hat_rows.mem")
    logical = read_mem(root / "bulk" / "logical_readout_rows.mem")
    data = rng.integers(0, 2, size=(256, 144), dtype=np.uint8).astype(np.bool_)
    measurements = np.zeros((256, circuit.num_measurements), dtype=np.bool_)
    data_index = {q: i for i, q in enumerate(readout["data_qubits"])}
    for pos, qubit in enumerate(readout["final_measurement_qubits"]):
        measurements[:, circuit.num_measurements-144+pos] = data[:, data_index[qubit]]
    ds, ls = circuit.compile_m2d_converter().convert(measurements=measurements, separate_observables=True)
    for i in range(256):
        word = g.packed(np.flatnonzero(data[i]).tolist())
        assert product(h_hat, word) == g.packed(np.flatnonzero(ds[i, readout["blocks"][-1]]).tolist())
        assert product(logical, word) == g.packed(np.flatnonzero(ls[i]).tolist())
    assert rank(h_hat) == 66
    assert rank(logical) == 12
    print(f"PASS {basis}: {total_replays} single-source Stim replays, 64 combined replays, 256 final readouts")


def defaultdict_columns(columns):
    # One destination cycle per template suffices: all other copies are translations.
    result = {}
    for j, col in enumerate(columns):
        entry = result.setdefault(col["template_cycle"], {})
        entry.setdefault(col["template_column"], j)
    return {t: list(indices.values()) for t, indices in result.items()}


def verify_common(root):
    path = root / "hardware"
    width = json.loads((path / "manifest.json").read_text())["W"]
    config = json.loads((path / "profiles.json").read_text())
    columns = json.loads((path / "columns.json").read_text())
    h = read_mem(path / "h_tilde_rows.mem")
    a = read_mem(path / "a_tilde_rows.mem")
    verify_dense_exports(columns, h, a)
    for name, profile in config.items():
        source = json.loads((root / name / "columns.json").read_text())
        mapping = profile["old_to_common"]
        assert len(source) == len(mapping) == len(set(mapping))
        active = int(profile["active_mask_hex"], 16)
        assert active == g.packed(mapping)
        assert read_mem(path / f"{name}_active_mask.mem") == [active]
        for old, new in enumerate(mapping):
            for field in ("cycle", "detectors", "boundary_detectors", "logicals"):
                assert source[old][field] == columns[new][field]
            assert profile["priors"][new] == source[old]["probability"]
        assert all(p == 0 for j, p in enumerate(profile["priors"]) if not active & (1 << j))
    # Match original reference masks at every stride after remapping.
    for stride in range(1, width):
        common_mask, _ = g.masks(columns, width, stride)
        for name, profile in config.items():
            source = json.loads((root / name / "columns.json").read_text())
            old_mask, _ = g.masks(source, width, stride)
            remapped = g.packed(new for old, new in enumerate(profile["old_to_common"]) if old_mask & (1 << old))
            assert remapped == common_mask & int(profile["active_mask_hex"], 16)
    print("PASS common graph: exact profile embedding, active masks, priors, all commit strides")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--circuit", type=Path)
    parser.add_argument("--basis", choices=("X", "Z"))
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--cross-sectors", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TinyMatrixTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)
    if args.circuit:
        if args.basis is None or args.generated is None:
            parser.error("circuit verification requires --basis and --generated")
        verify_export(args.circuit, args.basis, args.generated)
        verify_common(args.generated)
    if args.cross_sectors:
        root = args.cross_sectors
        hx = read_mem(root / "x_checks/bulk/h_hat_rows.mem")
        hz = read_mem(root / "z_checks/bulk/h_hat_rows.mem")
        lx = read_mem(root / "x_checks/bulk/logical_readout_rows.mem")
        lz = read_mem(root / "z_checks/bulk/logical_readout_rows.mem")
        assert all(popcount(x & z) % 2 == 0 for x in hx for z in hz)
        assert all(popcount(x & z) % 2 == 0 for x in lx for z in hz)
        assert all(popcount(x & z) % 2 == 0 for x in hx for z in lz)
        assert rank([product(lz, x) for x in lx]) == 12
        print("PASS cross-sector stabilizer commutation and rank-12 logical pairing")


if __name__ == "__main__":
    main()
