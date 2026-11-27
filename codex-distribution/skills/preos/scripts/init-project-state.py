#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re

from runtime_state import append_jsonl, atomic_write_json, git_snapshot, production_root, utc_now
from state_machine import validate_state


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
    now = utc_now(); git = git_snapshot(repo); pipeline_state = validate_state("PLANNING")

    pipeline = {
        "schema_version": "1.2", "project_id": args.project_id,
        "created_at": now, "updated_at": now, "state": pipeline_state,
        "current_stage": "project-init", "blueprint_phase": "project-classification",
        "preos_phase": "project-init", "project_contract_version": None,
        "current_task_packet": None, "gstack_specialist_stage": None,
        "implementation_status": "NOT_STARTED", "release_status": "NOT_AUTHORIZED",
        "last_transition": now, "last_checkpoint_id": None,
        "git_branch": git["branch"], "git_head": git["head"],
        "working_tree_fingerprint": git["working_tree_fingerprint"],
        "last_verified_action": "project runtime initialized",
        "next_unverified_action": "bind current Project Contract",
        "pending_test": None, "pending_build": None, "pending_migration": None, "pending_evidence": None,
        "active_risk_ids": [], "active_control_ids": [], "required_approval_ids": [],
    }
    current = {
        "schema_version": "1.2", "project_id": args.project_id, "updated_at": now,
        "current_stage": "project-init", "pipeline_state": pipeline_state,
        "blueprint_phase": "project-classification", "preos_phase": "project-init",
        "gstack_specialist_stage": None, "implementation_status": "NOT_STARTED",
        "release_status": "NOT_AUTHORIZED", "project_contract_version": None,
        "task_packet_id": None, "last_verified_action": "project runtime initialized",
        "next_unverified_action": "bind current Project Contract",
        "pending_test": None, "pending_build": None, "pending_migration": None, "pending_evidence": None,
        "required_approval_ids": [], "active_risk_ids": [], "active_control_ids": [],
        "bindings": {}, "git": git,
    }
    atomic_write_json(root / "PIPELINE-STATE.json", pipeline)
    atomic_write_json(root / "CURRENT-STATE.json", current)
    atomic_write_json(root / "approval-state.json", {
        "schema_version": "1.2", "project_id": args.project_id, "updated_at": now, "approvals": [],
    })
    atomic_write_json(root / "evidence-index.json", {
        "schema_version": "1.2", "project_id": args.project_id, "updated_at": now, "evidence": [],
    })
    (root / "implementation-ledger.jsonl").touch(exist_ok=True)
    (root / "recovery-events.jsonl").touch(exist_ok=True)
    token = re.sub(r"[^0-9]", "", now)
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"PROJECT-{token}-INITIALIZED", "timestamp": now,
        "event_type": "PROJECT_INITIALIZED", "project_id": args.project_id,
        "git_branch": git["branch"], "git_head": git["head"],
        "previous_pipeline_state": "UNINITIALIZED", "pipeline_state": pipeline_state,
    })
    print(f"INITIALIZED governed={governed} runtime={root} pipeline={pipeline_state}")


if __name__ == "__main__":
    main()
