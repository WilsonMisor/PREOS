#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re

from runtime_state import append_jsonl, atomic_write_json, git_snapshot, production_root, utc_now


def main() -> None:
    ap = argparse.ArgumentParser(description="Initialize governed PREOS application/runtime state.")
    ap.add_argument("project_id")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    governed = repo / ".ai-product-delivery"
    dirs = [
        "project-contract", "task-packets", "approvals",
        "preos/risk-model", "preos/control-assessments", "preos/architecture-economics",
        "preos/deferred-complexity", "preos/gate-state", "preos/evidence",
        "preos/risk-acceptance", "preos/incidents", "preos/traceability",
    ]
    for directory in dirs:
        (governed / directory).mkdir(parents=True, exist_ok=True)

    root = production_root(args.project_id)
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    now = utc_now()
    git = git_snapshot(repo)

    atomic_write_json(root / "PIPELINE-STATE.json", {
        "schema_version": "1.1",
        "project_id": args.project_id,
        "created_at": now,
        "updated_at": now,
        "state": "INITIALIZED",
        "current_stage": "project-init",
        "blueprint_phase": "project-classification",
        "preos_phase": "project-init",
        "project_contract_version": None,
        "current_task_packet": None,
        "gstack_specialist_stage": None,
        "implementation_status": "NOT_STARTED",
        "release_status": "NOT_AUTHORIZED",
        "last_transition": now,
        "last_checkpoint_id": None,
    })
    atomic_write_json(root / "CURRENT-STATE.json", {
        "schema_version": "1.1",
        "project_id": args.project_id,
        "updated_at": now,
        "current_stage": "project-init",
        "last_verified_action": "project runtime initialized",
        "next_unverified_action": "bind current Project Contract",
        "required_approval_ids": [],
        "bindings": {},
        "git": git,
    })
    atomic_write_json(root / "approval-state.json", {
        "schema_version": "1.1",
        "project_id": args.project_id,
        "updated_at": now,
        "approvals": [],
    })
    atomic_write_json(root / "evidence-index.json", {
        "schema_version": "1.1",
        "project_id": args.project_id,
        "updated_at": now,
        "evidence": [],
    })
    (root / "implementation-ledger.jsonl").touch(exist_ok=True)
    (root / "recovery-events.jsonl").touch(exist_ok=True)
    token = re.sub(r"[^0-9]", "", now)
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"PROJECT-{token}-INITIALIZED",
        "timestamp": now,
        "event_type": "PROJECT_INITIALIZED",
        "project_id": args.project_id,
        "git_branch": git["branch"],
        "git_head": git["head"],
    })
    print(f"INITIALIZED governed={governed} runtime={root}")


if __name__ == "__main__":
    main()
