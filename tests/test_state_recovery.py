import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SPEC = importlib.util.spec_from_file_location("runtime_state", SCRIPTS / "runtime_state.py")
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
        self.env = os.environ.copy()
        self.env["PREOS_STATE_ROOT"] = str(self.base / "state")

    def tearDown(self):
        if self.old_state is None:
            os.environ.pop("PREOS_STATE_ROOT", None)
        else:
            os.environ["PREOS_STATE_ROOT"] = self.old_state
        self.tmp.cleanup()

    def run_script(self, name, *args, check=True):
        return subprocess.run(
            [os.sys.executable, str(SCRIPTS / name), *map(str, args)],
            cwd=ROOT,
            env=self.env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def recovery_json(self, project="p1", check=True):
        proc = self.run_script("recover-state.py", project, "--repo", self.repo, check=check)
        return proc, json.loads(proc.stdout)

    def checkpoint(self, project="p1", last="unit tests passed", next_action="integration tests", **extra):
        root = MOD.production_root(project)
        (root / "checkpoints").mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": "1.1",
            "checkpoint_id": "CP-1-SOFT",
            "checkpoint_kind": "SOFT",
            "project_id": project,
            "updated_at": MOD.utc_now(),
            "current_stage": "production-implementation",
            "last_verified_action": last,
            "next_unverified_action": next_action,
            "required_approval_ids": [],
            "bindings": {},
            "git": MOD.git_snapshot(self.repo),
        }
        state.update(extra)
        MOD.atomic_write_json(root / "checkpoints" / "CP-1-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        MOD.atomic_write_json(root / "approval-state.json", {"schema_version": "1.1", "project_id": project, "updated_at": MOD.utc_now(), "approvals": []})
        MOD.atomic_write_json(root / "evidence-index.json", {"schema_version": "1.1", "project_id": project, "updated_at": MOD.utc_now(), "evidence": []})
        (root / "implementation-ledger.jsonl").touch(exist_ok=True)
        (root / "recovery-events.jsonl").touch(exist_ok=True)
        return root, state

    def prepare_governed_app(self):
        source = self.repo / "prd.md"
        source.write_text("approved requirement v1\n", encoding="utf-8")
        contract = self.repo / "project-contract.json"
        contract.write_text(json.dumps({
            "project_id": "p1",
            "source_hashes": [{"artifact": "prd.md", "sha256": MOD.sha256_file(source)}],
        }), encoding="utf-8")
        packet = self.repo / "task-packet.md"
        packet.write_text("TP-001 approved bounded scope\n", encoding="utf-8")
        code = self.repo / "app.py"
        code.write_text("print('v1')\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "governed app baseline")
        return source, contract, packet, code

    def cli_checkpoint(self, *, kind="soft", event="SESSION_INTERRUPTED", last="code written", next_action="unit tests", extra=()):
        source, contract, packet, code = self.prepare_governed_app()
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)
        args = [
            "p1", "--repo", self.repo, "--kind", kind, "--event", event,
            "--project-contract", contract, "--project-contract-version", "PC-1",
            "--task-packet", packet, "--task-packet-id", "TP-001",
            "--last-verified-action", last, "--next-unverified-action", next_action,
            *extra,
        ]
        proc = self.run_script("checkpoint-state.py", *args)
        return source, contract, packet, code, proc

    def test_clean_recovery_resumes_first_unverified_action(self):
        self.checkpoint()
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["last_verified_action"], "unit tests passed")
        self.assertEqual(result["next_unverified_action"], "integration tests")

    def test_pending_approval_survives_and_blocks(self):
        root, state = self.checkpoint(required_approval_ids=["A-1"])
        MOD.atomic_write_json(root / "approval-state.json", {
            "schema_version": "1.1", "project_id": "p1", "updated_at": MOD.utc_now(),
            "approvals": [{"approval_id": "A-1", "status": "PENDING", "authority": "ROLE GAP"}],
        })
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["pending_approvals"], ["A-1"])

    def test_missing_required_approval_remains_unapproved(self):
        self.checkpoint(required_approval_ids=["A-MISSING"])
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["missing_approvals"], ["A-MISSING"])

    def test_dirty_tree_mismatch_is_recovery_conflict(self):
        self.checkpoint()
        (self.repo / "README.md").write_text("changed after checkpoint\n", encoding="utf-8")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("WORKING_TREE_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_untracked_file_mismatch_is_recovery_conflict(self):
        self.checkpoint()
        (self.repo / "surprise.tmp").write_text("unexpected", encoding="utf-8")
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

    def test_branch_change_is_recovery_conflict(self):
        self.checkpoint()
        git(self.repo, "checkout", "-b", "other-branch")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("BRANCH_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_source_hash_drift_is_recovery_conflict(self):
        root, state = self.checkpoint()
        source = self.repo / "prd.md"
        source.write_text("v1", encoding="utf-8")
        contract = self.repo / "contract.json"
        contract.write_text(json.dumps({"source_hashes": [{"artifact": "prd.md", "sha256": MOD.sha256_file(source)}]}), encoding="utf-8")
        state["bindings"] = {"project_contract": MOD.file_binding(contract, self.repo)}
        state["git"] = MOD.git_snapshot(self.repo)
        state["updated_at"] = MOD.utc_now()
        state["checkpoint_id"] = "CP-2-SOFT"
        MOD.atomic_write_json(root / "checkpoints" / "CP-2-SOFT.json", state)
        MOD.atomic_write_json(root / "CURRENT-STATE.json", state)
        source.write_text("v2", encoding="utf-8")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("SOURCE_HASH_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_corrupt_any_checkpoint_is_rejected(self):
        root, _ = self.checkpoint()
        (root / "checkpoints" / "CP-Z-BAD.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            MOD.load_latest_state(root)

    def test_current_state_corruption_is_rejected(self):
        root, _ = self.checkpoint()
        (root / "CURRENT-STATE.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            MOD.load_latest_state(root)

    def test_persisted_timestamp_not_mtime_selects_latest_state(self):
        root, first = self.checkpoint(last="first", next_action="second")
        second = dict(first)
        second["checkpoint_id"] = "CP-2-SOFT"
        second["updated_at"] = "2099-01-01T00:00:00.000001Z"
        second["last_verified_action"] = "second"
        p2 = root / "checkpoints" / "CP-2-SOFT.json"
        MOD.atomic_write_json(p2, second)
        # Make the older logical state have a newer filesystem mtime.
        p1 = root / "checkpoints" / "CP-1-SOFT.json"
        future_mtime = time.time() + 10000
        os.utime(p1, (future_mtime, future_mtime))
        data, selected, _ = MOD.load_latest_state(root)
        self.assertEqual(data["checkpoint_id"], "CP-2-SOFT")
        self.assertEqual(selected.name, "CP-2-SOFT.json")

    def test_corrupt_ledger_produces_recovery_conflict(self):
        root, _ = self.checkpoint()
        (root / "implementation-ledger.jsonl").write_text("{bad\n", encoding="utf-8")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("LEDGER_INVALID", {c["type"] for c in result["conflicts"]})

    def test_uncertain_migration_produces_recovery_conflict(self):
        self.checkpoint(pending_migration="20260826-add-payments-table")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("MIGRATION_STATE_UNCERTAIN", {c["type"] for c in result["conflicts"]})

    def test_pending_test_is_rerun_first(self):
        self.checkpoint(next_action="security review", pending_test="integration:test_checkout")
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["next_unverified_action"], "re-run uncertain test: integration:test_checkout")

    def test_explicit_stale_evidence_is_revalidated_first(self):
        root, _ = self.checkpoint(next_action="next packet")
        MOD.atomic_write_json(root / "evidence-index.json", {
            "schema_version": "1.1", "project_id": "p1", "updated_at": MOD.utc_now(),
            "evidence": [{"evidence_id": "E-1", "status": "STALE", "bindings": {}}],
        })
        result = MOD.reconcile_project("p1", self.repo)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["stale_evidence"], ["E-1"])
        self.assertEqual(result["next_unverified_action"], "revalidate stale evidence: E-1")

    def test_atomic_write_leaves_parseable_complete_state(self):
        p = self.base / "atomic.json"
        for n in range(10):
            MOD.atomic_write_json(p, {"n": n, "payload": "x" * 1000})
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["n"], n)
        self.assertEqual(list(self.base.glob("atomic.json.*.tmp")), [])

    def test_granted_role_gap_is_not_human_authority(self):
        self.assertFalse(MOD.authority_is_human("ROLE GAP"))
        self.assertFalse(MOD.authority_is_human("Codex"))
        self.assertTrue(MOD.authority_is_human("Accountable Product Owner"))

    def test_fresh_process_session_loss_resumes_dirty_checkpoint_exactly(self):
        source, contract, packet, code = self.prepare_governed_app()
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)
        code.write_text("print('partial edit captured')\n", encoding="utf-8")
        self.run_script(
            "checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "soft",
            "--event", "SESSION_INTERRUPTED", "--project-contract", contract,
            "--project-contract-version", "PC-1", "--task-packet", packet,
            "--task-packet-id", "TP-001", "--last-verified-action", "file edit captured",
            "--next-unverified-action", "unit tests", "--pending-test", "unit:test_app",
        )
        # recover-state.py runs in a new Python process: no conversational/process memory survives.
        proc, result = self.recovery_json()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(result["status"], "SAFE_TO_RESUME")
        self.assertEqual(result["next_unverified_action"], "re-run uncertain test: unit:test_app")
        self.assertFalse(result["git"]["clean"])

    def test_fresh_process_pending_approval_survives_restart(self):
        source, contract, packet, code = self.prepare_governed_app()
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)
        self.run_script("record-approval.py", "p1", "A-PROD", "--status", "PENDING", "--scope", "production-relevant change")
        self.run_script(
            "checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "soft",
            "--event", "SESSION_INTERRUPTED", "--project-contract", contract,
            "--task-packet", packet, "--task-packet-id", "TP-001",
            "--required-approval", "A-PROD", "--last-verified-action", "review complete",
            "--next-unverified-action", "apply approved change",
        )
        proc, result = self.recovery_json(check=False)
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["pending_approvals"], ["A-PROD"])

    def test_fresh_process_external_edit_after_checkpoint_conflicts(self):
        source, contract, packet, code, _ = self.cli_checkpoint()
        code.write_text("print('external unexplained edit')\n", encoding="utf-8")
        proc, result = self.recovery_json(check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("WORKING_TREE_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_fresh_process_contract_and_task_drift_are_detected(self):
        source, contract, packet, code, _ = self.cli_checkpoint()
        contract.write_text(json.dumps({"project_id": "p1", "source_hashes": []}), encoding="utf-8")
        packet.write_text("TP-001 silently changed scope\n", encoding="utf-8")
        proc, result = self.recovery_json(check=False)
        self.assertEqual(proc.returncode, 2)
        types = {c["type"] for c in result["conflicts"]}
        self.assertIn("PROJECT_CONTRACT_HASH_MISMATCH", types)
        self.assertIn("TASK_PACKET_HASH_MISMATCH", types)

    def test_role_gap_cannot_grant_approval_via_cli(self):
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)
        proc = self.run_script(
            "record-approval.py", "p1", "A-1", "--status", "GRANTED",
            "--scope", "production", "--authority", "ROLE GAP", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("requires a named human", proc.stderr)

    def test_hard_checkpoint_requires_clean_verified_boundary(self):
        source, contract, packet, code = self.prepare_governed_app()
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)
        dirty = self.repo / "dirty.txt"
        dirty.write_text("not committed", encoding="utf-8")
        proc = self.run_script(
            "checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
            "--last-verified-action", "tests passed", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        dirty.unlink()
        proc = self.run_script(
            "checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
            "--event", "IMPLEMENTATION_COMPLETE", "--project-contract", contract,
            "--task-packet", packet, "--task-packet-id", "TP-001",
            "--last-verified-action", "required tests and evidence passed",
            "--next-unverified-action", "independent review",
        )
        self.assertIn("HARD CHECKPOINT", proc.stdout)


if __name__ == "__main__":
    unittest.main()
