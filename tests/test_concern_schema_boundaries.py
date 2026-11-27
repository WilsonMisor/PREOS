"""Independent schema and official CLI regressions for MP-REQ-00097/98/102."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from risk_concern_runtime import (CONCERN_SCHEMAS, RiskConcernError,
    validate_concern_record, validate_concern_runtime, validate_concern_schemas,
    validate_acceptance_record, verify_acceptance_authority)
from schema_validation import SchemaValidationError, validate_instance

SCOPES = 'project_contract_id project_id application_id feature_id task_packet_id branch environment release_id change_id scope_id'.split()
FORBIDDEN = SCOPES + 'risk_assessment_id assurance_state current_status acceptance risk_acceptance authority approval_id approved_at expires_at residual_risk compensating_controls evidence_freshness existing_controls gate_result'.split()


class ConcernSchemaBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'references/risks/model2/concern-runtime-evidence.json').read_text(encoding='utf-8'))
        self.schemas = {name: json.loads((ROOT / 'schemas' / file).read_text(encoding='utf-8')) for name, file in CONCERN_SCHEMAS.items()}

    def reject_both(self, record, collection):
        self.assertTrue(list(Draft202012Validator(self.schemas[collection]).iter_errors(record)))
        with self.assertRaises(RiskConcernError):
            validate_concern_record(record, collection)

    def test_all_six_fixture_collections_are_schema_valid(self):
        counts = validate_concern_schemas(self.data)
        self.assertEqual(counts, dict(definitions=3, assessments=3, economics=2, evolutions=2, evidence_bindings=2, acceptances=3))
        for collection, schema in self.schemas.items():
            Draft202012Validator.check_schema(schema)
            for record in self.data[collection]:
                Draft202012Validator(schema).validate(record)
        result = validate_concern_runtime(self.data)
        self.assertEqual(result['current_acceptances'], 0)
        self.assertEqual(result['temporally_eligible_acceptances'], 1)

    def test_all_4210_canonical_definitions_validate_without_mutation(self):
        path = ROOT / 'references/risks/model2/normalized-risk-definitions.jsonl'
        before = path.read_bytes()
        records = [json.loads(line) for line in before.splitlines()]
        self.assertEqual(len(records), 4210)
        validator = Draft202012Validator(self.schemas['definitions'])
        for record in records:
            validator.validate(record)
            validate_concern_record(record, 'definitions')
        self.assertEqual(path.read_bytes(), before)

    def test_definition_rejects_governed_state_at_all_object_boundaries(self):
        for field in FORBIDDEN:
            for placement in ('root', 'normalized_definition', 'source_locations', 'control_patterns'):
                record = copy.deepcopy(self.data['definitions'][0])
                target = record
                if placement == 'normalized_definition':
                    target = record[placement]
                elif placement == 'source_locations':
                    target = record[placement][0]
                elif placement == 'control_patterns':
                    target = record['normalized_definition'].setdefault(placement, {})
                target[field] = 'forged-governed-state'
                with self.subTest(field=field, placement=placement):
                    self.reject_both(record, 'definitions')
                    data = copy.deepcopy(self.data)
                    data['definitions'][0] = record
                    with self.assertRaisesRegex(RiskConcernError, 'schema invalid'):
                        validate_concern_runtime(data)

    def scopeless(self):
        record = copy.deepcopy(self.data['assessments'][0])
        for field in SCOPES:
            record.pop(field, None)
        return record

    def test_source_risk_id_and_context_do_not_supply_assessment_scope(self):
        record = self.scopeless()
        record['context'] = {'feature': 'unbound source text', 'project_id': 'not-an-explicit-binding'}
        self.assertIn('source_risk_id', record)
        self.reject_both(record, 'assessments')
        self.data['assessments'][0] = record
        with self.assertRaises(RiskConcernError):
            validate_concern_runtime(self.data)

    def test_each_governed_scope_passes_and_multiple_assessments_share_definition(self):
        for field in SCOPES:
            record = self.scopeless()
            record[field] = 'governed-scope-001'
            with self.subTest(field=field):
                Draft202012Validator(self.schemas['assessments']).validate(record)
                validate_concern_record(record, 'assessments')
                data = copy.deepcopy(self.data)
                data['assessments'][0] = record
                self.assertEqual(validate_concern_runtime(data)['assessments'], 3)

    def test_scope_values_and_schema_siblings_fail_closed(self):
        for field in SCOPES:
            for value in ('', '  \t\n', None, [], {}):
                record = self.scopeless()
                record[field] = value
                with self.subTest(field=field, value=value):
                    self.reject_both(record, 'assessments')
        for mutation in ('required', 'additional', 'type'):
            record = copy.deepcopy(self.data['assessments'][0])
            if mutation == 'required':
                del record['likelihood']
            elif mutation == 'additional':
                record['unrecognized'] = 'forged'
            else:
                record['severity'] = 42
            self.reject_both(record, 'assessments')

    def test_acceptance_missing_residual_or_controls_fails_before_eligibility(self):
        for field in ('residual_risk', 'compensating_controls'):
            record = copy.deepcopy(self.data['acceptances'][0])
            del record[field]
            with self.subTest(field=field):
                self.reject_both(record, 'acceptances')
                with self.assertRaisesRegex(RiskConcernError, field):
                    validate_acceptance_record(record)
                self.data['acceptances'][0] = record
                with self.assertRaisesRegex(RiskConcernError, 'schema invalid'):
                    validate_concern_runtime(self.data)
                self.setUp()

    def test_controls_are_explicit_array_and_structural_validity_is_not_approval(self):
        record = copy.deepcopy(self.data['acceptances'][0])
        self.assertEqual(record['compensating_controls'], [])
        self.assertTrue(validate_acceptance_record(record, now=datetime(2026, 11, 27, tzinfo=timezone.utc)))
        with self.assertRaisesRegex(RiskConcernError, 'approval store'):
            verify_acceptance_authority(record, None)
        for value in (None, '', 'none', {}):
            self.reject_both({**record, 'compensating_controls': value}, 'acceptances')

    def test_template_has_all_authority_verifier_fields(self):
        template = json.loads((ROOT / 'templates/risk-acceptance.json').read_text())
        Draft202012Validator(self.schemas['acceptances']).validate(template)
        for field in ('project_id', 'approval_id', 'residual_risk', 'compensating_controls'):
            self.assertIn(field, template)
        self.assertIn('REPLACE', template['approval_id'])
        self.assertFalse(template['current_authority'])

    def test_official_cli_rejects_missing_required_field_in_every_concern(self):
        fields = dict(definitions='canonical_key', assessments='applicability',
                      economics='business_consequence', evolutions='prevention_strategy',
                      evidence_bindings='automated_test', acceptances='residual_risk')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'concerns.json'
            for collection, field in fields.items():
                data = copy.deepcopy(self.data)
                del data[collection][0][field]
                path.write_text(json.dumps(data), encoding='utf-8')
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate-risk-concerns.py'), str(path)], capture_output=True, text=True)
                with self.subTest(collection=collection):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('schema invalid', result.stdout + result.stderr)
                    self.assertIn(field, result.stdout + result.stderr)
                    self.assertNotIn('PASS', result.stdout)

    def test_nonarray_collections_fail_closed(self):
        for collection in CONCERN_SCHEMAS:
            data = copy.deepcopy(self.data)
            data[collection] = {}
            with self.assertRaises(RiskConcernError):
                validate_concern_runtime(data)

    def test_combinators_do_not_skip_sibling_constraints(self):
        for keyword in ('anyOf', 'oneOf'):
            schema = {keyword: [{'required': ['scope']}], 'type': 'object',
                      'properties': {'scope': {'type': 'string'}}, 'additionalProperties': False}
            with self.assertRaises(SchemaValidationError):
                validate_instance({'scope': 'present', 'forged': True}, schema)


if __name__ == '__main__':
    unittest.main()
