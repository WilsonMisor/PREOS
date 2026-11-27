#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
from pathlib import Path
import re

from schema_validation import load_schema, validate_instance
from runtime_state import evidence_binding_reasons, git_snapshot, load_json

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BINDINGS = {
    "git_head", "source_hashes", "configuration_files", "schema_files",
    "dependency_files", "test_definition_files", "environment",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PREOS evidence records.")
    parser.add_argument("evidence", nargs="+")
    parser.add_argument("--require-complete-bindings", action="store_true", help="Require the complete production freshness binding vocabulary")
    parser.add_argument("--evaluate-current-state", action="store_true", help="Compare CURRENT evidence bindings against the current repository and environment")
    parser.add_argument("--repo", default=".", help="Repository used for live freshness evaluation")
    args = parser.parse_args()
    errs: list[str] = []
    now = datetime.datetime.now(datetime.timezone.utc)
    schema = load_schema(ROOT / "schemas/evidence-record.schema.json")
    repo = Path(args.repo).resolve()
    actual_git = git_snapshot(repo) if args.evaluate_current_state else None
    for path_text in args.evidence:
        path = Path(path_text)
        try:
            evidence = load_json(path)
            validate_instance(evidence, schema, root_schema=schema, path=str(path))
        except Exception as exc:
            errs.append(f"{path}: schema validation failed: {exc}")
            continue
        if evidence.get("validity") == "GREEN":
            errs.append(f"{path}: validity uses CURRENT/STALE/EXPIRED/UNKNOWN, not GREEN")
        sha = evidence.get("commit_sha")
        if sha and not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
            errs.append(f"{path}: invalid commit_sha")
        if args.require_complete_bindings and evidence.get("validity") == "CURRENT":
            bindings = evidence.get("bindings", {})
            missing = sorted(REQUIRED_BINDINGS - set(bindings))
            if missing:
                errs.append(f"{path}: CURRENT evidence missing freshness bindings: {', '.join(missing)}")
            if not sha:
                errs.append(f"{path}: CURRENT evidence requires commit_sha")
            elif bindings.get("git_head") and bindings.get("git_head") != sha:
                errs.append(f"{path}: commit_sha differs from bindings.git_head")
            env = bindings.get("environment")
            if env is not None and (not isinstance(env, dict) or not isinstance(env.get("variables"), list) or not env.get("sha256")):
                errs.append(f"{path}: environment binding requires variables[] and sha256")
            for key in ("source_hashes", "configuration_files", "schema_files", "dependency_files", "test_definition_files"):
                if key in bindings and not isinstance(bindings[key], list):
                    errs.append(f"{path}: {key} must be an array")
        if args.evaluate_current_state and evidence.get("validity") == "CURRENT" and actual_git is not None:
            try:
                reasons = evidence_binding_reasons(evidence, actual_git, repo)
            except Exception as exc:
                errs.append(f"{path}: current-state comparison failed: {exc}")
            else:
                if reasons:
                    errs.append(f"{path}: CURRENT evidence is stale against live bindings: {', '.join(reasons)}")
        until = evidence.get("valid_until")
        if until:
            try:
                dt = datetime.datetime.fromisoformat(str(until).replace("Z", "+00:00"))
                if dt < now and evidence.get("validity") == "CURRENT":
                    errs.append(f"{path}: expired evidence cannot remain CURRENT")
            except ValueError:
                errs.append(f"{path}: invalid valid_until")
    if errs:
        print("\n".join("FAIL " + error for error in errs))
        raise SystemExit(1)
    suffix = ""
    if args.require_complete_bindings:
        suffix = " with complete freshness bindings"
    if args.evaluate_current_state:
        suffix += " and live binding comparison"
    print(f"PASS evidence: {len(args.evidence)} record(s) structurally valid{suffix}")


if __name__ == "__main__":
    main()
