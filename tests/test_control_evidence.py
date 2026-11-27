import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import control_assurance as ca


class ControlEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.source=self.repo/'operation.py'
        self.source.write_text('def valid_port(value):\n    return isinstance(value,int) and 1 <= value <= 65535\n',encoding='utf-8')
        (self.repo/'test_operation.py').write_text('import unittest\nfrom operation import valid_port\nclass PortTests(unittest.TestCase):\n def test_input(self):\n  self.assertTrue(valid_port(443))\n  self.assertFalse(valid_port(-1))\n  self.assertFalse(valid_port("443"))\n',encoding='utf-8')
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','PAS isolated fixture'],['add','.'],['commit','-qm','test fixture']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        self.record=ca.capture_control_evidence(self.repo,'test_operation.PortTests.test_input','test_operation.py',['operation.py'],['NDC-11'],self.repo/'evidence.json',project_id='fixture',release_id='r1')

    def evaluate(self,record=None,control='NDC-11'):
        return ca.evaluate_evidence(self.record if record is None else record,self.repo,control,project_id='fixture',release_id='r1')

    def test_real_execution_receipt_is_current_for_its_scope(self):
        self.assertEqual(self.evaluate(),[])
        receipt=json.loads(Path(self.record['artifact_location']).read_text())
        self.assertEqual(receipt['returncode'],0)
        self.assertIn('Ran 1 test',receipt['stderr'])

    def test_recapture_cannot_overwrite_retained_execution_history(self):
        previous=(self.repo/'evidence.json').read_bytes()
        artifact=Path(self.record['artifact_location']).read_bytes()
        with self.assertRaisesRegex(ValueError,'immutable'):
            ca.capture_control_evidence(self.repo,'test_operation.PortTests.test_input','test_operation.py',['operation.py'],['NDC-11'],self.repo/'evidence.json')
        self.assertEqual((self.repo/'evidence.json').read_bytes(),previous)
        self.assertEqual(Path(self.record['artifact_location']).read_bytes(),artifact)

    def test_invalidation_keeps_hash_verified_previous_version(self):
        import hashlib
        script=Path(__file__).resolve().parents[1]/'scripts/invalidate-stale-evidence.py'
        previous=(self.repo/'evidence.json').read_bytes()
        self.source.write_text('changed implementation')
        subprocess.run([sys.executable,str(script),str(self.repo/'evidence.json'),'--repo',str(self.repo)],check=True,capture_output=True)
        invalidated=json.loads((self.repo/'evidence.json').read_text())
        self.assertEqual(invalidated['validity'],'STALE')
        self.assertEqual(Path(invalidated['previous_version']['path']).read_bytes(),previous)
        self.assertEqual(invalidated['previous_version']['sha256'],hashlib.sha256(previous).hexdigest())

    def test_artifact_binding_detects_replacement_in_recovery(self):
        from runtime_state import evidence_binding_reasons,git_snapshot,file_binding
        record=copy.deepcopy(self.record)
        record['bindings']['artifact']=file_binding(Path(record['artifact_location']),self.repo)
        Path(record['artifact_location']).write_text('altered evidence')
        self.assertIn('artifact changed',evidence_binding_reasons(record,git_snapshot(self.repo),self.repo))

    def test_changed_implementation_and_test_invalidate_evidence(self):
        self.source.write_text('def valid_port(value): return True\n')
        self.assertIn('source changed',self.evaluate())
        (self.repo/'test_operation.py').write_text('# removed test\n')
        self.assertIn('test definition changed',self.evaluate())

    def test_changed_execution_artifact_and_wrong_scope_fail(self):
        record=copy.deepcopy(self.record)
        record['release_id']='r2'
        self.assertTrue(self.evaluate(record))
        self.assertTrue(self.evaluate(control='NDC-06'))
        Path(self.record['artifact_location']).write_text('{"returncode":0,"tests_executed":true}')
        self.assertIn('execution artifact missing or changed',self.evaluate())

    def test_failed_test_result_remains_blocking_even_with_current_bindings(self):
        (self.repo/'test_operation.py').write_text('import unittest\nclass PortTests(unittest.TestCase):\n def test_input(self): self.fail("unsafe")\n')
        record=ca.capture_control_evidence(self.repo,'test_operation.PortTests.test_input','test_operation.py',['operation.py'],['NDC-11'],self.repo/'failure.json',project_id='fixture',release_id='r1')
        self.assertIn('required executable test failed or was skipped',self.evaluate(record))

    def test_revoked_acceptance_and_high_score_cannot_override_blockers(self):
        contract={'production_intent':False,'readiness_score':100,'risk_acceptances':[{'acceptance_id':'A-1','risk_definition_id':'R-1','definition_version':'1.0.0','authority':'Human Fixture Reviewer','reason':'bounded test','scope':'fixture','approved_at':'2026-01-01T00:00:00Z','expires_at':'2027-01-01T00:00:00Z','review_trigger':'change','status':'REVOKED','revoked_at':'2026-02-01T00:00:00Z','revoked_by':'Human Fixture Reviewer','revocation_reason':'new finding'}]}
        result=ca.evidence_gate_engine(contract,repo=self.repo)
        self.assertEqual(result['gate_state'],'RED')
        self.assertFalse(result['production_authorized'])

    def test_unknown_required_assurance_never_promotes_to_green(self):
        result=ca.evidence_gate_engine({'production_intent':False,'required_assurance_states':['UNKNOWN'],'readiness_score':100},repo=self.repo)
        self.assertEqual(result['gate_state'],'RED')

    def test_expiry_and_unknown_validity_block_real_execution_evidence(self):
        record=copy.deepcopy(self.record);record['valid_until']='2000-01-01T00:00:00Z'
        self.assertIn('validity period expired',self.evaluate(record))
        record=copy.deepcopy(self.record);record['validity']='UNKNOWN'
        self.assertIn('evidence is not current',self.evaluate(record))

    def test_recovery_does_not_treat_unknown_evidence_as_current(self):
        from runtime_state import stale_evidence,git_snapshot
        from datetime import datetime,timezone
        record=copy.deepcopy(self.record);record['validity']='UNKNOWN'
        index={'schema_version':'1.2','project_id':'fixture','updated_at':datetime.now(timezone.utc).isoformat(),'evidence':[record]}
        (self.repo/'evidence-index.json').write_text(json.dumps(index))
        self.assertEqual(stale_evidence(self.repo,git_snapshot(self.repo),{},self.repo),[record['evidence_id']])


if __name__ == '__main__':
    unittest.main()
