import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/classify-controls.py"


class ApplicabilitySemanticsTests(unittest.TestCase):
    def run_classify(self, controls, check=True):
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "assessments.json"
            out = Path(td) / "out.json"
            inp.write_text(json.dumps({"controls": controls}), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--assessments", str(inp), "--output", str(out)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if check:
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
            return proc, payload

    def by_no(self, payload, no=1):
        return next(c for c in payload["controls"] if c["control_no"] == no)

    def test_unresolved_controls_escalate_instead_of_silently_applying(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["controls"]), 75)
        self.assertTrue(all(c["applicability"] == "ESCALATE" for c in payload["controls"]))
        self.assertTrue(all(c["result"] == "HUMAN REVIEW" for c in payload["controls"]))

    def test_conditional_true_resolves_to_applies_and_creates_obligation(self):
        _, payload = self.run_classify({"1": {
            "applicability": "CONDITIONAL", "condition": "project stores customer data",
            "condition_result": "TRUE", "result": "UNKNOWN"
        }})
        c = self.by_no(payload)
        self.assertEqual(c["requested_applicability"], "CONDITIONAL")
        self.assertEqual(c["applicability"], "APPLIES")
        self.assertTrue(c["obligation_required"])

    def test_conditional_false_resolves_to_not_applicable_with_reason(self):
        _, payload = self.run_classify({"1": {
            "applicability": "CONDITIONAL", "condition": "project is multi-tenant SaaS",
            "condition_result": "FALSE", "not_applicable_reason": "Static marketing website has no tenants"
        }})
        c = self.by_no(payload)
        self.assertEqual(c["applicability"], "NOT_APPLICABLE")
        self.assertEqual(c["result"], "NOT_APPLICABLE")
        self.assertFalse(c["obligation_required"])

    def test_conditional_unknown_escalates(self):
        _, payload = self.run_classify({"1": {
            "applicability": "CONDITIONAL", "condition": "regulated data may be processed",
            "condition_result": "UNKNOWN"
        }})
        c = self.by_no(payload)
        self.assertEqual(c["applicability"], "ESCALATE")
        self.assertEqual(c["result"], "HUMAN REVIEW")

    def test_not_applicable_requires_evidence_based_reason(self):
        proc, _ = self.run_classify({"1": {"applicability": "NOT_APPLICABLE"}}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("NOT_APPLICABLE requires", proc.stderr)

    def test_already_satisfied_uses_existing_evidence_without_duplicate_obligation(self):
        _, payload = self.run_classify({"1": {
            "applicability": "APPLIES", "already_satisfied": True,
            "evidence_ids": ["E-existing"], "result": "GREEN"
        }})
        c = self.by_no(payload)
        self.assertTrue(c["already_satisfied"])
        self.assertFalse(c["obligation_required"])
        self.assertEqual(c["evidence_ids"], ["E-existing"])
        self.assertEqual(c["result"], "GREEN")

    def test_newly_green_applicable_control_requires_evidence(self):
        proc, _ = self.run_classify({"1": {
            "applicability": "APPLIES", "already_satisfied": False,
            "result": "GREEN", "evidence_ids": []
        }}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("GREEN APPLIES control requires evidence_ids", proc.stderr)

    def test_newly_green_applicable_control_accepts_bound_evidence_id(self):
        _, payload = self.run_classify({"1": {
            "applicability": "APPLIES", "already_satisfied": False,
            "result": "GREEN", "evidence_ids": ["E-NEW"]
        }})
        c = self.by_no(payload)
        self.assertEqual(c["result"], "GREEN")
        self.assertTrue(c["obligation_required"])
        self.assertEqual(c["evidence_ids"], ["E-NEW"])

    def test_forbidden_is_blocking_without_human_override(self):
        proc, payload = self.run_classify({"1": {
            "applicability": "FORBIDDEN", "forbidden_reason": "Action violates production policy"
        }}, check=False)
        self.assertEqual(proc.returncode, 4)
        c = self.by_no(payload)
        self.assertEqual(c["result"], "BLOCKED")

    def test_forbidden_rejects_ai_override(self):
        proc, _ = self.run_classify({"1": {
            "applicability": "FORBIDDEN", "forbidden_reason": "Action violates production policy",
            "authorized_override": {"approval_id": "A-1", "authority": "Codex", "rationale": "model says yes"}
        }}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("accountable human authority", proc.stderr)

    def test_forbidden_accepts_explicit_accountable_human_override_but_not_fake_green(self):
        _, payload = self.run_classify({"1": {
            "applicability": "FORBIDDEN", "forbidden_reason": "Normally prohibited production action",
            "authorized_override": {"approval_id": "A-HUMAN", "authority": "Accountable Product Owner", "rationale": "documented exception"}
        }})
        c = self.by_no(payload)
        self.assertEqual(c["applicability"], "FORBIDDEN")
        self.assertEqual(c["result"], "HUMAN REVIEW")


if __name__ == "__main__":
    unittest.main()
