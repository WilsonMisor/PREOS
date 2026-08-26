import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SPEC = importlib.util.spec_from_file_location("runtime_state_acceptance", SCRIPTS / "runtime_state.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()


class SessionLossAcceptanceTests(unittest.TestCase):
    """Explicit coverage for master-plan interruption acceptance rows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "session-loss@example.invalid")
        git(self.repo, "config", "user.name", "Session Loss Acceptance")
        (self.repo / "README.md").write_text("baseline\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")
        self.old_state = os.environ.get("PREOS_STATE_ROOT")
        os.environ["PREOS_STATE_ROOT"] = str(self.base / "state")

    def tearDown(self):
        if self.old_state is None:
            os.environ.pop("PREOS_STATE_ROOT", None)
        else:
            os.environ["PREOS_STATE_ROOT"] = self.old_state
        self.tmp.cleanup()

    def checkpoint(self, **extra):
        root = MOD.production_root("acceptance")
        (root / "checkpoints").mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": "1.1",
            "checkpoint_id": "CP-ACCEPTANCE-SOFT",
            "checkpoint_kind": "SOFT",
            "project_id": "acceptance",
            "updated_at": MOD.utc_now(),
            "current_stage": "production-implementation",
            "last_verified_action": "TP-001 verified",
            "next_unverified_action": "start TP-002",
            "required_approval_ids": [],
            "bindings": {},
            "git": MOD.git_snapshot(self.repo),
        }
        state.update(extra)
        MOD.atomic_write_json(root / "checkpoints" / "CP-ACCEPTANCE-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        MOD.atomic_write_json(root / "approval-state.json", {
            "schema_version": "1.1", "project_id": "acceptance",
            "updated_at": MOD.utc_now(), "approvals": [],
        })
        MOD.atomic_write_json(root / "evidence-index.json", {
            "schema_version": "1.1", "project_id": "acceptance",
            "updated_at": MOD.utc_now(), "evidence": [],
        })
        (root / "implementation-ledger.jsonl").touch(exist_ok=True)
        (root / "recovery-events.jsonl").touch(exist_ok=True)
        return root, state

    def test_session_end_between_task_packets_resumes_next_ready_packet(self):
        self.checkpoint()
        result = MOD.reconcile_project("acceptance", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["next_unverified_action"], "start TP-002")

    def test_passed_test_without_persisted_evidence_remains_incomplete(self):
        self.checkpoint(
            last_verified_action="integration test passed",
            next_unverified_action="security review",
            pending_evidence="E-INTEGRATION-RESULT",
        )
        result = MOD.reconcile_project("acceptance", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["next_unverified_action"], "capture pending evidence: E-INTEGRATION-RESULT")

    def test_gstack_context_cannot_override_git_conflict(self):
        self.checkpoint()
        fake_gstack = self.base / "gstack-context.json"
        fake_gstack.write_text(json.dumps({
            "claim": "SAFE_TO_RESUME",
            "note": "semantic context only, deliberately conflicting with Git",
        }), encoding="utf-8")
        (self.repo / "README.md").write_text("external change after checkpoint\n", encoding="utf-8")
        result = MOD.reconcile_project("acceptance", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("WORKING_TREE_MISMATCH", {c["type"] for c in result["conflicts"]})
        self.assertTrue(fake_gstack.is_file())

    def test_gstack_context_cannot_override_project_contract_conflict(self):
        contract = self.repo / "project-contract.json"
        contract.write_text(json.dumps({"project_id": "acceptance", "source_hashes": []}), encoding="utf-8")
        git(self.repo, "add", "project-contract.json")
        git(self.repo, "commit", "-m", "bind project contract")
        root, state = self.checkpoint()
        state["bindings"] = {"project_contract": MOD.file_binding(contract, self.repo)}
        state["git"] = MOD.git_snapshot(self.repo)
        state["updated_at"] = MOD.utc_now()
        MOD.atomic_write_json(root / "checkpoints" / "CP-CONTRACT-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        (self.base / "gstack-context.json").write_text(json.dumps({"claim": "contract approved"}), encoding="utf-8")
        contract.write_text(json.dumps({"project_id": "acceptance", "source_hashes": [], "silently_changed": True}), encoding="utf-8")
        result = MOD.reconcile_project("acceptance", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("PROJECT_CONTRACT_HASH_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_source_change_invalidates_bound_evidence(self):
        source = self.repo / "requirements.md"
        source.write_text("approved requirement v1\n", encoding="utf-8")
        contract = self.repo / "project-contract.json"
        contract.write_text(json.dumps({
            "project_id": "acceptance",
            "source_hashes": [{"artifact": "requirements.md", "sha256": MOD.sha256_file(source)}],
        }), encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "governed source and contract")
        root, state = self.checkpoint()
        state["bindings"] = {"project_contract": MOD.file_binding(contract, self.repo)}
        state["git"] = MOD.git_snapshot(self.repo)
        state["updated_at"] = MOD.utc_now()
        MOD.atomic_write_json(root / "checkpoints" / "CP-SOURCE-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        MOD.atomic_write_json(root / "evidence-index.json", {
            "schema_version": "1.1",
            "project_id": "acceptance",
            "updated_at": MOD.utc_now(),
            "evidence": [{
                "evidence_id": "E-SOURCE-BOUND",
                "status": "FRESH",
                "bindings": {
                    "git_head": state["git"]["head"],
                    "project_contract": state["bindings"]["project_contract"],
                    "source_hashes": [{"path": "requirements.md", "sha256": MOD.sha256_file(source)}],
                },
            }],
        })
        source.write_text("approved requirement v2\n", encoding="utf-8")
        result = MOD.reconcile_project("acceptance", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("SOURCE_HASH_MISMATCH", {c["type"] for c in result["conflicts"]})
        self.assertIn("E-SOURCE-BOUND", result["stale_evidence"])


if __name__ == "__main__":
    unittest.main()
