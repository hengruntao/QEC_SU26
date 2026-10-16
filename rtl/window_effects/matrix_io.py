"""Validated IBM sparse-NPZ input; bit j always denotes matrix column j."""
from pathlib import Path
import hashlib
import numpy as np

N_FAULTS, N_CHECKS, N_LOGICAL, M = 8785, 1008, 12, 72


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sparse_entries(path, shape):
    """Read SciPy CSR/CSC archives without a SciPy runtime dependency."""
    with np.load(path, allow_pickle=False) as z:
        if tuple(z['shape']) != shape:
            raise ValueError(f'{path}: expected shape {shape}, got {z["shape"]}')
        fmt = z['format'].item()
        if isinstance(fmt, bytes):
            fmt = fmt.decode('ascii')
        if fmt not in ('csr', 'csc'):
            raise ValueError('Only CSR/CSC sparse NPZ is supported')
        ptr, idx, data = z['indptr'], z['indices'], z['data']
        major, minor = shape if fmt == 'csr' else shape[::-1]
        if (ptr.shape != (major+1,) or ptr[0] != 0 or ptr[-1] != len(idx)
                or len(data) != len(idx) or np.any(np.diff(ptr) < 0)
                or np.any(idx < 0) or np.any(idx >= minor)
                or np.any((data != 0) & (data != 1))):
            raise ValueError('Malformed or nonbinary sparse matrix')
        entries = set()
        for a in range(major):
            for k in range(int(ptr[a]), int(ptr[a+1])):
                if not data[k]:
                    continue
                pair = (a, int(idx[k])) if fmt == 'csr' else (int(idx[k]), a)
                if pair in entries:
                    raise ValueError('Duplicate sparse entries need explicit normalization')
                entries.add(pair)
        return entries


def bits(value, size, name):
    a = np.asarray(value)
    if a.shape != (size,) or np.any((a != 0) & (a != 1)):
        raise ValueError(f'{name}: expected {size} binary entries')
    return a.astype(np.uint8)


def load_inputs(directory, mask_path, commit_cycles):
    directory = Path(directory)
    if not 1 <= commit_cycles < N_CHECKS//M:
        raise ValueError('Carry cycle must fit inside H; C must be at least one')
    h_path, a_path = directory/'144_12_12_Hdec.npz', directory/'144_12_12_Adec.npz'
    h = sparse_entries(h_path, (N_CHECKS, N_FAULTS))
    a = sparse_entries(a_path, (N_LOGICAL, N_FAULTS))
    mask = bits(np.load(mask_path, allow_pickle=False), N_FAULTS, 'commit mask')
    return h, a, mask, {'H': sha256(h_path), 'A': sha256(a_path), 'mask': sha256(mask_path)}


def packed(values):
    return sum(int(bit) << j for j, bit in enumerate(values))
