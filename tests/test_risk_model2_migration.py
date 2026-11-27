import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from preos_common import iter_risks
from schema_validation import load_schema, validate_instance

spec = importlib.util.spec_from_file_location("validate_risk_model2", SCRIPTS / "validate-risk-model2.py")
validate_risk_model2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_risk_model2)


class RiskModel2MigrationTests(unittest.TestCase):
    def test_crosswalk_has_explicit_disposition_per_legacy_risk(self):
        crosswalk_path = ROOT / "references" / "risks" / "migration" / "legacy-to-model2-crosswalk.json"
        schema_path = ROOT / "references" / "risks" / "migration" / "legacy-to-model2-crosswalk.schema.json"
        rows = json.loads(crosswalk_path.read_text(encoding="utf-8"))
        schema = load_schema(schema_path)
        legacy_ids = {risk["check_id"] for risk in iter_risks(ROOT)}
        self.assertEqual(len(rows), 1130)
        self.assertEqual({row["v1_risk_id"] for row in rows}, legacy_ids)
        for row in rows[:10]:
            validate_instance(row, schema, root_schema=schema)
        self.assertTrue(all(row["disposition"] for row in rows))

    def test_unresolved_crosswalk_rows_do_not_activate_model2(self):
        rows = json.loads((ROOT / "references" / "risks" / "migration" / "legacy-to-model2-crosswalk.json").read_text(encoding="utf-8"))
        unresolved = [row for row in rows if row["disposition"] == "UNRESOLVED"]
        self.assertEqual(len(unresolved), 1130)
        self.assertTrue(all(row["review_status"] == "HUMAN_REVIEW_REQUIRED" for row in unresolved))
        self.assertTrue(all(row["v2_risk_ids"] == [] for row in unresolved))

    def test_validator_passes_pre_activation_and_reports_disabled_gate(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "validate-risk-model2.py")], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("activation gate: disabled", proc.stdout)
        self.assertIn("model2 catalogue: 4337 records validated", proc.stdout)

    def test_project_contract_schema_and_template_declare_risk_corpus(self):
        schema = json.loads((ROOT / "schemas" / "project-contract.schema.json").read_text(encoding="utf-8"))
        template = json.loads((ROOT / "templates" / "project-contract.json").read_text(encoding="utf-8"))
        self.assertIn("risk_corpus", schema["required"])
        risk_schema = schema["properties"]["risk_corpus"]
        self.assertEqual(risk_schema["properties"]["version"]["enum"], ["legacy-v1", "model2"])
        for field in ["semantic_review", "approval_gate", "human_approval_record", "source_version_hashes"]:
            self.assertIn(field, risk_schema["required"])
            self.assertIn(field, template["risk_corpus"])
        validate_instance(template, schema, root_schema=schema)
        self.assertEqual(template["risk_corpus"]["version"], "legacy-v1")
        self.assertFalse(template["risk_corpus"]["activation_allowed"])
        self.assertEqual(template["risk_corpus"]["approval_gate"]["status"], "OPEN")
        self.assertIsNone(template["risk_corpus"]["human_approval_record"])

    def test_model2_activation_requires_human_approval_binding(self):
        template = json.loads((ROOT / "templates" / "project-contract.json").read_text(encoding="utf-8"))
        active = copy.deepcopy(template)
        active["risk_corpus"].update({"version": "model2", "activation_allowed": True})
        with self.assertRaises(SystemExit):
            validate_risk_model2.validate_model2_activation_binding(active)
        active["risk_corpus"].update({
            "semantic_review": {
                "status": "COMPLETE",
                "unresolved_count": 0,
                "reviewed_at": "2026-09-22T00:00:00Z",
                "reviewer": "qualified-human-reviewer",
            },
            "approval_gate": {
                "gate_id": "PREOS_MODEL2_CROSSWALK_APPROVAL",
                "status": "APPROVED",
            },
            "human_approval_record": {
                "approval_id": "APPROVAL-1",
                "approved_by": "accountable-human",
                "approved_at": "2026-09-22T00:00:00Z",
                "authority_role": "risk acceptance authority",
                "scope": "model2 project contract activation test fixture",
            },
            "source_version_hashes": [
                {"artifact": "references/risks/model2/risk-corpus.jsonl", "sha256": "a" * 64}
            ],
        })
        validate_risk_model2.validate_model2_activation_binding(active)


if __name__ == "__main__":
    unittest.main()