#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import hashlib
from pathlib import Path

from preos_common import dump_json, load_json
from runtime_state import evidence_binding_reasons, git_snapshot, atomic_write_json


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
    out = Path(args.output or args.evidence).resolve()
    source = Path(args.evidence).resolve()
    if out != source and out.exists():
        raise ValueError('replacement output already exists; evidence history must be retained')
    if reasons:
        previous = source.read_bytes()
        digest = hashlib.sha256(previous).hexdigest()
        history = source.parent / '.evidence-history' / (digest + '.json')
        history.parent.mkdir(exist_ok=True)
        if history.exists() and history.read_bytes() != previous:
            raise ValueError('evidence history hash conflict')
        if not history.exists(): history.write_bytes(previous)
        evidence["validity"] = "STALE"
        evidence["stale_reasons"] = sorted(set(reasons))
        evidence['previous_version'] = {'path': str(history), 'sha256': digest}
        evidence['invalidated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if reasons or out != source: atomic_write_json(out, evidence)
    print(("STALE: " + ", ".join(evidence["stale_reasons"])) if reasons else "UNCHANGED")


if __name__ == "__main__":
    main()
