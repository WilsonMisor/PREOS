import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from production_feedback import validate_learning
from lifecycle_traceability import sha
from test_lifecycle_resolution import build_fixture


class ProductionFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.before=sha((ROOT/'references/risks/model2/normalized-risk-definitions.jsonl').read_bytes())
        build_fixture(self.repo)
        self.learning=json.loads((self.repo/'learning.json').read_text())

    def test_learning_executes_regression_and_only_queues_candidate(self):
        result=validate_learning(self.learning,self.repo)
        self.assertEqual(result['actions_accounted'],12)
        candidate=json.loads((self.repo/self.learning['candidate']['path']).read_text())
        self.assertTrue(candidate['candidate_id'].startswith('CAND-RISK-'))
        self.assertFalse(any(e['stage']=='CANONICAL_PROMOTION' for e in candidate['events']))
        self.assertEqual(sha((ROOT/'references/risks/model2/normalized-risk-definitions.jsonl').read_bytes()),self.before)

    def test_missing_actions_or_unjustified_conditional_omissions_fail(self):
        for field in ('root_cause','trigger','contributing_factors','missed_detection_reason'):
            bad=copy.deepcopy(self.learning);bad.pop(field)
            with self.assertRaises(ValueError): validate_learning(bad,self.repo)
        for field in ('architecture_decision','cost_model','security_model'):
            bad=copy.deepcopy(self.learning);bad[field]={'disposition':'NOT_APPLICABLE'}
            with self.assertRaises(ValueError): validate_learning(bad,self.repo)

    def test_changed_monitoring_and_failed_regression_are_rejected(self):
        path=self.repo/'monitoring.json';original=path.read_bytes();path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed'): validate_learning(self.learning,self.repo)
        path.write_bytes(original)
        path=self.repo/'evidence.execution.json';execution=json.loads(path.read_text());execution['returncode']=1;path.write_text(json.dumps(execution))
        self.learning['regression_test']['execution']['sha256']=sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'regression failed'): validate_learning(self.learning,self.repo)


if __name__=='__main__': unittest.main()
