import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_state", ROOT / "scripts" / "runtime_state.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


class StateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "preos-test@example.invalid")
        git(self.repo, "config", "user.name", "PREOS Test")
        (self.repo / "README.md").write_text("baseline\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "baseline")
        self.old_state = os.environ.get("PREOS_STATE_ROOT")
        os.environ["PREOS_STATE_ROOT"] = str(self.base / "state")

    def tearDown(self):
        if self.old_state is None:
            os.environ.pop("PREOS_STATE_ROOT", None)
        else:
            os.environ["PREOS_STATE_ROOT"] = self.old_state
        self.tmp.cleanup()

    def checkpoint(self, project="p1", last="unit tests passed", next_action="integration tests"):
        root = MOD.production_root(project)
        (root / "checkpoints").mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": "1.0",
            "checkpoint_id": "CP-1-SOFT",
            "checkpoint_kind": "SOFT",
            "project_id": project,
            "updated_at": MOD.utc_now(),
            "current_stage": "production-implementation",
            "last_verified_action": last,
            "next_unverified_action": next_action,
            "bindings": {},
            "git": MOD.git_snapshot(self.repo),
        }
        MOD.atomic_write_json(root / "checkpoints" / "CP-1-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        MOD.atomic_write_json(root / "approval-state.json", {"project_id": project, "approvals": []})
        MOD.atomic_write_json(root / "evidence-index.json", {"project_id": project, "evidence": []})
        return root, state

    def test_clean_recovery_resumes_first_unverified_action(self):
        self.checkpoint()
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["last_verified_action"], "unit tests passed")
        self.assertEqual(result["next_unverified_action"], "integration tests")

    def test_pending_approval_survives_and_blocks(self):
        root, _ = self.checkpoint()
        MOD.atomic_write_json(root / "approval-state.json", {"project_id": "p1", "approvals": [{"approval_id": "A-1", "status": "PENDING"}]})
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["pending_approvals"], ["A-1"])

    def test_dirty_tree_mismatch_is_recovery_conflict(self):
        self.checkpoint()
        (self.repo / "README.md").write_text("changed after checkpoint\n", encoding="utf-8")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("WORKING_TREE_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_head_change_is_recovery_conflict(self):
        self.checkpoint()
        (self.repo / "next.txt").write_text("new\n", encoding="utf-8")
        git(self.repo, "add", "next.txt")
        git(self.repo, "commit", "-m", "unexpected")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("HEAD_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_source_hash_drift_is_recovery_conflict(self):
        root, state = self.checkpoint()
        source = self.repo / "prd.md"
        source.write_text("v1", encoding="utf-8")
        contract = self.repo / "contract.json"
        contract.write_text(json.dumps({"source_hashes": [{"artifact": "prd.md", "sha256": MOD.sha256_file(source)}]}), encoding="utf-8")
        state["bindings"] = {"project_contract": MOD.file_binding(contract, self.repo)}
        state["git"] = MOD.git_snapshot(self.repo)
        MOD.atomic_write_json(root / "checkpoints" / "CP-2-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        source.write_text("v2", encoding="utf-8")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("SOURCE_HASH_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_corrupt_newest_state_is_rejected(self):
        root, _ = self.checkpoint()
        bad = root / "checkpoints" / "CP-Z-BAD.json"
        bad.write_text("{", encoding="utf-8")
        stat = bad.stat()
        os.utime(bad, (stat.st_atime + 10, stat.st_mtime + 10))
        with self.assertRaises(ValueError):
            MOD.load_latest_state(root)


if __name__ == "__main__":
    unittest.main()
