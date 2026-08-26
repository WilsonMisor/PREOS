import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


class MasterPlanRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"; self.repo.mkdir()
        git(self.repo, "init"); git(self.repo, "config", "user.email", "preos@example.invalid"); git(self.repo, "config", "user.name", "PREOS")
        (self.repo / "README.md").write_text("baseline\n", encoding="utf-8")
        git(self.repo, "add", "."); git(self.repo, "commit", "-m", "baseline")
        self.env = os.environ.copy(); self.env["PREOS_STATE_ROOT"] = str(self.base / "state")
        self.run_script("init-project-state.py", "p1", "--repo", self.repo)

    def tearDown(self): self.tmp.cleanup()

    def run_script(self, name, *args, check=True, env=None):
        proc = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], cwd=ROOT,
                              env=env or self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check: self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    @property
    def root(self): return Path(self.env["PREOS_STATE_ROOT"]) / "projects/p1/production"

    def recover(self, check=False):
        proc = self.run_script("recover-state.py", "p1", "--repo", self.repo, check=check)
        return proc, json.loads(proc.stdout)

    def governed_files(self, strict_packet=False):
        contract = self.repo / "project-contract.json"
        source = self.repo / "requirements.md"; source.write_text("The app must remain deterministic.\n", encoding="utf-8")
        packet = self.repo / "task-packet.md"
        if strict_packet:
            packet.write_text(
                "# TP-1\n\n## Required checks\n\n- python unit tests must pass\n\n"
                "## Required evidence\n\n- E-TEST must be current\n",
                encoding="utf-8",
            )
        else: packet.write_text("TP-1 bounded scope\n", encoding="utf-8")
        contract.write_text(json.dumps({"project_id": "p1", "source_hashes": []}), encoding="utf-8")
        git(self.repo, "add", "."); git(self.repo, "commit", "-m", "governed files")
        return contract, packet

    def capture_test_evidence(self, contract, packet):
        config = self.repo / "config.json"; config.write_text("{}\n", encoding="utf-8")
        schema = self.repo / "schema.sql"; schema.write_text("create table x(id int);\n", encoding="utf-8")
        deps = self.repo / "requirements.txt"; deps.write_text("\n", encoding="utf-8")
        testdef = self.repo / "test_contract.txt"; testdef.write_text("unit:test\n", encoding="utf-8")
        artifact = self.repo / "test-result.txt"; artifact.write_text("PASS\n", encoding="utf-8")
        git(self.repo, "add", "."); git(self.repo, "commit", "-m", "verified test inputs")
        self.run_script("capture-evidence.py", "p1", "E-TEST", "--repo", self.repo,
                        "--producer", "gstack-qa", "--environment", "test",
                        "--artifact", artifact, "--project-contract", contract, "--task-packet", packet,
                        "--config", config, "--schema", schema, "--dependency", deps,
                        "--test-definition", testdef, "--test-or-command", "unit:test")
        manifest = self.base / "verification.json"
        manifest.write_text(json.dumps({
            "schema_version": "1.0",
            "checks": [{"id": "unit", "status": "PASS", "command_or_test": "unit:test", "evidence_id": "E-TEST"}],
            "evidence_ids": ["E-TEST"], "traceability": "UPDATED", "rollback_point": "git HEAD"
        }), encoding="utf-8")
        return manifest

    def test_pipeline_state_is_reconciled_and_tamper_blocks_recovery(self):
        contract, packet = self.governed_files()
        self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--event", "SESSION_INTERRUPTED",
                        "--project-contract", contract, "--task-packet", packet, "--task-packet-id", "TP-1",
                        "--last-verified-action", "edit captured", "--next-unverified-action", "tests", "--pending-test", "unit")
        pipeline_path = self.root / "PIPELINE-STATE.json"
        pipeline = json.loads(pipeline_path.read_text(encoding="utf-8")); pipeline["current_task_packet"] = "TP-WRONG"
        pipeline_path.write_text(json.dumps(pipeline), encoding="utf-8")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("PIPELINE_TASK_PACKET_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_invalid_state_transition_is_rejected(self):
        proc = self.run_script("checkpoint-state.py", "p1", "--repo", self.repo,
                               "--event", "CHECKPOINT", "--pipeline-state", "RELEASED",
                               "--last-verified-action", "none", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid PREOS state transition", proc.stderr)

    def test_runtime_schema_violation_becomes_recovery_conflict(self):
        current = self.root / "CURRENT-STATE.json"
        data = json.loads(current.read_text(encoding="utf-8")); data["required_approval_ids"] = "not-an-array"
        current.write_text(json.dumps(data), encoding="utf-8")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["status"], "RECOVERY_CONFLICT")
        self.assertIn("RECOVERY_STATE_INVALID", {c["type"] for c in result["conflicts"]})

    def test_unknown_ledger_event_is_integrity_conflict(self):
        ledger = self.root / "implementation-ledger.jsonl"
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event_id": "BAD-1", "timestamp": "2099-01-01T00:00:00Z", "event_type": "MADE_UP_EVENT", "project_id": "p1"}) + "\n")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("LEDGER_INVALID", {c["type"] for c in result["conflicts"]})

    def test_ledger_checkpoint_task_packet_reference_mismatch_is_rejected(self):
        contract, packet = self.governed_files()
        self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--event", "SESSION_INTERRUPTED",
                        "--project-contract", contract, "--task-packet", packet, "--task-packet-id", "TP-1",
                        "--last-verified-action", "captured", "--next-unverified-action", "test")
        ledger = self.root / "implementation-ledger.jsonl"
        rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
        cp_event = next(x for x in rows if x["event_type"] == "SOFT_CHECKPOINT")
        cp_event["event_id"] = "BAD-CP-REF"; cp_event["task_packet_id"] = "TP-WRONG"; cp_event["timestamp"] = "2099-01-01T00:00:00Z"
        with ledger.open("a", encoding="utf-8") as f: f.write(json.dumps(cp_event) + "\n")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("LEDGER_INVALID", {c["type"] for c in result["conflicts"]})

    def test_ledger_tail_pipeline_state_mismatch_is_recovery_conflict(self):
        contract, packet = self.governed_files()
        self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--event", "SESSION_INTERRUPTED",
                        "--project-contract", contract, "--task-packet", packet, "--task-packet-id", "TP-1",
                        "--last-verified-action", "captured", "--next-unverified-action", "test")
        current_path = self.root / "CURRENT-STATE.json"; pipeline_path = self.root / "PIPELINE-STATE.json"
        current = json.loads(current_path.read_text(encoding="utf-8")); pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
        current["pipeline_state"] = "APPROVED_FOR_IMPLEMENTATION"; pipeline["state"] = "APPROVED_FOR_IMPLEMENTATION"
        current_path.write_text(json.dumps(current), encoding="utf-8"); pipeline_path.write_text(json.dumps(pipeline), encoding="utf-8")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("LEDGER_PIPELINE_STATE_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_ledger_tail_checkpoint_mismatch_is_recovery_conflict(self):
        contract, packet = self.governed_files()
        self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--event", "SESSION_INTERRUPTED",
                        "--project-contract", contract, "--task-packet", packet, "--task-packet-id", "TP-1",
                        "--last-verified-action", "captured", "--next-unverified-action", "test")
        current_path = self.root / "CURRENT-STATE.json"; pipeline_path = self.root / "PIPELINE-STATE.json"
        current = json.loads(current_path.read_text(encoding="utf-8")); pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
        current["checkpoint_id"] = "CP-AHEAD"; current["updated_at"] = "2099-01-01T00:00:00Z"
        (self.root / "checkpoints/CP-AHEAD.json").write_text(json.dumps(current), encoding="utf-8")
        current_path.write_text(json.dumps(current), encoding="utf-8")
        pipeline["last_checkpoint_id"] = "CP-AHEAD"; pipeline["updated_at"] = "2099-01-01T00:00:00Z"; pipeline["last_transition"] = "2099-01-01T00:00:00Z"
        pipeline_path.write_text(json.dumps(pipeline), encoding="utf-8")
        proc, result = self.recover()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("LEDGER_CHECKPOINT_MISMATCH", {c["type"] for c in result["conflicts"]})

    def test_hard_checkpoint_refuses_declared_requirements_without_verification_manifest(self):
        contract, packet = self.governed_files(strict_packet=True)
        proc = self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
                               "--event", "IMPLEMENTATION_COMPLETE", "--project-contract", contract,
                               "--task-packet", packet, "--task-packet-id", "TP-1",
                               "--last-verified-action", "claimed complete", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("verification-manifest", proc.stderr)

    def test_relative_task_packet_is_resolved_against_repo_before_hard_verification(self):
        contract, packet = self.governed_files(strict_packet=True)
        proc = self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
                               "--event", "IMPLEMENTATION_COMPLETE", "--project-contract", contract,
                               "--task-packet", packet.name, "--task-packet-id", "TP-1",
                               "--last-verified-action", "claimed complete", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("verification-manifest", proc.stderr)

    def test_hard_checkpoint_accepts_machine_verified_current_evidence(self):
        contract, packet = self.governed_files(strict_packet=True)
        manifest = self.capture_test_evidence(contract, packet)
        proc = self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
                               "--event", "IMPLEMENTATION_COMPLETE", "--project-contract", contract,
                               "--task-packet", packet, "--task-packet-id", "TP-1",
                               "--last-verified-action", "unit test and evidence verified",
                               "--next-unverified-action", "independent review", "--verification-manifest", manifest)
        self.assertIn("HARD CHECKPOINT", proc.stdout)
        state = json.loads((self.root / "CURRENT-STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(state["hard_checkpoint_verification"]["evidence_ids"], ["E-TEST"])

    def test_hard_checkpoint_rejects_indexed_evidence_without_explicit_current_validity(self):
        contract, packet = self.governed_files(strict_packet=True)
        manifest = self.capture_test_evidence(contract, packet)
        index_path = self.root / "evidence-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["evidence"][0]["validity"] = "UNKNOWN"
        index_path.write_text(json.dumps(index), encoding="utf-8")
        proc = self.run_script("checkpoint-state.py", "p1", "--repo", self.repo, "--kind", "hard",
                               "--event", "IMPLEMENTATION_COMPLETE", "--project-contract", contract,
                               "--task-packet", packet, "--task-packet-id", "TP-1",
                               "--last-verified-action", "unit test claimed verified",
                               "--verification-manifest", manifest, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not explicitly CURRENT", proc.stderr)

    def test_all_freshness_binding_categories_invalidate_evidence(self):
        contract, packet = self.governed_files()
        config = self.repo / "config.json"; config.write_text("{}\n", encoding="utf-8")
        schema = self.repo / "schema.sql"; schema.write_text("v1\n", encoding="utf-8")
        deps = self.repo / "requirements.txt"; deps.write_text("dep==1\n", encoding="utf-8")
        testdef = self.repo / "test_contract.txt"; testdef.write_text("v1\n", encoding="utf-8")
        artifact = self.repo / "evidence.txt"; artifact.write_text("PASS\n", encoding="utf-8")
        git(self.repo, "add", "."); git(self.repo, "commit", "-m", "evidence inputs")
        env = self.env.copy(); env["APP_MODE"] = "v1"
        self.run_script("capture-evidence.py", "p1", "E-FRESH", "--repo", self.repo,
                        "--producer", "qa", "--environment", "test", "--artifact", artifact,
                        "--project-contract", contract, "--task-packet", packet,
                        "--source", self.repo / "requirements.md", "--config", config, "--schema", schema,
                        "--dependency", deps, "--test-definition", testdef, "--env-var", "APP_MODE", env=env)
        env2 = self.env.copy(); env2["APP_MODE"] = "v2"
        proc = subprocess.run([sys.executable, str(SCRIPTS / "recover-state.py"), "p1", "--repo", str(self.repo)],
                              cwd=ROOT, env=env2, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = json.loads(proc.stdout)
        self.assertIn("E-FRESH", result["stale_evidence"])
        self.assertEqual(result["next_unverified_action"], "revalidate stale evidence: E-FRESH")


if __name__ == "__main__": unittest.main()
