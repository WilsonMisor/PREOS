#!/usr/bin/env python3
"""Reconcile PREOS runtime state with actual project/Git/evidence/approval truth."""

from pathlib import Path
import argparse
import json

from runtime_state import reconcile_project


def main() -> None:
    ap = argparse.ArgumentParser(description="Recover interrupted PREOS production implementation safely.")
    ap.add_argument("project_id")
    ap.add_argument("--repo", default=".", help="Application repository root")
    args = ap.parse_args()
    try:
        result = reconcile_project(args.project_id, Path(args.repo))
    except Exception as exc:
        result = {
            "status": "RECOVERY_CONFLICT",
            "project_id": args.project_id,
            "conflicts": [{"type": "RECOVERY_STATE_INVALID", "detail": str(exc)}],
            "next_unverified_action": None,
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "RECOVERY_CONFLICT":
        raise SystemExit(2)
    if result["status"] == "BLOCKED":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
