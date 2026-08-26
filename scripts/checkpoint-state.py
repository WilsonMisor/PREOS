#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re

from runtime_state import atomic_write_json, append_jsonl, file_binding, git_snapshot, production_root, utc_now


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a deterministic PREOS soft or hard checkpoint.")
    ap.add_argument("project_id")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--kind", choices=["soft", "hard"], default="soft")
    ap.add_argument("--event", default="CHECKPOINT")
    ap.add_argument("--stage", default="production-implementation")
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
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    root = production_root(args.project_id)
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    git = git_snapshot(repo)
    if args.kind == "hard":
        if not git["clean"]:
            raise SystemExit("Hard checkpoint refused: working tree is not clean. Verify and commit the coherent unit first; PREOS will not auto-commit or push.")
        if not args.last_verified_action:
            raise SystemExit("Hard checkpoint refused: last verified action is required.")
        if any([args.pending_test, args.pending_build, args.pending_migration, args.pending_evidence]):
            raise SystemExit("Hard checkpoint refused: test/build/migration/evidence state is still pending or uncertain.")

    bindings = {}
    if args.project_contract:
        bindings["project_contract"] = file_binding(Path(args.project_contract), repo)
    if args.task_packet:
        bindings["task_packet"] = file_binding(Path(args.task_packet), repo)

    now = utc_now()
    stamp = re.sub(r"[^0-9]", "", now)
    base_id = f"CP-{stamp}-{args.kind.upper()}"
    checkpoint_id = base_id
    suffix = 1
    while (root / "checkpoints" / f"{checkpoint_id}.json").exists():
        checkpoint_id = f"{base_id}-{suffix:02d}"
        suffix += 1

    state = {
        "schema_version": "1.1",
        "checkpoint_id": checkpoint_id,
        "checkpoint_kind": args.kind.upper(),
        "project_id": args.project_id,
        "updated_at": now,
        "current_stage": args.stage,
        "blueprint_phase": args.blueprint_phase,
        "preos_phase": args.preos_phase,
        "gstack_specialist_stage": args.gstack_specialist_stage,
        "implementation_status": args.implementation_status,
        "release_status": args.release_status,
        "event": args.event,
        "project_contract_version": args.project_contract_version,
        "task_packet_id": args.task_packet_id,
        "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test,
        "pending_build": args.pending_build,
        "pending_migration": args.pending_migration,
        "pending_evidence": args.pending_evidence,
        "required_approval_ids": sorted(set(args.required_approval)),
        "bindings": bindings,
        "git": git,
    }
    checkpoint_path = root / "checkpoints" / f"{checkpoint_id}.json"
    atomic_write_json(checkpoint_path, state)
    atomic_write_json(root / "CURRENT-STATE.json", state)

    pipeline = {
        "schema_version": "1.1",
        "project_id": args.project_id,
        "updated_at": now,
        "state": "IMPLEMENTING" if args.stage == "production-implementation" else args.stage.upper().replace("-", "_"),
        "current_stage": args.stage,
        "blueprint_phase": args.blueprint_phase,
        "preos_phase": args.preos_phase,
        "project_contract_version": args.project_contract_version,
        "current_task_packet": args.task_packet_id,
        "gstack_specialist_stage": args.gstack_specialist_stage,
        "implementation_status": args.implementation_status,
        "release_status": args.release_status,
        "last_transition": now,
        "last_checkpoint_id": checkpoint_id,
    }
    atomic_write_json(root / "PIPELINE-STATE.json", pipeline)

    if args.event != "CHECKPOINT":
        append_jsonl(root / "implementation-ledger.jsonl", {
            "event_id": f"EV-{stamp}-{args.event}",
            "timestamp": now,
            "event_type": args.event,
            "project_id": args.project_id,
            "task_packet_id": args.task_packet_id,
            "checkpoint_id": checkpoint_id,
        })
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"EV-{stamp}-{args.kind.upper()}-CHECKPOINT",
        "timestamp": now,
        "event_type": "HARD_CHECKPOINT" if args.kind == "hard" else "SOFT_CHECKPOINT",
        "project_id": args.project_id,
        "task_packet_id": args.task_packet_id,
        "checkpoint_id": checkpoint_id,
        "git_branch": git["branch"],
        "git_head": git["head"],
        "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test,
        "pending_build": args.pending_build,
        "pending_migration": args.pending_migration,
    })
    print(f"{args.kind.upper()} CHECKPOINT {checkpoint_id} {checkpoint_path}")


if __name__ == "__main__":
    main()
