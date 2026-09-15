#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from preos_common import dump_json, load_json
from runtime_state import evidence_binding_reasons, git_snapshot


def compare_supplied_bindings(evidence: dict, current: dict) -> list[str]:
    reasons: list[str] = []
    old = evidence.get("bindings", {})
    if not isinstance(old, dict):
        raise ValueError("evidence bindings are invalid")
    for key, value in old.items():
        if key in current and current[key] != value:
            reasons.append(f"{key} changed")
    return reasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Invalidate PREOS evidence when bound inputs no longer match.")
    parser.add_argument("evidence")
    parser.add_argument("--current-bindings", help="Optional JSON file of precomputed current bindings")
    parser.add_argument("--repo", default=".", help="Repository used when comparing evidence against live bindings")
    parser.add_argument("--output")
    args = parser.parse_args()
    evidence = load_json(args.evidence)
    if args.current_bindings:
        reasons = compare_supplied_bindings(evidence, load_json(args.current_bindings))
    else:
        repo = Path(args.repo).resolve()
        reasons = evidence_binding_reasons(evidence, git_snapshot(repo), repo)
    until = evidence.get("valid_until")
    if until:
        try:
            if datetime.datetime.fromisoformat(str(until).replace("Z", "+00:00")) < datetime.datetime.now(datetime.timezone.utc):
                reasons.append("validity period expired")
        except ValueError:
            reasons.append("invalid validity period")
    if reasons:
        evidence["validity"] = "STALE"
        evidence["stale_reasons"] = sorted(set(reasons))
    out = args.output or args.evidence
    dump_json(out, evidence)
    print(("STALE: " + ", ".join(evidence["stale_reasons"])) if reasons else "UNCHANGED")


if __name__ == "__main__":
    main()
