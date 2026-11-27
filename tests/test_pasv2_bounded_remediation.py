import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from risk_concern_runtime import RiskConcernError, validate_acceptance_record, validate_concern_runtime
from runtime_state import environment_binding


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_jsonl(path: Path):
    return [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in jsonl(path)]


def run_script(name, *args, check=True):
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check:
        assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


class PASV2BoundedRemediationTests(unittest.TestCase):
    def test_concern_runtime_keeps_definition_independent_from_operational_records(self):
        data = json.loads((ROOT / "references" / "risks" / "model2" / "concern-runtime-evidence.json").read_text(encoding="utf-8"))
        result = validate_concern_runtime(data)
        self.assertEqual(result["definitions"], 3)
        self.assertEqual(result["assessments"], 3)
        self.assertGreaterEqual(result["independent_definitions"], 1)
        self.assertEqual(result["current_acceptances"], 0)
        self.assertEqual(result["temporally_eligible_acceptances"], 1)
        versions = {item["definition_version"] for item in data["definitions"] if item["risk_definition_id"] == data["definitions"][0]["risk_definition_id"]}
        self.assertEqual(versions, {"1.0.0", "1.1.0"})

    def test_concern_runtime_rejects_orphan_or_mismatched_definition_refs(self):
        data = json.loads((ROOT / "references" / "risks" / "model2" / "concern-runtime-evidence.json").read_text(encoding="utf-8"))
        data["economics"][0]["risk_definition_id"] = "RDEF-MISSING"
        with self.assertRaisesRegex(RiskConcernError, "missing RiskDefinition"):
            validate_concern_runtime(data)

    def test_acceptance_current_authority_rules_include_revocation_and_staleness(self):
        base = {
            "acceptance_id": "RA-T",
            "risk_ids": ["RDEF-X@1.0.0"],
            "risk_definition_id": "RDEF-X",
            "definition_version": "1.0.0",
            "risk_assessment_id": "RAS-X",
            "authority": "Accountable Product Owner",
            "reason": "temporary exposure",
            "residual_risk": "bounded integration exposure",
            "compensating_controls": [],
            "scope": "bounded release",
            "scope_hash": "scope-a",
            "current_scope_hash": "scope-a",
            "approved_at": "2026-09-14T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "review_trigger": "definition or scope change",
            "status": "ACTIVE",
            "current_authority": True,
        }
        self.assertTrue(validate_acceptance_record(dict(base)))
        ai = dict(base, authority="Codex")
        with self.assertRaisesRegex(RiskConcernError, "AI/tool"):
            validate_acceptance_record(ai)
        stale = dict(base, current_definition_version="1.1.0")
        with self.assertRaisesRegex(RiskConcernError, "cannot be current"):
            validate_acceptance_record(stale)
        revoked = dict(base, status="REVOKED", revoked_at="2026-09-15T00:00:00Z", revoked_by="Chief Risk Owner", revocation_reason="control landed")
        with self.assertRaisesRegex(RiskConcernError, "cannot be current"):
            validate_acceptance_record(revoked)
        bad_revoke = dict(revoked, current_authority=False, revoked_by="gstack")
        with self.assertRaisesRegex(RiskConcernError, "AI/tool revoking"):
            validate_acceptance_record(bad_revoke)

    def test_acceptance_cli_rejects_revoked_as_current_but_accepts_archive_mode(self):
        record = {
            "acceptance_id": "RA-ARCHIVE",
            "risk_ids": ["RDEF-X@1.0.0"],
            "risk_definition_id": "RDEF-X",
            "definition_version": "1.0.0",
            "authority": "Chief Risk Owner",
            "reason": "revoked after mitigation",
            "residual_risk": "historical integration exposure",
            "compensating_controls": [],
            "scope": "old release",
            "approved_at": "2026-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "review_trigger": "control landed",
            "status": "REVOKED",
            "revoked_at": "2026-09-15T00:00:00Z",
            "revoked_by": "Chief Risk Owner",
            "revocation_reason": "replacement control available",
            "current_authority": False,
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "acceptance.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            current = run_script("validate-risk-acceptance.py", path, check=False)
            self.assertNotEqual(current.returncode, 0)
            self.assertIn("not current acceptance authority", current.stdout)
            archive = run_script("validate-risk-acceptance.py", "--allow-noncurrent", path)
            self.assertIn("PASS risk acceptance", archive.stdout)

    def test_semantic_sentinels_are_corrected_without_raw_overwrite(self):
        proc = run_script("semantic-risk-validator.py")
        self.assertIn("PASS semantic risk validation", proc.stdout)
        raw = {row["risk_id"]: row for row in jsonl(ROOT / "references" / "risks" / "model2" / "risk-corpus.jsonl")}
        raw_a = json.dumps(raw["4.1.21"], ensure_ascii=False).lower()
        raw_b = json.dumps(raw["5.6.17"], ensure_ascii=False).lower()
        self.assertTrue(any(token in raw_a for token in ("concurrent", "shared state", "lost update", "isolation strategy")))
        self.assertTrue(any(token in raw_b for token in ("sensor", "control command", "control loop", "interlock")))
        defs = jsonl(ROOT / "references" / "risks" / "model2" / "normalized-risk-definitions.jsonl")
        by_source = {source: row for row in defs for source in row["source_records"]}
        a = json.dumps(by_source["4.1.21"].get("normalized_definition"), ensure_ascii=False).lower()
        b = json.dumps(by_source["5.6.17"].get("normalized_definition"), ensure_ascii=False).lower()
        self.assertIn("serialization", a)
        self.assertIn("encoding", a)
        self.assertNotIn("shared state", a)
        self.assertIn("pharmaceutical", b)
        self.assertIn("traceability", b)
        self.assertNotIn("control loop", b)

    def test_relationship_validator_accepts_full_graph_and_rejects_orphan_endpoint(self):
        ok = run_script("validate-risk-relationships.py")
        self.assertIn("4337 variants", ok.stdout)
        with tempfile.TemporaryDirectory() as td:
            rel = Path(td) / "relationships.jsonl"
            rel.write_text((ROOT / "references" / "risks" / "model2" / "risk-relationships.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            with rel.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"relationship_id": "REL-BAD", "relationship_type": "RELATED_TO", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "MISSING"}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "MISSING2"}, "provenance_class": "human-reviewed relation", "evidence_reference": "unit-test", "confidence": 0.5, "review_status": "VALIDATED_BY_RULE"}) + "\n")
            bad = run_script("validate-risk-relationships.py", "--relationships", rel, check=False)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("orphan", bad.stderr + bad.stdout)

    def test_source2_readiness_ledger_is_complete_and_mapped(self):
        proc = run_script("validate-readiness.py")
        self.assertIn("1148 semantic units", proc.stdout)
        rows = jsonl(ROOT / "references" / "readiness" / "source2-readiness-units.jsonl")
        self.assertEqual(len(rows), 1148)
        self.assertEqual(len({row["readiness_domain_id"] for row in rows if row["readiness_domain_id"].startswith("RD-") and row["readiness_domain_id"] != "RD-GLOBAL"}), 36)
        self.assertIn("required_evidence_item", {row["classification"] for row in rows})
        self.assertTrue(all(row["target_artifacts"] for row in rows))
        deterministic = [row for row in rows if row.get("mapping_status") != "HUMAN_REVIEW_REQUIRED"]
        supplemental = [row for row in rows if row.get("mapping_policy_id") == "SOURCE2-CONTEXTUAL-REQUIREMENT"]
        self.assertTrue(all(row["preos_gates"] and (row["preos_control_ids"] or row.get('supplemental_requirement_id')==row['source_unit_id']) for row in deterministic))
        self.assertTrue(supplemental)
        self.assertTrue(all(row['preos_gates']==['G11'] and not row['preos_control_ids'] and row['supplemental_requirement_id']==row['source_unit_id'] for row in supplemental))
        self.assertIn("gstack-cso", {row["gstack_specialist_route"] for row in deterministic})
        self.assertIn("gstack-benchmark", {row["gstack_specialist_route"] for row in deterministic})
        self.assertIn("gstack-design-review", {row["gstack_specialist_route"] for row in deterministic})


    def test_model2_generator_is_idempotent_and_validator_clean(self):
        model2 = ROOT / "references" / "risks" / "model2"
        with tempfile.TemporaryDirectory() as td:
            input_dir = Path(td) / "input"
            output_dir = Path(td) / "output"
            input_dir.mkdir()
            for name in ("risk-corpus.jsonl", "concern-runtime-evidence.json"):
                shutil.copyfile(model2 / name, input_dir / name)
            proc = run_script("generate-model2-remediation.py", "--input-dir", input_dir, "--output-dir", output_dir)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["definitions"], len(jsonl(model2 / "normalized-risk-definitions.jsonl")))
            self.assertEqual(payload["reviews"], len(jsonl(model2 / "semantic-review-ledger.jsonl")))
            self.assertEqual(payload["human_review_required"], 4335)
            sem = run_script("semantic-risk-validator.py", "--definitions", output_dir / "normalized-risk-definitions.jsonl", "--reviews", output_dir / "semantic-review-ledger.jsonl")
            self.assertIn("PASS semantic risk validation", sem.stdout)
            rel = run_script("validate-risk-relationships.py", "--definitions", output_dir / "normalized-risk-definitions.jsonl", "--variants", output_dir / "risk-context-variants.jsonl", "--relationships", output_dir / "risk-relationships.jsonl", "--types", output_dir / "risk-relationship-types.json")
            self.assertIn("PASS risk relationship validation", rel.stdout)
            concerns = run_script("validate-risk-concerns.py", output_dir / "concern-runtime-evidence.json")
            self.assertIn("PASS risk concern linkage", concerns.stdout)
            for name in (
                "normalized-risk-definitions.jsonl",
                "semantic-review-ledger.jsonl",
                "risk-context-variants.jsonl",
                "risk-relationships.jsonl",
            ):
                self.assertEqual(canonical_jsonl(output_dir / name), canonical_jsonl(model2 / name), name)
            relationship_text = (output_dir / "risk-relationships.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("Vocabulary support exemplar", relationship_text)

    def test_readiness_generator_is_idempotent_and_validator_clean(self):
        readiness = ROOT / "references" / "readiness"
        with tempfile.TemporaryDirectory() as td:
            output_dir = Path(td) / "readiness"
            proc = run_script("generate-readiness-remediation.py", "--output-dir", output_dir, "--skip-traceability")
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["source2_readiness_units"], 1148)
            validation = run_script("validate-readiness.py", "--source2", output_dir / "source2-readiness-units.jsonl")
            self.assertIn("PASS Source 2 readiness ledger", validation.stdout)
            self.assertEqual(
                canonical_jsonl(output_dir / "source2-readiness-units.jsonl"),
                canonical_jsonl(readiness / "source2-readiness-units.jsonl"),
            )
            generated = jsonl(output_dir / "source2-readiness-units.jsonl")
            self.assertTrue(any(row.get("mapping_policy_id") == "SOURCE2-CONTEXTUAL-REQUIREMENT" for row in generated))
            self.assertTrue(all(row['preos_gates']==['G11'] and not row['preos_control_ids'] for row in generated if row.get('mapping_policy_id')=='SOURCE2-CONTEXTUAL-REQUIREMENT'))

    def test_selector_filters_and_retrieval_levels_are_bounded(self):
        one = run_script("select-risk-model2.py", "--id", "4.1.21", "--retrieval-level", "1", "--limit", "1")
        payload = json.loads(one.stdout)
        self.assertEqual(payload["count"], 1)
        level1 = payload["records"][0]
        for key in ("risk_id", "canonical_name", "category", "severity_hint"):
            self.assertIn(key, level1)
        self.assertNotIn("raw_record", level1)
        self.assertNotIn("normalized_definition", level1)
        two = run_script("select-risk-model2.py", "--canonical-name", "Serialization Failure", "--retrieval-level", "2", "--limit", "1")
        level2 = json.loads(two.stdout)["records"][0]
        for key in ("trigger", "failure_mechanism", "required_controls"):
            self.assertIn(key, level2)
            self.assertTrue(level2[key])
        three = run_script("select-risk-model2.py", "--alias", "Serialization Failure", "--retrieval-level", "3", "--limit", "1")
        level3 = json.loads(three.stdout)["records"][0]
        for key in ("tests", "monitoring", "recovery", "evidence"):
            self.assertIn(key, level3)
            self.assertTrue(level3[key])
        four = run_script("select-risk-model2.py", "--source-variant-id", "RCV-S1-4-1-21", "--relationship", "VARIANT_OF", "--retrieval-level", "4", "--limit", "1")
        payload = json.loads(four.stdout)
        self.assertEqual(payload["count"], 1)
        self.assertIn("raw_record", payload["records"][0])
        self.assertIn("relationships", payload["records"][0])

    def test_live_evidence_comparison_and_invalidation_mark_stale_bindings(self):
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        good = {
            "evidence_id": "E-PASV2-GOOD",
            "produced_at": "2026-09-15T00:00:00Z",
            "producer": "test",
            "environment": "unit",
            "artifact_location": "unit",
            "validity": "CURRENT",
            "commit_sha": head,
            "bindings": {
                "git_head": head,
                "source_hashes": [],
                "configuration_files": [],
                "schema_files": [],
                "dependency_files": [],
                "test_definition_files": [],
                "environment": environment_binding([]),
            },
        }
        stale = dict(good, evidence_id="E-PASV2-STALE", commit_sha="deadbeef")
        stale["bindings"] = dict(good["bindings"], git_head="deadbeef")
        with tempfile.TemporaryDirectory() as td:
            good_path = Path(td) / "good.json"
            stale_path = Path(td) / "stale.json"
            out_path = Path(td) / "out.json"
            good_path.write_text(json.dumps(good), encoding="utf-8")
            stale_path.write_text(json.dumps(stale), encoding="utf-8")
            ok = run_script("validate-evidence.py", "--require-complete-bindings", "--evaluate-current-state", "--repo", ROOT, good_path)
            self.assertIn("live binding comparison", ok.stdout)
            bad = run_script("validate-evidence.py", "--require-complete-bindings", "--evaluate-current-state", "--repo", ROOT, stale_path, check=False)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("commit changed", bad.stdout)
            invalidated = run_script("invalidate-stale-evidence.py", "--repo", ROOT, "--output", out_path, stale_path)
            self.assertIn("STALE", invalidated.stdout)
            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["validity"], "STALE")

    def test_traceability_chain_reaches_release_incident_learning_with_explicit_na(self):
        proc = run_script("validate-traceability-chain.py")
        self.assertIn("PASS traceability chain", proc.stdout)
        result=json.loads(proc.stdout.split('PASS traceability chain: ',1)[1])
        self.assertEqual(result['records'],8556)
        self.assertTrue(result['unbound_project_links_explicit'])


if __name__ == "__main__":
    unittest.main()
