#!/usr/bin/env python3
from __future__ import annotations

import argparse

from runtime_state import append_jsonl, atomic_write_json, authority_is_human, load_approvals, load_pipeline_state, production_root, utc_now


def main() -> None:
    ap = argparse.ArgumentParser(description="Persist a PREOS human approval decision across AI sessions.")
    ap.add_argument("project_id"); ap.add_argument("approval_id")
    ap.add_argument("--status", choices=["PENDING", "GRANTED", "DENIED"], required=True)
    ap.add_argument("--type", default="CONSEQUENTIAL_DECISION")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--authority", default="ROLE GAP")
    ap.add_argument("--rationale", default="")
    args = ap.parse_args()

    if args.status in {"GRANTED", "DENIED"} and not authority_is_human(args.authority):
        raise SystemExit("Consequential approval or denial requires a named human/accountable authority; AI/Codex/gstack/PREOS/ROLE GAP may not decide it.")

    root = production_root(args.project_id); root.mkdir(parents=True, exist_ok=True)
    state = load_approvals(root, args.project_id)
    approvals = [a for a in state.get("approvals", []) if a.get("approval_id") != args.approval_id]
    now = utc_now()
    record = {
        "approval_id": args.approval_id, "approval_type": args.type, "scope": args.scope,
        "status": args.status, "authority": args.authority, "rationale": args.rationale,
        "updated_at": now,
    }
    approvals.append(record)
    atomic_write_json(root / "approval-state.json", {
        "schema_version": "1.2", "project_id": args.project_id, "updated_at": now, "approvals": approvals,
    })
    pipeline = load_pipeline_state(root, required=False)
    pipeline_state = pipeline.get("state") if pipeline and pipeline.get("schema_version") == "1.2" else None
    event_type = "APPROVAL_REQUIRED" if args.status == "PENDING" else "APPROVAL_RECEIVED"
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"APPROVAL-{args.approval_id}-{now}", "timestamp": now,
        "event_type": event_type, "project_id": args.project_id,
        "approval_id": args.approval_id, "approval_status": args.status,
        "scope": args.scope, "authority": args.authority, "pipeline_state": pipeline_state,
    })
    print(f"APPROVAL {args.approval_id} {args.status}")


if __name__ == "__main__":
    main()
