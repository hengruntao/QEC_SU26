"""Independent-source audit tests; no synthesis or full Relay execution."""
from pathlib import Path
import tempfile
import unittest
from audit_window_mapping import audit

ROOT=Path(__file__).parent


class MappingTests(unittest.TestCase):
    def test_commit_cuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for c in (1,8,11):
                report=audit(ROOT/'data/ibm',ROOT/'data/ibm/gross_x_memory_12_rounds.stim',c,Path(tmp)/str(c))
                self.assertEqual(report['H_stim_exact_signature_matches'],8784)
                self.assertEqual(report['logical_transform_rank'],12)
                self.assertEqual(report['committed_faults'],720*c)
                self.assertEqual(report['carry_unique_columns'],504)
                self.assertEqual(report['carry_row_weights'],[10]*72)
                self.assertEqual(report['null_fault_columns'],[8784])

    def test_reject_invalid_commit_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            for c in (0,12,13):
                with self.assertRaises(ValueError):
                    audit(ROOT/'data/ibm',ROOT/'data/ibm/gross_x_memory_12_rounds.stim',c,Path(tmp))


if __name__=='__main__':
    unittest.main()
