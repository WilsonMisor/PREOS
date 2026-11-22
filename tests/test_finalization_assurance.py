"""Adversarial regression tests for the recovered PAS v2 implementation."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from risk_concern_runtime import (RiskConcernError, validate_concern_runtime,
    validate_acceptance_record, verify_acceptance_authority, acceptance_scope)
from control_assurance import evidence_gate_engine
from four_source_audit import verify_source1, verify_source2, verify_semantic_units, verify_source4_crosswalk
from risk_field_crosswalk import project_fields, reconstruct, validate_mapping


class FinalizationAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'references/risks/model2/concern-runtime-evidence.json').read_text())
        self.original=copy.deepcopy(self.data['definitions'])
        self.now=datetime(2026,11,21,tzinfo=timezone.utc)

    def unchanged(self): self.assertEqual(self.data['definitions'],self.original)

    def test_definition_exists_without_assessment(self):
        self.assertEqual(validate_concern_runtime({'definitions':self.original})['independent_definitions'],3)

    def test_multiple_assessments_share_one_definition(self):
        self.assertEqual(validate_concern_runtime(self.data)['assessments'],3)
        self.assertEqual(self.data['assessments'][0]['risk_definition_id'],self.data['assessments'][1]['risk_definition_id'])

    def test_stale_replaced_invalid_evidence_preserves_definitions_and_history(self):
        before=copy.deepcopy(self.data['evidence_bindings'])
        self.data['evidence_bindings'][1]['validity']='STALE'
        replacement=copy.deepcopy(self.data['evidence_bindings'][1]); replacement.update(risk_evidence_id='REB-003',validity='CURRENT')
        self.data['evidence_bindings'].append(replacement)
        self.data['evidence_bindings'][1]['replacement_evidence_id']='REB-003'
        validate_concern_runtime(self.data); self.unchanged()
        self.assertEqual(self.data['evidence_bindings'][0],before[0])

    def test_acceptance_expiration_and_revocation_do_not_change_definition(self):
        active=self.data['acceptances'][0]
        with self.assertRaisesRegex(RiskConcernError,'expired'):
            validate_acceptance_record(active,now=datetime(2028,1,1,tzinfo=timezone.utc))
        active.update(status='REVOKED',current_authority=False,revoked_at='2026-11-20T00:00:00Z',revoked_by='Human Test Owner',revocation_reason='test revocation')
        self.assertFalse(validate_acceptance_record(active,now=self.now)); self.unchanged()

    def test_evidence_replacement_orphans_cycles_and_scope_mismatch_rejected(self):
        for replacement in ['missing', 'REB-001']:
            data=copy.deepcopy(self.data); data['evidence_bindings'][1]['replacement_evidence_id']=replacement
            with self.assertRaises(RiskConcernError): validate_concern_runtime(data)
        data=copy.deepcopy(self.data); data['evidence_bindings'][1]['risk_assessment_id']='RAS-002'
        with self.assertRaises(RiskConcernError): validate_concern_runtime(data)

    def test_economics_and_evolution_refresh_preserve_historical_versions(self):
        history=copy.deepcopy((self.data['economics'],self.data['evolutions']))
        for collection,identity in [('economics','risk_economics_id'),('evolutions','risk_evolution_id')]:
            new=copy.deepcopy(self.data[collection][-1]);new[identity]='new-version'
            if collection=='economics': new['unit_economics']={'incident_cost':2300}
            else: new['activation_trigger']='measured request rate exceeds reviewed limit'
            self.data[collection].append(new)
        validate_concern_runtime(self.data);self.unchanged()
        self.assertEqual(self.data['economics'][:-1],history[0]); self.assertEqual(self.data['evolutions'][:-1],history[1])

    def test_all_concern_orphans_and_duplicate_identities_rejected(self):
        for collection,identity in [('assessments','risk_assessment_id'),('economics','risk_economics_id'),('evolutions','risk_evolution_id'),('evidence_bindings','risk_evidence_id'),('acceptances','acceptance_id')]:
            with self.subTest(collection=collection):
                data=copy.deepcopy(self.data);data[collection][0]['definition_version']='99.0.0'
                with self.assertRaises(RiskConcernError): validate_concern_runtime(data)
                data=copy.deepcopy(self.data);data[collection].append(copy.deepcopy(data[collection][0]))
                with self.assertRaisesRegex(RiskConcernError,'duplicate'): validate_concern_runtime(data)

    def test_assessment_cannot_overwrite_definition_or_source_truth(self):
        self.data['assessments'][0]['normalized_definition']={'canonical_name':'fabricated'}
        with self.assertRaisesRegex(RiskConcernError,'cannot overwrite'): validate_concern_runtime(self.data)

    def test_definition_rejects_source_default_status_contamination(self):
        for field in ['assurance_state','release_id','risk_acceptance','evidence_freshness']:
            data=copy.deepcopy(self.data);data['definitions'][0][field]='FAIL'
            with self.assertRaisesRegex(RiskConcernError,'mutable'):validate_concern_runtime(data)

    def test_structurally_valid_acceptance_is_not_human_approval(self):
        record=copy.deepcopy(self.data['acceptances'][0])
        self.assertTrue(validate_acceptance_record(record,now=self.now))
        with self.assertRaisesRegex(RiskConcernError,'approval store'):verify_acceptance_authority(record,None,now=self.now)
        result=evidence_gate_engine({'production_intent':False,'risk_acceptances':[record]})
        self.assertEqual(result['gate_state'],'RED');self.assertFalse(result['production_authorized'])
        self.assertEqual(validate_concern_runtime(self.data)['current_acceptances'],0)

    def test_durable_human_approval_is_scoped_and_cannot_survive_mutation(self):
        record=copy.deepcopy(self.data['acceptances'][0])
        record.update(project_id='isolated-test-fixture',approval_id='TEST-ONLY',residual_risk='test exposure',compensating_controls=[])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            approval={'approval_id':'TEST-ONLY','approval_type':'RISK_ACCEPTANCE','status':'GRANTED','authority':record['authority'],'scope':acceptance_scope(record),'rationale':'Synthetic test only','updated_at':'2026-11-20T00:00:00Z'}
            state={'schema_version':'1.2','project_id':record['project_id'],'updated_at':approval['updated_at'],'approvals':[approval]}
            (root/'approval-state.json').write_text(json.dumps(state))
            self.assertTrue(verify_acceptance_authority(record,root,now=self.now))
            for field,value in [('scope','expanded'),('residual_risk','different'),('expires_at','2099-01-01T00:00:00Z'),('readiness_requirement_ids',['forged-requirement'])]:
                changed={**record,field:value}
                with self.assertRaisesRegex(RiskConcernError,'changed'):verify_acceptance_authority(changed,root,now=self.now)
            approval['status']='DENIED';(root/'approval-state.json').write_text(json.dumps(state))
            with self.assertRaises(RiskConcernError):verify_acceptance_authority(record,root,now=self.now)

    def test_future_approval_invalid_chronology_and_unknown_authority_rejected(self):
        base=self.data['acceptances'][0]
        for values in [{'approved_at':'2090-01-01T00:00:00Z'},{'expires_at':'2020-01-01T00:00:00Z'},{'authority':'ROLE GAP'},{'authority':'Codex'}]:
            with self.assertRaises(RiskConcernError):validate_acceptance_record({**base,**values},now=self.now)

    def test_source1_all_fields_identities_and_variants_reparsed(self):
        self.assertEqual(verify_source1()['records'],4337)

    def test_source2_all_domains_and_paragraphs_reparsed(self):
        self.assertEqual(verify_source2()['domains'],36)

    def test_source3_source4_every_meaningful_line_reparsed(self):
        result=verify_semantic_units(); self.assertEqual(result['source-3']['units'],1612); self.assertEqual(result['source-4']['units'],1459)

    def test_source4_structures_match_original_locations(self):
        self.assertGreater(verify_source4_crosswalk()['source_items_checked_against_text'],900)

    def test_37_and_40_fields_round_trip_without_status_or_approval_inference(self):
        for source,count in [('source-1',40),('source-4',37)]:
            fields={i:{'text':f'unique field {i}','nested':['FAIL','No implementation evidence']} for i in range(1,count+1)}
            projected=project_fields(source,fields)
            self.assertEqual(reconstruct(projected),fields)
            self.assertFalse(projected['creates_assessment']);self.assertFalse(projected['grants_acceptance'])
            self.assertEqual(validate_mapping(source)['fields'],count)
            status_field=40 if count==40 else 21
            self.assertEqual(projected['projections']['risk_assessment']['source_projection.source_status']['source_field'],status_field)
            self.assertFalse(any('status' in p for p in projected['projections']['risk_definition']))

if __name__=='__main__':unittest.main()
