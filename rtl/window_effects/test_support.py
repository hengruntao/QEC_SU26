"""Tests for support software only, not a test of the unimplemented RTL."""
import json
import hashlib
from pathlib import Path
import tempfile
import subprocess
import shutil
import unittest
import numpy as np
from check_effects_constants import check, dense
from generate_effects_constants import generate
from generate_effects_vectors import generate as generate_vectors
from window_effects_golden import EffectsGolden


def save_sparse(path, shape, entries, fmt):
    major, minor = shape if fmt=='csr' else shape[::-1]
    groups=[[] for _ in range(major)]
    for r,c in entries:
        a,b=(r,c) if fmt=='csr' else (c,r)
        groups[a].append(b)
    indices=[]; ptr=[0]
    for group in groups:
        indices.extend(sorted(group)); ptr.append(len(indices))
    np.savez(path,shape=np.array(shape),format=np.array(fmt.encode()),
             indices=np.array(indices,dtype=np.int64),indptr=np.array(ptr,dtype=np.int64),
             data=np.ones(len(indices),dtype=np.uint8))


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        rng=np.random.default_rng(10)
        h={(int(rng.integers(1008)),int(rng.integers(8785))) for _ in range(12000)}
        a={(int(rng.integers(12)),int(rng.integers(8785))) for _ in range(1200)}
        save_sparse(self.root/'144_12_12_Hdec.npz',(1008,8785),h,'csc')
        save_sparse(self.root/'144_12_12_Adec.npz',(12,8785),a,'csr')
        self.mask=self.root/'mask.npy'
        np.save(self.mask,rng.integers(0,2,8785,dtype=np.uint8))
        self.package=self.root/'window_effects_pkg.sv'

    def tearDown(self):
        self.tmp.cleanup()

    def test_constants_and_tamper_detection(self):
        generate(self.root,self.mask,8,self.package,'SYNTHETIC TEST ONLY')
        check(self.root,self.mask,self.package,8)
        self.package.write_text(self.package.read_text().replace('COMMIT_MASK =', 'BAD_MASK ='))
        with self.assertRaises(ValueError): check(self.root,self.mask,self.package,8)
        generate(self.root,self.mask,8,self.package,'SYNTHETIC TEST ONLY')
        self.package.write_text(self.package.read_text().replace('CARRY_ROW_71, CARRY_ROW_70','CARRY_ROW_70, CARRY_ROW_71'))
        with self.assertRaises(ValueError): check(self.root,self.mask,self.package,8)

    def test_golden_against_dense_math(self):
        model=EffectsGolden(self.root,self.mask,8)
        h=dense(self.root/'144_12_12_Hdec.npz'); a=dense(self.root/'144_12_12_Adec.npz')
        mask=np.load(self.mask); rng=np.random.default_rng(20)
        frame=np.zeros(12,dtype=np.uint8)
        for n in range(40):
            if n%13==0: model.reset(); frame[:]=0
            e=rng.integers(0,2,8785,dtype=np.uint8)
            valid=n%5!=0; success=valid and n%7!=0
            committed=e & mask if success else np.zeros(8785,dtype=np.uint8)
            frame ^= (a @ committed) & 1
            result=model.step(e,n%7!=0,valid)
            np.testing.assert_array_equal(result['frame'],frame)
            np.testing.assert_array_equal(result['carry'],((h @ committed)&1)[576:648])
            self.assertEqual(result['success'],success)
            self.assertEqual(result['valid'],valid)

    def test_vectors_and_real_capture_contract(self):
        model=EffectsGolden(self.root,self.mask,8)
        captures=self.root/'captures.json'
        captures.write_text(json.dumps(dict(source_hashes=model.hashes,provenance='SYNTHETIC interface fixture, not real BP',
            transactions=[dict(e_hat_hex='1',converged=True)])))
        rows=generate_vectors(self.root,self.mask,8,self.root/'vectors',12,relay=captures)
        self.assertEqual(len(rows),21)
        self.assertEqual(rows[-1]['kind'],'relay')
        doc=json.loads(captures.read_text()); doc['source_hashes']['H']='wrong'
        captures.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            generate_vectors(self.root,self.mask,8,self.root/'bad_vectors',relay=captures)

    def test_reject_wrong_dimensions_and_masks(self):
        np.save(self.mask,np.zeros(8640,dtype=np.uint8))
        with self.assertRaises(ValueError): EffectsGolden(self.root,self.mask,8)
        np.save(self.mask,np.full(8785,2,dtype=np.uint8))
        with self.assertRaises(ValueError): EffectsGolden(self.root,self.mask,8)

    def test_pinned_ibm_archives_and_export(self):
        data=Path(__file__).parent/'data/ibm'
        provenance=json.loads((data/'provenance.json').read_text())
        for name,digest in provenance['files'].items():
            self.assertEqual(hashlib.sha256((data/name).read_bytes()).hexdigest(),digest)
        # Deliberately synthetic mask exercises the real matrices, not a production window.
        generate(data,self.mask,8,self.package,'SYNTHETIC MASK; not an IBM window definition')
        check(data,self.mask,self.package,8)

    @unittest.skipUnless(shutil.which('tclsh'),'tclsh not installed')
    def test_tcl_creation_and_scaffold_guard(self):
        harness=self.root/'mock.tcl'
        harness.write_text('''set script [lindex $argv 0]
set argv [lrange $argv 1 end]
proc create_project {name out args} {file mkdir $out}
proc current_project {} {return project}
proc set_property {args} {}
proc add_files {args} {}
proc get_filesets {args} {return fileset}
proc update_compile_order {args} {}
source $script
''')
        script=Path(__file__).parent/'run_effects_vivado.tcl'
        command=['tclsh',str(harness),str(script),'--out',str(self.root/'project with spaces')]
        result=subprocess.run(command,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run(command,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        for action in ('sim','synth'):
            result=subprocess.run(['tclsh',str(harness),str(script),'--action',action,
                '--out',str(self.root/action)],text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('interface-only skeleton',result.stderr)


if __name__=='__main__':
    unittest.main()
