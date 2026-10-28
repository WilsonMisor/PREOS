import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import candidate_workflow as cw


def candidate_fixture():
    return {'provenance_class':'ENGINEERING_EXPANSION','source':{'kind':'incident','reference':'INC-TEST-001'},'definition':{'canonical_name':'Duplicate Callback Ledger Credit','dimension':'universal','category':'Financial correctness','root_cause':'Provider retries reuse the same event identity.','failure_mechanism':'Consumer credits the ledger twice.','trigger_conditions':'Repeated provider callback after a timeout.','prevention_strategy':'Persist a unique provider event key atomically with ledger posting.','automated_test':'Duplicate callback causes exactly one ledger posting.','owner':'Payments Engineering'}}


class CandidateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.corpus = self.root/'corpus'
        self.corpus.mkdir()
        cw.write_rows(self.corpus/'normalized-risk-definitions.jsonl', [])
        cw.write_rows(self.corpus/'risk-relationships.jsonl', [])
        cw.atomic_write_json(self.corpus/'catalogue-index.json', {'catalogue_version':'1.0.0','count':0})
        self.test_repo = self.root/'app'
        self.test_repo.mkdir()
        (self.test_repo/'test_callback.py').write_text('import unittest\nclass CallbackTests(unittest.TestCase):\n    def test_duplicate(self):\n        posted = {}\n        for event in ["event-1", "event-1"]:\n            posted.setdefault(event, 100)\n        self.assertEqual(sum(posted.values()), 100)\n', encoding='utf-8')
        self.candidate = candidate_fixture()
        self.path = cw.submit(self.candidate,self.root/'queue')
        self.regression = {'path':'test_callback.py','selector':'test_callback.CallbackTests.test_duplicate'}
        self.approval_root = self.root/'state'
        self.approval_root.mkdir()

    def prepare(self, **kwargs):
        return cw.prepare_promotion(self.path, self.corpus, version=kwargs.get('version','1.1.0'), regression=self.regression, test_repo=self.test_repo)

    def grant(self, approval_scope, **changes):
        record = {'approval_id':'REVIEW-1','approval_type':'CANONICAL_RISK_PROMOTION','scope':approval_scope,'status':'GRANTED','authority':'Test Human Reviewer','rationale':'Reviewed mechanism, deduplication, version decision and executable regression.','updated_at':'2026-10-22T00:00:00Z'}
        record.update(changes)
        cw.atomic_write_json(self.approval_root/'approval-state.json', {'schema_version':'1.2','project_id':'fixture','updated_at':'2026-10-22T00:00:00Z','approvals':[record]})

    def publish(self):
        return cw.promote(self.path,self.corpus,self.root/'published',approval_root=self.approval_root,project_id='fixture',approval_id='REVIEW-1',test_repo=self.test_repo)

    def test_complete_versioned_promotion_preserves_source_and_all_audit_steps(self):
        before = cw.catalogue_snapshot(self.corpus)
        prepared = self.prepare()
        self.grant(prepared['approval_scope'])
        result = self.publish()
        self.assertNotEqual(result['candidate_id'],result['risk_definition_id'])
        version = Path(result['version_path'])
        definitions = cw.read_rows(version/'normalized-risk-definitions.jsonl')
        self.assertEqual(definitions[0]['semantic_review_status'],'ACCEPTED_BY_HUMAN')
        self.assertEqual(cw.read_json(version/'catalogue-index.json')['candidate_promotions'][result['candidate_id']],result['risk_definition_id'])
        audit = cw.read_json(version/'promotion-audit.json')
        cw.validate_journal(audit)
        self.assertEqual([e['stage'] for e in audit['events']],['CANDIDATE_RECORDED','RELATIONSHIP_REVIEW','SEMANTIC_RULE_REVIEW','PROMOTION_PLAN','HUMAN_REVIEW','REGRESSION_EXECUTED','CANONICAL_PROMOTION'])
        self.assertEqual(before,cw.catalogue_snapshot(self.corpus))
        self.assertEqual(cw.read_json(self.root/'published/CURRENT.json')['catalogue_version'],'1.1.0')

    def test_intake_is_idempotent_and_never_mutates_corpus(self):
        before = cw.catalogue_snapshot(self.corpus)
        self.assertEqual(cw.submit(self.candidate,self.root/'queue'),self.path)
        self.assertEqual(before,cw.catalogue_snapshot(self.corpus))
        self.assertEqual(len(cw.read_json(self.path)['events']),1)

    def test_missing_or_denied_review_blocks_promotion(self):
        prepared = self.prepare()
        with self.assertRaisesRegex(ValueError,'not granted'):
            self.publish()
        self.grant(prepared['approval_scope'],status='DENIED')
        with self.assertRaisesRegex(ValueError,'not granted'):
            self.publish()
        self.assertFalse((self.root/'published/CURRENT.json').exists())

    def test_ai_stale_wrong_scope_and_expired_reviews_are_rejected(self):
        prepared = self.prepare()
        for changes in ({'authority':'Codex'},{'scope':'another-plan'},{'expires_at':'2000-01-01T00:00:00Z'},{'revoked_at':'2026-10-22T00:00:00Z'}):
            self.grant(prepared['approval_scope'],**changes)
            with self.assertRaises(ValueError):
                self.publish()

    def test_duplicate_links_existing_and_cannot_be_promoted(self):
        cw.write_rows(self.corpus/'normalized-risk-definitions.jsonl',[{'canonical_name':self.candidate['definition']['canonical_name'],'risk_definition_id':'RDEF-EXISTING','definition_version':'1.0.0'}])
        with self.assertRaisesRegex(ValueError,'duplicate candidate'):
            self.prepare()
        self.assertEqual(cw.read_json(self.path)['events'][-1]['details']['matches'][0]['relationship'],'SAME_AS')

    def test_version_must_advance(self):
        for version in ('1.0.0','0.9.0','../escape'):
            with self.assertRaises(ValueError):
                self.prepare(version=version)

    def test_candidate_and_test_tampering_invalidate_approval(self):
        prepared = self.prepare()
        self.grant(prepared['approval_scope'])
        test_path = self.test_repo/'test_callback.py'
        test_path.write_text(test_path.read_text()+'\n# changed\n')
        with self.assertRaisesRegex(ValueError,'test changed'):
            self.publish()
        state = cw.read_json(self.path)
        state['candidate']['definition']['failure_mechanism']='changed'
        cw.atomic_write_json(self.path,state)
        with self.assertRaisesRegex(ValueError,'candidate ID'):
            self.publish()

    def test_failure_and_skipped_regression_never_publish(self):
        test_path = self.test_repo/'test_callback.py'
        for source in ('import unittest\nclass CallbackTests(unittest.TestCase):\n def test_duplicate(self): self.fail("broken")\n', 'import unittest\nclass CallbackTests(unittest.TestCase):\n @unittest.skip("missing environment")\n def test_duplicate(self): pass\n'):
            test_path.write_text(source,encoding='utf-8')
            prepared = self.prepare()
            self.grant(prepared['approval_scope'])
            with self.assertRaisesRegex(ValueError,'regression failed'):
                self.publish()
            self.assertFalse((self.root/'published/CURRENT.json').exists())

    def test_source_change_invalidates_prior_review(self):
        prepared = self.prepare()
        self.grant(prepared['approval_scope'])
        cw.atomic_write_json(self.corpus/'catalogue-index.json',{'catalogue_version':'1.0.1'})
        with self.assertRaisesRegex(ValueError,'catalogue changed'):
            self.publish()

    def test_external_research_requires_source_and_date(self):
        self.candidate['provenance_class']='EXTERNAL_RESEARCH_REQUIRED'
        with self.assertRaisesRegex(ValueError,'source URL'):
            cw.submit(self.candidate,self.root/'queue')
        self.candidate['research']={'url':'https://example.invalid/test-source','retrieved_at':'2026-10-01T00:00:00Z'}
        self.assertTrue(cw.submit(self.candidate,self.root/'queue').is_file())

    def test_source_direct_and_qualified_review_also_require_human_approval(self):
        for provenance in ('SOURCE_DIRECT','QUALIFIED_HUMAN_REVIEW_REQUIRED'):
            candidate = copy.deepcopy(self.candidate)
            candidate['provenance_class']=provenance
            path=cw.submit(candidate,self.root/'queue')
            cw.prepare_promotion(path,self.corpus,version='1.1.0',regression=self.regression,test_repo=self.test_repo)
            with self.assertRaisesRegex(ValueError,'not granted'):
                cw.promote(path,self.corpus,self.root/'published',approval_root=self.approval_root,project_id='fixture',approval_id='REVIEW-1',test_repo=self.test_repo)

    def test_semantic_contamination_and_project_status_rejected(self):
        self.candidate['definition'].update(canonical_name='Serialization Failure',root_cause='Shared state concurrent writes')
        with self.assertRaisesRegex(ValueError,'sentinel'):
            cw.submit(self.candidate,self.root/'queue')
        self.candidate=candidate_fixture()
        self.candidate['definition']['release_id']='release-1'
        with self.assertRaisesRegex(ValueError,'project/release'):
            cw.submit(self.candidate,self.root/'queue')


if __name__ == '__main__':
    unittest.main()
