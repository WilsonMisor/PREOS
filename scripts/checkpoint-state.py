#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from runtime_state import (
    atomic_write_json, append_jsonl, evidence_binding_reasons, file_binding,
    git_snapshot, load_json, load_pipeline_state, parse_time, production_root,
    sha256_file, stale_evidence, utc_now,
)
from schema_validation import validate_file
from state_machine import target_for_event, validate_state

ROOT = Path(__file__).resolve().parents[1]


def _section_has_requirements(text: str, heading: str) -> bool:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return False
    tail = text[match.end():]
    next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
    body = tail[:next_heading.start()] if next_heading else tail
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.endswith(":"):
            continue
        if ":" in line and not line.split(":", 1)[1].strip():
            continue
        return True
    return False


def _validate_hard_verification(manifest_path: Path | None, task_packet: Path | None, root: Path, repo: Path, git: dict) -> dict | None:
    packet_requires_checks = False; packet_requires_evidence = False
    if task_packet and task_packet.is_file():
        text = task_packet.read_text(encoding="utf-8")
        packet_requires_checks = _section_has_requirements(text, "Required checks")
        packet_requires_evidence = _section_has_requirements(text, "Required evidence")
    if manifest_path is None:
        if packet_requires_checks or packet_requires_evidence:
            raise SystemExit("Hard checkpoint refused: Task Packet declares required checks/evidence but --verification-manifest was not supplied.")
        return None

    manifest = validate_file(manifest_path, ROOT / "schemas/hard-checkpoint-verification.schema.json")
    checks = manifest.get("checks", [])
    if packet_requires_checks and not checks:
        raise SystemExit("Hard checkpoint refused: declared Task Packet checks have no verification records.")
    if any(c.get("status") not in {"PASS", "NOT_APPLICABLE"} for c in checks):
        raise SystemExit("Hard checkpoint refused: verification manifest contains a non-passing check.")
    evidence_ids = sorted({str(x) for x in manifest.get("evidence_ids", [])})
    if packet_requires_evidence and not evidence_ids:
        raise SystemExit("Hard checkpoint refused: declared Task Packet evidence has not been recorded.")

    index_path = root / "evidence-index.json"
    indexed = {}
    if index_path.exists():
        index = validate_file(index_path, ROOT / "schemas/evidence-index.schema.json")
        indexed = {str(e["evidence_id"]): e for e in index.get("evidence", [])}
    missing = [eid for eid in evidence_ids if eid not in indexed]
    if missing:
        raise SystemExit(f"Hard checkpoint refused: verification evidence is not indexed: {', '.join(missing)}")
    stale = stale_evidence(root, git, {}, repo)
    bad = sorted(set(evidence_ids) & set(stale))
    if bad:
        raise SystemExit(f"Hard checkpoint refused: verification evidence is stale: {', '.join(bad)}")
    check_evidence = {str(c.get("evidence_id")) for c in checks if c.get("evidence_id")}
    missing_check_evidence = sorted(check_evidence - set(evidence_ids))
    if missing_check_evidence:
        raise SystemExit(f"Hard checkpoint refused: check evidence IDs missing from manifest evidence_ids: {', '.join(missing_check_evidence)}")
    return {
        "manifest": file_binding(manifest_path, repo),
        "checks_verified": len(checks),
        "evidence_ids": evidence_ids,
        "traceability": manifest["traceability"],
        "rollback_point": manifest["rollback_point"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a deterministic PREOS soft or hard checkpoint.")
    ap.add_argument("project_id")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--kind", choices=["soft", "hard"], default="soft")
    ap.add_argument("--event", default="CHECKPOINT")
    ap.add_argument("--stage", default="production-implementation")
    ap.add_argument("--pipeline-state", choices=sorted(__import__("state_machine").STATE_SET))
    ap.add_argument("--blueprint-phase", default="implementation")
    ap.add_argument("--preos-phase", default="production-implement")
    ap.add_argument("--gstack-specialist-stage")
    ap.add_argument("--implementation-status", default="IMPLEMENTING")
    ap.add_argument("--release-status", default="NOT_AUTHORIZED")
    ap.add_argument("--project-contract")
    ap.add_argument("--task-packet")
    ap.add_argument("--task-packet-id")
    ap.add_argument("--project-contract-version")
    ap.add_argument("--last-verified-action")
    ap.add_argument("--next-unverified-action")
    ap.add_argument("--pending-test")
    ap.add_argument("--pending-build")
    ap.add_argument("--pending-migration")
    ap.add_argument("--pending-evidence")
    ap.add_argument("--required-approval", action="append", default=[])
    ap.add_argument("--active-risk-id", action="append", default=[])
    ap.add_argument("--active-control-id", action="append", default=[])
    ap.add_argument("--verification-manifest")
    args = ap.parse_args()

    repo = Path(args.repo).resolve(); root = production_root(args.project_id)
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    git = git_snapshot(repo)
    pipeline = load_pipeline_state(root, required=True)
    if str(pipeline.get("schema_version")) != "1.2":
        raise SystemExit("Checkpoint refused: legacy pipeline state must be reconciled/upgraded before new checkpoints are written.")
    previous_pipeline = validate_state(str(pipeline["state"]))
    explicit = args.pipeline_state
    if args.event == "SESSION_INTERRUPTED" and explicit is None and args.task_packet_id and previous_pipeline in {"PLANNING", "APPROVED_FOR_IMPLEMENTATION"}:
        explicit = "IMPLEMENTING"
    target_pipeline = target_for_event(args.event, previous_pipeline, explicit)

    hard_verification = None
    task_packet_path = Path(args.task_packet).resolve() if args.task_packet else None
    if args.kind == "hard":
        if not git["clean"]:
            raise SystemExit("Hard checkpoint refused: working tree is not clean. Verify and commit the coherent unit first; PREOS will not auto-commit or push.")
        if not args.last_verified_action:
            raise SystemExit("Hard checkpoint refused: last verified action is required.")
        if any([args.pending_test, args.pending_build, args.pending_migration, args.pending_evidence]):
            raise SystemExit("Hard checkpoint refused: test/build/migration/evidence state is still pending or uncertain.")
        manifest_path = Path(args.verification_manifest).resolve() if args.verification_manifest else None
        hard_verification = _validate_hard_verification(manifest_path, task_packet_path, root, repo, git)

    bindings = {}
    if args.project_contract: bindings["project_contract"] = file_binding(Path(args.project_contract), repo)
    if args.task_packet: bindings["task_packet"] = file_binding(Path(args.task_packet), repo)

    now = utc_now(); stamp = re.sub(r"[^0-9]", "", now)
    base_id = f"CP-{stamp}-{args.kind.upper()}"; checkpoint_id = base_id; suffix = 1
    while (root / "checkpoints" / f"{checkpoint_id}.json").exists():
        checkpoint_id = f"{base_id}-{suffix:02d}"; suffix += 1

    state = {
        "schema_version": "1.2", "checkpoint_id": checkpoint_id,
        "checkpoint_kind": args.kind.upper(), "project_id": args.project_id,
        "updated_at": now, "current_stage": args.stage, "pipeline_state": target_pipeline,
        "blueprint_phase": args.blueprint_phase, "preos_phase": args.preos_phase,
        "gstack_specialist_stage": args.gstack_specialist_stage,
        "implementation_status": args.implementation_status, "release_status": args.release_status,
        "event": args.event, "project_contract_version": args.project_contract_version,
        "task_packet_id": args.task_packet_id, "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test, "pending_build": args.pending_build,
        "pending_migration": args.pending_migration, "pending_evidence": args.pending_evidence,
        "required_approval_ids": sorted(set(args.required_approval)),
        "active_risk_ids": sorted(set(args.active_risk_id)),
        "active_control_ids": sorted(set(args.active_control_id)),
        "bindings": bindings, "git": git,
        "hard_checkpoint_verification": hard_verification,
    }
    checkpoint_path = root / "checkpoints" / f"{checkpoint_id}.json"
    atomic_write_json(checkpoint_path, state); atomic_write_json(root / "CURRENT-STATE.json", state)

    pipeline_out = {
        "schema_version": "1.2", "project_id": args.project_id,
        "created_at": pipeline.get("created_at"), "updated_at": now,
        "state": target_pipeline, "current_stage": args.stage,
        "blueprint_phase": args.blueprint_phase, "preos_phase": args.preos_phase,
        "project_contract_version": args.project_contract_version,
        "current_task_packet": args.task_packet_id,
        "gstack_specialist_stage": args.gstack_specialist_stage,
        "implementation_status": args.implementation_status, "release_status": args.release_status,
        "last_transition": now, "last_checkpoint_id": checkpoint_id,
        "git_branch": git["branch"], "git_head": git["head"],
        "working_tree_fingerprint": git["working_tree_fingerprint"],
        "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test, "pending_build": args.pending_build,
        "pending_migration": args.pending_migration, "pending_evidence": args.pending_evidence,
        "active_risk_ids": sorted(set(args.active_risk_id)),
        "active_control_ids": sorted(set(args.active_control_id)),
        "required_approval_ids": sorted(set(args.required_approval)),
    }
    atomic_write_json(root / "PIPELINE-STATE.json", pipeline_out)

    if args.event != "CHECKPOINT":
        append_jsonl(root / "implementation-ledger.jsonl", {
            "event_id": f"EV-{stamp}-{args.event}", "timestamp": now,
            "event_type": args.event, "project_id": args.project_id,
            "task_packet_id": args.task_packet_id, "checkpoint_id": checkpoint_id,
            "previous_pipeline_state": previous_pipeline, "pipeline_state": target_pipeline,
        })
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"EV-{stamp}-{args.kind.upper()}-CHECKPOINT", "timestamp": now,
        "event_type": "HARD_CHECKPOINT" if args.kind == "hard" else "SOFT_CHECKPOINT",
        "project_id": args.project_id, "task_packet_id": args.task_packet_id,
        "checkpoint_id": checkpoint_id, "git_branch": git["branch"], "git_head": git["head"],
        "last_verified_action": args.last_verified_action, "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test, "pending_build": args.pending_build,
        "pending_migration": args.pending_migration, "previous_pipeline_state": target_pipeline,
        "pipeline_state": target_pipeline,
    })
    print(f"{args.kind.upper()} CHECKPOINT {checkpoint_id} {checkpoint_path} pipeline={target_pipeline}")


if __name__ == "__main__":
    main()
