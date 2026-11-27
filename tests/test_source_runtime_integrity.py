import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from source_semantics import select as select_source, validate as validate_sources
from readiness_assurance import select as select_readiness, evaluate
from control_assurance import evidence_gate_engine
from catalogue_traceability import generate, validate, expected_rows
from risk_graph import RiskGraph

class SourceRuntimeIntegrityTests(unittest.TestCase):
    def test_all_doctrine_units_are_addressable_and_runtime_owners_resolve(self):
        result=validate_sources();self.assertEqual(result['source-3']['units'],1612);self.assertEqual(result['source-4']['units'],1459)
        selected=select_source('source-4',keyword='reconciliation',limit=3)
        self.assertEqual(len(selected),3)
        self.assertTrue(all('reconciliation' in r['text'].casefold() and r['source_sha256'] for r in selected))
        with self.assertRaises(ValueError):select_source('source-4',limit=1459)

    def test_readiness_selection_preserves_identity_and_bound(self):
        selected=select_readiness(domain='RD-01',limit=3)
        self.assertTrue(selected);self.assertLessEqual(len(selected),3)
        self.assertTrue(all(r['readiness_domain_id']=='RD-01' for r in selected))
        with self.assertRaises(ValueError):select_readiness(limit=1148)

    def test_source_status_cannot_override_missing_evidence_or_blocker(self):
        unit=select_readiness(keyword='evidence',limit=1)[0]['source_unit_id']
        base={'production_intent':False,'readiness_requirements':[{'source_unit_id':unit,'status':'PASS','applicability':'APPLICABLE'}]}
        self.assertEqual(evidence_gate_engine(base)['gate_state'],'RED')
        for status in ('FAIL','UNKNOWN','CONDITIONAL PASS'):
            candidate=copy.deepcopy(base);candidate['readiness_requirements'][0]['status']=status;candidate['aggregate_score']=100
            self.assertEqual(evidence_gate_engine(candidate)['gate_state'],'RED')
        base['readiness_requirements'][0].update(status='NOT APPLICABLE',applicability='NOT_APPLICABLE')
        self.assertTrue(evaluate(base)['blocked'])
        base['readiness_requirements'][0].update(applicability_rationale='Documentation change',applicability_basis='Approved task scope excludes production behavior')
        self.assertFalse(evaluate(base)['blocked'])
        base['readiness_requirements'].append(base['readiness_requirements'][0])
        with self.assertRaises(ValueError):evaluate(base)

    def test_traceability_rejects_forged_resolves_and_swapped_definition(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'graph.jsonl';generate(path)
            original=path.read_text();data=[json.loads(x) for x in original.splitlines()]
            data[0]['nodes'][0]['resolves']=True
            path.write_text('\n'.join(json.dumps(x) for x in data))
            with self.assertRaises(ValueError):validate(path)
            data[0]['nodes'][0].pop('resolves');data[0]['nodes'][3]=data[1]['nodes'][3]
            path.write_text('\n'.join(json.dumps(x) for x in data))
            with self.assertRaises(ValueError):validate(path)

    def test_name_matches_are_not_validated_equivalence_or_specialization(self):
        graph=RiskGraph();result=graph.query('relationship',limit=500)
        self.assertEqual(result['total_matches'],len(graph.variants))
        self.assertTrue(all(r['relationship_type']=='VARIANT_OF' for r in result['results']))

    def test_selector_uses_contextual_review_and_keeps_raw_provenance(self):
        import subprocess
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/select-risk-model2.py'),'--id','5.6.17','--retrieval-level','4'],capture_output=True,text=True,encoding='utf-8',check=True)
        record=json.loads(proc.stdout)['records'][0]
        self.assertEqual(record['semantic_review_status'],'CORRECTED')
        self.assertIn('serial',record['failure_mechanism'].casefold())
        self.assertNotEqual(record['failure_mechanism'],record['raw_record']['fields']['Failure mechanism'])
        self.assertEqual(record['activation_state'],'installed_not_default')

if __name__=='__main__':unittest.main()
