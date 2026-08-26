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
    ap.add_argument("--project-contract")
    ap.add_argument("--task-packet")
    ap.add_argument("--task-packet-id")
    ap.add_argument("--project-contract-version")
    ap.add_argument("--last-verified-action")
    ap.add_argument("--next-unverified-action")
    ap.add_argument("--pending-test")
    ap.add_argument("--pending-evidence")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    root = production_root(args.project_id)
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    git = git_snapshot(repo)
    if args.kind == "hard" and not git["clean"]:
        raise SystemExit("Hard checkpoint refused: working tree is not clean. Verify and commit the coherent unit first; PREOS will not auto-commit or push.")

    bindings = {}
    if args.project_contract:
        bindings["project_contract"] = file_binding(Path(args.project_contract), repo)
    if args.task_packet:
        bindings["task_packet"] = file_binding(Path(args.task_packet), repo)

    now = utc_now()
    stamp = re.sub(r"[^0-9]", "", now)
    checkpoint_id = f"CP-{stamp}-{args.kind.upper()}"
    state = {
        "schema_version": "1.0",
        "checkpoint_id": checkpoint_id,
        "checkpoint_kind": args.kind.upper(),
        "project_id": args.project_id,
        "updated_at": now,
        "current_stage": args.stage,
        "event": args.event,
        "project_contract_version": args.project_contract_version,
        "task_packet_id": args.task_packet_id,
        "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
        "pending_test": args.pending_test,
        "pending_evidence": args.pending_evidence,
        "bindings": bindings,
        "git": git,
    }
    checkpoint_path = root / "checkpoints" / f"{checkpoint_id}.json"
    atomic_write_json(checkpoint_path, state)
    atomic_write_json(root / "CURRENT-STATE.json", state)

    pipeline_path = root / "PIPELINE-STATE.json"
    pipeline = {
        "schema_version": "1.0",
        "project_id": args.project_id,
        "updated_at": now,
        "state": "IMPLEMENTING" if args.stage == "production-implementation" else args.stage.upper().replace("-", "_"),
        "current_stage": args.stage,
        "task_packet_id": args.task_packet_id,
        "last_checkpoint_id": checkpoint_id,
    }
    atomic_write_json(pipeline_path, pipeline)
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"EV-{stamp}",
        "timestamp": now,
        "event_type": "HARD_CHECKPOINT" if args.kind == "hard" else "SOFT_CHECKPOINT",
        "project_id": args.project_id,
        "task_packet_id": args.task_packet_id,
        "checkpoint_id": checkpoint_id,
        "git_branch": git["branch"],
        "git_head": git["head"],
        "last_verified_action": args.last_verified_action,
        "next_unverified_action": args.next_unverified_action,
    })
    print(f"{args.kind.upper()} CHECKPOINT {checkpoint_id} {checkpoint_path}")


if __name__ == "__main__":
    main()
