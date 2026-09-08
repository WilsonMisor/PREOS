#!/usr/bin/env python3
"""Capture evidence with the complete PREOS freshness binding vocabulary."""
from __future__ import annotations

import argparse
from pathlib import Path

from runtime_state import (
    atomic_write_json, environment_binding, file_binding, file_bindings,
    git_snapshot, load_json, production_root, utc_now,
)
from schema_validation import validate_instance, load_schema, validate_file

ROOT = Path(__file__).resolve().parents[1]


def _paths(values: list[str]) -> list[Path]:
    return [Path(v) for v in values]


def main() -> None:
    ap = argparse.ArgumentParser(description="Capture PREOS evidence with deterministic freshness bindings.")
    ap.add_argument("project_id"); ap.add_argument("evidence_id")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--producer", required=True)
    ap.add_argument("--environment", required=True, help="Non-secret environment label")
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--project-contract")
    ap.add_argument("--task-packet")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--schema", action="append", default=[])
    ap.add_argument("--dependency", action="append", default=[])
    ap.add_argument("--test-definition", action="append", default=[])
    ap.add_argument("--env-var", action="append", default=[])
    ap.add_argument("--valid-until")
    ap.add_argument("--test-or-command")
    ap.add_argument("--result", default="PASS")
    ap.add_argument("--requirement-id", action="append", default=[])
    ap.add_argument("--risk-id", action="append", default=[])
    ap.add_argument("--control-id", action="append", default=[])
    args = ap.parse_args()

    repo = Path(args.repo).resolve(); root = production_root(args.project_id)
    artifact = Path(args.artifact)
    if not artifact.is_absolute(): artifact = repo / artifact
    artifact = artifact.resolve()
    if not artifact.is_file(): raise SystemExit(f"evidence artifact does not exist: {artifact}")
    git = git_snapshot(repo)
    bindings = {
        "git_head": git["head"],
        "source_hashes": file_bindings(_paths(args.source), repo),
        "configuration_files": file_bindings(_paths(args.config), repo),
        "schema_files": file_bindings(_paths(args.schema), repo),
        "dependency_files": file_bindings(_paths(args.dependency), repo),
        "test_definition_files": file_bindings(_paths(args.test_definition), repo),
        "environment": environment_binding(args.env_var),
    }
    if args.project_contract: bindings["project_contract"] = file_binding(Path(args.project_contract), repo)
    if args.task_packet: bindings["task_packet"] = file_binding(Path(args.task_packet), repo)
    try: artifact_display = artifact.relative_to(repo).as_posix()
    except ValueError: artifact_display = str(artifact)
    record = {
        "evidence_id": args.evidence_id,
        "requirement_ids": sorted(set(args.requirement_id)),
        "risk_ids": sorted(set(args.risk_id)),
        "control_ids": sorted(set(args.control_id)),
        "produced_at": utc_now(), "producer": args.producer,
        "environment": args.environment, "commit_sha": git["head"],
        "test_or_command": args.test_or_command, "result": args.result,
        "artifact_location": artifact_display, "validity": "CURRENT",
        "valid_until": args.valid_until, "bindings": bindings,
        "invalidation_conditions": [
            "source changes", "Project Contract changes", "Task Packet changes",
            "code/commit changes", "environment changes", "configuration changes",
            "schema changes", "dependency versions change", "test definition changes",
            "validity period expires",
        ],
        "revalidation_trigger": "any bound input changes",
        "required_human_approval": None,
    }
    schema = load_schema(ROOT / "schemas/evidence-record.schema.json")
    validate_instance(record, schema, root_schema=schema, path="evidence")
    evidence_dir = root / "evidence-records"; evidence_dir.mkdir(parents=True, exist_ok=True)
    record_path = evidence_dir / f"{args.evidence_id}.json"
    if record_path.exists(): raise SystemExit(f"evidence_id already exists: {args.evidence_id}")
    atomic_write_json(record_path, record)

    index_path = root / "evidence-index.json"
    if index_path.exists(): index = validate_file(index_path, ROOT / "schemas/evidence-index.schema.json")
    else: index = {"schema_version": "1.2", "project_id": args.project_id, "updated_at": utc_now(), "evidence": []}
    if any(str(e.get("evidence_id")) == args.evidence_id for e in index.get("evidence", [])):
        raise SystemExit(f"evidence_id already indexed: {args.evidence_id}")
    index["schema_version"] = "1.2"; index["updated_at"] = utc_now()
    index.setdefault("evidence", []).append({
        "evidence_id": args.evidence_id, "status": "CURRENT", "validity": "CURRENT",
        "valid_until": args.valid_until, "artifact_location": artifact_display, "bindings": bindings,
    })
    atomic_write_json(index_path, index)
    print(f"EVIDENCE_CAPTURED {args.evidence_id} {record_path}")


if __name__ == "__main__":
    main()
