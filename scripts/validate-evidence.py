#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
from pathlib import Path
import re
import sys

from schema_validation import load_schema, validate_instance
from runtime_state import load_json

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BINDINGS = {
    "git_head", "source_hashes", "configuration_files", "schema_files",
    "dependency_files", "test_definition_files", "environment",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate PREOS evidence records and freshness-binding completeness.")
    ap.add_argument("evidence", nargs="+")
    args = ap.parse_args(); errs = []; now = datetime.datetime.now(datetime.timezone.utc)
    schema = load_schema(ROOT / "schemas/evidence-record.schema.json")
    for path_text in args.evidence:
        path = Path(path_text)
        try:
            e = load_json(path)
            validate_instance(e, schema, root_schema=schema, path=str(path))
        except Exception as exc:
            errs.append(f"{path}: schema validation failed: {exc}"); continue
        if e.get("validity") == "GREEN": errs.append(f"{path}: validity uses CURRENT/STALE/EXPIRED/UNKNOWN, not GREEN")
        sha = e.get("commit_sha")
        if sha and not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha): errs.append(f"{path}: invalid commit_sha")
        if e.get("validity") == "CURRENT":
            bindings = e.get("bindings", {})
            missing = sorted(REQUIRED_BINDINGS - set(bindings))
            if missing: errs.append(f"{path}: CURRENT evidence missing freshness bindings: {', '.join(missing)}")
            if not sha: errs.append(f"{path}: CURRENT evidence requires commit_sha")
            elif bindings.get("git_head") and bindings.get("git_head") != sha:
                errs.append(f"{path}: commit_sha differs from bindings.git_head")
            env = bindings.get("environment")
            if env is not None and (not isinstance(env, dict) or not isinstance(env.get("variables"), list) or not env.get("sha256")):
                errs.append(f"{path}: environment binding requires variables[] and sha256")
            for key in ("source_hashes", "configuration_files", "schema_files", "dependency_files", "test_definition_files"):
                if key in bindings and not isinstance(bindings[key], list): errs.append(f"{path}: {key} must be an array")
        until = e.get("valid_until")
        if until:
            try:
                dt = datetime.datetime.fromisoformat(str(until).replace("Z", "+00:00"))
                if dt < now and e.get("validity") == "CURRENT": errs.append(f"{path}: expired evidence cannot remain CURRENT")
            except ValueError: errs.append(f"{path}: invalid valid_until")
    if errs:
        print("\n".join("FAIL " + e for e in errs)); raise SystemExit(1)
    print(f"PASS evidence: {len(args.evidence)} record(s) schema-valid with complete freshness bindings")


if __name__ == "__main__":
    main()
