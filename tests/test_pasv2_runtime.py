import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pasv2_runtime as rt


class PASV2RuntimeTests(unittest.TestCase):
    def test_candidate_risk_workflow_blocks_unapproved_generated_candidates(self):
        candidate = {
            "canonical_name": "Novel Provider Reconciliation Drift",
            "provenance_class": "ENGINEERING_EXPANSION",
            "source": {"class": "incident-derived", "incident_id": "INC-001"},
        }
        result = rt.evaluate_candidate_risk(candidate)
        self.assertFalse(result["promotion_allowed"])
        self.assertEqual(result["canonicalization_decision"], "QUEUE_HUMAN_REVIEW")
        with self.assertRaisesRegex(ValueError, "candidate cannot be promoted"):
            rt.promote_candidate_risk(candidate)

    def test_candidate_compatibility_api_cannot_promote_from_caller_approval_flags(self):
        candidate = {
            "canonical_name": "Novel Provider Reconciliation Drift",
            "provenance_class": "ENGINEERING_EXPANSION",
            "source": {"class": "incident-derived", "incident_id": "INC-001"},
        }
        with self.assertRaisesRegex(ValueError, 'durable scoped PREOS approval'):
            rt.promote_candidate_risk(candidate, {"approved": True, "qualified_human": True, "reviewer": "Chief Risk Owner"})

    def test_five_engines_execute_required_contracts(self):
        result = rt.run_five_engines(rt.high_assurance_fixture(), evidence={})
        self.assertIn("Context Engine", result["context"]["engine"])
        self.assertEqual(set(result.keys()), {"context", "risk_generation", "economics_complexity", "evolution", "evidence_gate"})
        self.assertEqual(result["risk_generation"]["axes_considered"], rt.RISK_GENERATION_AXES)
        self.assertIn("attacker replay", result["risk_generation"]["withdrawal_transfer_regression"])
        self.assertEqual(result["economics_complexity"]["cost_dimensions_available"], 25)
        self.assertEqual(result["evidence_gate"]["gate_state"], "RED")

    def test_nondeferrable_controls_block_first_release_and_can_be_not_applicable(self):
        blocked = rt.evaluate_nondeferrable_controls({"first_production_release": True}, evidence={})
        self.assertTrue(blocked["blocked"])
        self.assertEqual(len(blocked["results"]), 20)
        self.assertTrue(any(row["state"] == "BLOCKING_MISSING_EVIDENCE" for row in blocked["results"]))
        na = rt.evaluate_nondeferrable_controls({"production_intent": False, "first_production_release": False}, evidence={})
        self.assertFalse(na["blocked"])
        self.assertTrue(all(row["state"] == "NOT_APPLICABLE" for row in na["results"]))

    def test_graph_queries_return_real_edges_or_honest_empty_results(self):
        relation = rt.query_risk_graph("relationship", limit=3)
        self.assertEqual(relation["total_matches"], 4337)  # Only structural VARIANT_OF links are validated.
        self.assertIn(relation["results"][0]["relationship_type"], {"VARIANT_OF", "SAME_AS", "SPECIALIZES"})
        controls = rt.query_risk_graph("mitigated-by", "FS-004", limit=3)
        self.assertEqual(controls["total_matches"], 0)  # A contextual FS-004 hint is not a validated mitigation edge.
        causes = rt.query_risk_graph("causes", limit=3)
        self.assertEqual(causes["total_matches"], 0)
        self.assertEqual(causes["empty_result_policy"], "NO_VALIDATED_RELATION_EXISTS")

    def test_source4_completeness_is_computed_and_report_has_20_sections(self):
        checks = rt.validate_source4_completeness()
        self.assertEqual(checks["total_checks"], 34)
        self.assertEqual(checks["failed_checks"], 0)
        report = rt.source4_report()
        self.assertEqual(report.count("## "), 20)
        self.assertIn("Completeness checks: 34 total, 0 failed", report)

    def test_lifecycle_traceability_has_resolving_deep_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trace.jsonl"
            generated = rt.generate_lifecycle_traceability(path)
            self.assertEqual(generated["records"], 8556)
            self.assertTrue(path.with_suffix(".coverage.json").is_file())
            result = rt.validate_lifecycle_traceability(path)
            self.assertTrue(result["unbound_project_links_explicit"])
            self.assertGreater(result["resolved_unique_nodes"], 8556)
            self.assertGreater(result["human_review"], 0)
            self.assertEqual(result["all_source_graph_records"], 8556)
            self.assertEqual(result["all_source_count"], 4)

    def test_high_assurance_and_low_risk_acceptance_fixtures(self):
        high = rt.evaluate_high_assurance_acceptance()
        self.assertTrue(high["pass"])
        self.assertTrue(all(high["outcomes"].values()))
        low = rt.evaluate_low_risk_proportionality()
        self.assertTrue(low["pass"])
        self.assertEqual(low["loaded_risk_count"], 0)
        self.assertEqual(low["specialist_routes"], [])

    def test_runtime_cli_and_benchmark_budget(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "pasv2_runtime.py"), "validate-all"], cwd=ROOT.parent, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        bench = payload["benchmark"]
        self.assertLess(bench["catalogue_query_ms"], bench["budgets"]["catalogue_query_ms"])
        self.assertLess(bench["selection_time_ms"], bench["budgets"]["selection_time_ms"])
        self.assertLess(bench["validation_time_ms"], bench["budgets"]["validation_time_ms"])


if __name__ == "__main__":
    unittest.main()
