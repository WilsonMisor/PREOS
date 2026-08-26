#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from runtime_state import append_jsonl, atomic_write_json, authority_is_ai, load_approvals, production_root, utc_now


def main() -> None:
    ap = argparse.ArgumentParser(description="Persist a PREOS human approval decision across AI sessions.")
    ap.add_argument("project_id")
    ap.add_argument("approval_id")
    ap.add_argument("--status", choices=["PENDING", "GRANTED", "DENIED"], required=True)
    ap.add_argument("--type", default="CONSEQUENTIAL_DECISION")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--authority", default="ROLE GAP")
    ap.add_argument("--rationale", default="")
    args = ap.parse_args()

    if args.status == "GRANTED" and authority_is_ai(args.authority):
        raise SystemExit("AI/Codex/gstack/PREOS may not grant consequential human approval.")

    root = production_root(args.project_id)
    root.mkdir(parents=True, exist_ok=True)
    state = load_approvals(root, args.project_id)
    approvals = [a for a in state.get("approvals", []) if a.get("approval_id") != args.approval_id]
    now = utc_now()
    record = {
        "approval_id": args.approval_id,
        "approval_type": args.type,
        "scope": args.scope,
        "status": args.status,
        "authority": args.authority,
        "rationale": args.rationale,
        "updated_at": now,
    }
    approvals.append(record)
    state = {"schema_version": "1.0", "project_id": args.project_id, "updated_at": now, "approvals": approvals}
    atomic_write_json(root / "approval-state.json", state)
    append_jsonl(root / "implementation-ledger.jsonl", {
        "event_id": f"APPROVAL-{args.approval_id}-{now}",
        "timestamp": now,
        "event_type": f"APPROVAL_{args.status}",
        "project_id": args.project_id,
        "approval_id": args.approval_id,
        "scope": args.scope,
        "authority": args.authority,
    })
    print(f"APPROVAL {args.approval_id} {args.status}")


if __name__ == "__main__":
    main()
