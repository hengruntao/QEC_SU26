"""Algorithm 2 lines 18-22, literal GF(2) operations; not a BP decoder."""
import numpy as np
from matrix_io import N_FAULTS, N_LOGICAL, M, bits, load_inputs


class EffectsGolden:
    def __init__(self, data, mask, commit_cycles):
        self.h, self.a, self.mask, self.hashes = load_inputs(data, mask, commit_cycles)
        self.c = commit_cycles
        self.reset()

    def reset(self):
        self.frame = np.zeros(N_LOGICAL, dtype=np.uint8)

    def step(self, e_hat, converged, valid=True):
        """One accepted request, not a cycle-accurate pipeline model.

        Invalid input produces no response. Failed decode produces a response
        with success=0, zero carry, unchanged frame and no committed faults.
        The downstream window may advance ONLY on a successful response.
        """
        e_hat = bits(e_hat,N_FAULTS,'e_hat')
        carry = np.zeros(M,dtype=np.uint8)
        e_com = np.zeros(N_FAULTS,dtype=np.uint8)
        delta = np.zeros(N_LOGICAL,dtype=np.uint8)
        if valid and converged:
            # Line 18 must use m_com: m_cvg has detector-space dimensions.
            e_com = e_hat & self.mask
            for row,col in self.a:
                delta[row] ^= e_com[col]
            detector_delta = np.zeros(1008,dtype=np.uint8)
            for row,col in self.h:
                detector_delta[row] ^= e_com[col]
            carry = detector_delta[self.c*M:(self.c+1)*M].copy()
            self.frame ^= delta
        return dict(valid=bool(valid),success=bool(valid and converged),
                    frame=self.frame.copy(),carry=carry,e_com=e_com,delta_frame=delta)
