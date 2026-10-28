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


if __name__ == '__main__':
    unittest.main()
