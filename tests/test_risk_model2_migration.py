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
        self.assertIn("not installed before crosswalk gate", proc.stdout)

    def test_project_contract_schema_and_template_declare_risk_corpus(self):
        schema = json.loads((ROOT / "schemas" / "project-contract.schema.json").read_text(encoding="utf-8"))
        template = json.loads((ROOT / "templates" / "project-contract.json").read_text(encoding="utf-8"))
        self.assertIn("risk_corpus", schema["required"])
        self.assertEqual(schema["properties"]["risk_corpus"]["properties"]["version"]["enum"], ["legacy-v1", "model2"])
        self.assertEqual(template["risk_corpus"]["version"], "legacy-v1")
        self.assertFalse(template["risk_corpus"]["activation_allowed"])


if __name__ == "__main__":
    unittest.main()
