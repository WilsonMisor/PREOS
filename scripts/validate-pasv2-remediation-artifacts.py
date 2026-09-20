#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT = WORKSPACE / ".migration-control" / "pasv2-remediation"


def count_jsonl(path: Path) -> int:
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += 1
    return total


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit("FAIL PAS v2 remediation artifacts: " + message)

def require_files(root: Path) -> None:
    required = [
        "FINAL-REMEDIATION-REPORT.md",
        "REMEDIATION-REGISTER.md",
        "remediation-register.json",
        "artifact-registry.json",
        "source-2-semantic-unit-ledger.jsonl",
        "source-3-semantic-unit-ledger.jsonl",
        "source-4-corrected-semantic-unit-ledger.jsonl",
        "complete-master-prompt-compliance-register.json",
        "COMPLETE-MASTER-PROMPT-COMPLIANCE-REGISTER.md",
        "original-finding-disposition-matrix.json",
        "ORIGINAL-FINDING-DISPOSITION-MATRIX.md",
        "HUMAN-DECISION-BRIEF.md",
    ]
    missing = []
    for name in required:
        if not (root / name).is_file():
            missing.append(name)
    if missing:
        fail("missing " + ", ".join(missing))

def validate_source_ledgers(root: Path) -> None:
    expected = {}
    expected["source-2-semantic-unit-ledger.jsonl"] = 1148
    expected["source-3-semantic-unit-ledger.jsonl"] = 1612
    expected["source-4-corrected-semantic-unit-ledger.jsonl"] = 1459
    fields = [
        "source_unit_id",
        "source_location",
        "source_hash",
        "concept_classification",
        "implementation_type",
        "smallest_implementing_artifacts",
        "exact_reference",
        "validator_test_evidence",
        "status",
        "rationale",
        "excerpt_sha256",
        "excerpt",
    ]
    for name, count in expected.items():
        path = root / name
        if count_jsonl(path) != count:
            fail(name + " count mismatch")
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            for field in fields:
                if row.get(field) in (None, "", []):
                    fail(name + " line " + str(line_no) + " missing " + field)
            if name.startswith("source-4"):
                artifacts = row.get("smallest_implementing_artifacts")
                if artifacts and len(artifacts) == 3:
                    if "source4-production-assurance-crosswalk.json" in " ".join(artifacts):
                        fail("Source 4 blanket three-artifact mapping remains")

def validate_master_register(root: Path) -> None:
    register = load_json(root / "complete-master-prompt-compliance-register.json")
    expected = register.get("expected_requirement_ids", [])
    registered = register.get("registered_requirement_ids", [])
    if not expected or len(expected) <= 19:
        fail("master prompt register is not complete")
    if expected != registered:
        fail("master prompt register id mismatch")
    if register.get("missing_requirement_ids") not in ([], None):
        fail("master prompt register has missing ids")
    if len(register.get("entries", [])) != len(expected):
        fail("master prompt register entry count mismatch")


def validate_original_findings(root: Path) -> None:
    matrix = load_json(root / "original-finding-disposition-matrix.json")
    entries = matrix.get("entries", [])
    ids = []
    for entry in entries:
        fid = entry.get("first_audit_finding_id")
        ids.append(fid)
        for field in ("final_status", "implementing_artifacts", "validator_tests"):
            if entry.get(field) in (None, "", []):
                fail("finding " + str(fid) + " missing " + field)
    expected = ["AUD-" + str(i).zfill(3) for i in range(1, 64)]
    if ids != expected:
        fail("original finding matrix must preserve AUD-001 through AUD-063")
    if matrix.get("replacement_aud_ids_introduced") not in ([], None):
        fail("replacement AUD IDs introduced")

def validate_artifact_registry(root: Path) -> None:
    registry = load_json(root / "artifact-registry.json")
    artifacts = registry.get("artifacts", [])
    if registry.get("artifact_count") != len(artifacts):
        fail("artifact registry count mismatch")
    required = [
        "repository_workspace",
        "path",
        "purpose",
        "source_requirement_ids",
        "source_documents",
        "format",
        "schema",
        "generated_manual",
        "generator",
        "checksum",
        "validator",
        "test_coverage",
        "canonical_status",
        "related_final_commit",
        "lifecycle_freshness_rule",
    ]
    for idx, item in enumerate(artifacts, 1):
        for field in required:
            if item.get(field) in (None, "", []):
                fail("artifact registry entry " + str(idx) + " missing " + field)
        path = WORKSPACE / item["path"]
        if item.get("canonical_status") == "canonical" and not path.is_file():
            fail("artifact registry missing file " + item["path"])

def validate_suite_lock() -> None:
    path = WORKSPACE / "SUITE-LOCK.json"
    if not path.is_file():
        fail("SUITE-LOCK.json missing")
    lock = load_json(path)
    required = [
        "suite_version",
        "preos_version",
        "preos_commit",
        "blueprint_version",
        "blueprint_commit",
        "gstack_version",
        "gstack_commit",
        "integration_contract_version",
        "risk_catalogue_version",
        "risk_schema_version",
        "readiness_framework_mapping_version",
        "gate_schema_version",
        "virtual_team_contract_version",
        "tested_codex_host_profile",
        "os_runtime_profile",
    ]
    for field in required:
        if lock.get(field) in (None, "", []):
            fail("SUITE-LOCK missing " + field)
    gates = {}
    for gate in lock.get("human_gates", []):
        gates[gate.get("gate_id")] = gate.get("status")
    for gate_id in (
        "PREOS_MODEL2_CROSSWALK_APPROVAL",
        "GSTACK_WINDOWS_BROAD_SUITE_BACKLOG_DISPOSITION",
        "PRODUCTION_RELEASE_AUTHORITY",
    ):
        if gates.get(gate_id) != "OPEN":
            fail("human gate not preserved OPEN: " + gate_id)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remediation-root", default=str(DEFAULT))
    args = parser.parse_args()
    root = Path(args.remediation_root)
    require_files(root)
    validate_source_ledgers(root)
    validate_master_register(root)
    validate_original_findings(root)
    validate_artifact_registry(root)
    validate_suite_lock()
    print("PASS PAS v2 remediation artifacts: rich registers, ledgers, traceability, suite lock, and human gates")


if __name__ == "__main__":
    main()
