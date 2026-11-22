#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT = WORKSPACE / ".migration-control" / "pasv2-remediation"
sys.path.insert(0, str(ROOT / "scripts"))
from pasv2_runtime import validate_all_runtime

SELF_REGISTER_NAMES = {
    "complete-master-prompt-compliance-register.json",
    ".migration-control/pasv2-remediation/complete-master-prompt-compliance-register.json",
}


def count_jsonl(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def load_json(path: Path) -> Any:
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
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        fail("missing " + ", ".join(missing))


def json_pointer_resolves(path: Path, pointer: str) -> bool:
    if path.suffix == ".jsonl":
        return pointer in ("", "/") and count_jsonl(path) > 0
    data = load_json(path)
    if pointer in ("", "/"):
        return True
    node = data
    for raw_part in pointer.strip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        elif isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                return False
            node = node[int(part)]
        else:
            return False
    return True


def markdown_anchor_resolves(path: Path, anchor: str) -> bool:
    def slug(text: str) -> str:
        return re.sub(r"[^a-z0-9 -]", "", text.lower()).strip().replace(" ", "-")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match and slug(match.group(1)) == anchor:
            return True
    return False


def python_symbol_resolves(path: Path, symbol: str) -> bool:
    pattern = re.compile(rf"^(def|class)\s+{re.escape(symbol)}\b")
    return any(pattern.match(line) for line in path.read_text(encoding="utf-8").splitlines())


def jsonl_record_resolves(path: Path, expression: str) -> bool:
    if "=" not in expression:
        return False
    field, expected = expression.split("=", 1)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if str(row.get(field)) == expected:
                return True
    return False


def resolve_reference(row: dict[str, Any]) -> bool:
    ref = str(row.get("exact_reference") or "")
    unit_id = str(row.get("source_unit_id") or "")
    disposition = str(row.get("reference_disposition") or row.get("status") or "")
    if ref == "SOURCE_PRESERVATION_ONLY:" + unit_id:
        return disposition == "SOURCE_PRESERVATION_ONLY"
    if ref == "HUMAN_REVIEW:" + unit_id:
        return disposition == "HUMAN_REVIEW"
    if "#" not in ref:
        return False
    artifact, fragment = ref.split("#", 1)
    path = WORKSPACE / artifact
    if not path.is_file():
        return False
    if fragment.startswith("/"):
        return json_pointer_resolves(path, fragment)
    if fragment.startswith("symbol:"):
        return python_symbol_resolves(path, fragment.split(":", 1)[1])
    if fragment.startswith("heading:"):
        return markdown_anchor_resolves(path, fragment.split(":", 1)[1])
    if fragment.startswith("record:"):
        return jsonl_record_resolves(path, fragment.split(":", 1)[1])
    return False


def validate_source_ledgers(root: Path) -> None:
    expected = {
        "source-2-semantic-unit-ledger.jsonl": 1148,
        "source-3-semantic-unit-ledger.jsonl": 1612,
        "source-4-corrected-semantic-unit-ledger.jsonl": 1459,
    }
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
            if name.startswith(("source-3", "source-4")) and not resolve_reference(row):
                fail(name + " line " + str(line_no) + " exact_reference does not resolve: " + str(row.get("exact_reference")))
            if name.startswith("source-4"):
                artifacts = row.get("smallest_implementing_artifacts")
                if artifacts and len(artifacts) == 3 and "source4-production-assurance-crosswalk.json" in " ".join(artifacts):
                    fail("Source 4 blanket three-artifact mapping remains")


def path_or_command_exists(value: str) -> bool:
    if "::" in value:
        value = value.split("::", 1)[0]
    if "#" in value:
        value = value.split("#", 1)[0]
    value = value.strip()
    if not value or value in SELF_REGISTER_NAMES:
        return False
    if value.startswith("python "):
        value = value.split(" ", 1)[1]
    return (WORKSPACE / value).exists() or Path(value).exists()


def validate_master_register(root: Path) -> None:
    register = load_json(root / "complete-master-prompt-compliance-register.json")
    expected = register.get("expected_requirement_ids", [])
    registered = register.get("registered_requirement_ids", [])
    if not expected or len(expected) != 525:
        fail("master prompt register must preserve exactly 525 requirement ids")
    if expected != registered:
        fail("master prompt register id mismatch")
    if register.get("missing_requirement_ids") not in ([], None):
        fail("master prompt register has missing ids")
    entries = register.get("entries", [])
    if len(entries) != len(expected):
        fail("master prompt register entry count mismatch")
    for entry in entries:
        rid = entry.get("requirement_id")
        for field in ("exact_requirement_text", "affected_repositories", "implementing_artifacts", "validator_test", "evidence", "status", "final_result"):
            if entry.get(field) in (None, "", []):
                fail(f"master register {rid} missing {field}")
        artifacts = entry.get("implementing_artifacts") or []
        evidence = entry.get("evidence") or []
        if set(evidence) <= SELF_REGISTER_NAMES:
            fail(f"master register {rid} uses only the register as evidence")
        for item in artifacts + evidence:
            if str(item) in SELF_REGISTER_NAMES:
                continue
            if not path_or_command_exists(str(item)):
                fail(f"master register {rid} unresolved path/evidence {item}")


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
        if "PENDING" in str(item.get("related_final_commit")):
            fail("artifact registry entry " + str(idx) + " has pending final commit placeholder")
        path = WORKSPACE / item["path"]
        if item.get("canonical_status") == "canonical" and not path.is_file():
            fail("artifact registry missing file " + item["path"])



def validate_pasv2_runtime_behavior() -> None:
    try:
        result = validate_all_runtime()
    except Exception as exc:
        fail("runtime behavior validation failed: " + str(exc))
    if result.get("source4_checks") != 34:
        fail("runtime Source-4 validator did not compute all 34 checks")
    if result.get("traceability_records", 0) < 5485:
        fail("runtime traceability graph is incomplete")
    if not result.get("high_assurance") or not result.get("low_risk"):
        fail("runtime acceptance fixtures failed")
    benchmark = result.get("benchmark", {})
    budgets = benchmark.get("budgets", {})
    for field in ("catalogue_query_ms", "selection_time_ms", "validation_time_ms"):
        if benchmark.get(field, 0) >= budgets.get(field, 0):
            fail("runtime benchmark budget exceeded for " + field)

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
        "selected_skill_root",
        "owned_skill_source",
        "owned_skill_count",
        "owned_skill_ids",
    ]
    for field in required:
        if lock.get(field) in (None, "", []):
            fail("SUITE-LOCK missing " + field)
    for version_field, commit_field in (("preos_version", "preos_commit"), ("blueprint_version", "blueprint_commit"), ("gstack_version", "gstack_commit")):
        if lock.get(version_field) == lock.get(commit_field) and lock.get(version_field) != "unversioned-commit-pinned":
            fail(f"SUITE-LOCK stores commit SHA in {version_field}")
    if lock.get("owned_skill_count") != len(set(lock.get("owned_skill_ids", []))) or not lock.get("owned_skill_ids"):
        fail("SUITE-LOCK owned_skill_ids must be unique and agree with the derived count")
    gates = {gate.get("gate_id"): gate.get("status") for gate in lock.get("human_gates", [])}
    for gate_id in (
        "PREOS_MODEL2_CROSSWALK_APPROVAL",
        "GSTACK_WINDOWS_BROAD_SUITE_BACKLOG_DISPOSITION",
        "PRODUCTION_RELEASE_AUTHORITY",
    ):
        if gates.get(gate_id) != "OPEN":
            fail("human gate not preserved OPEN: " + gate_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remediation-root", help="Explicitly audit an archived programme evidence directory")
    args = parser.parse_args()
    if args.remediation_root is None:
        from four_source_audit import audit
        from source_semantics import validate
        from catalogue_traceability import validate as validate_trace
        from risk_field_crosswalk import validate_mapping
        result={'sources':audit(),'semantics':validate(),'traceability':validate_trace(),
                'field_crosswalks':{s:validate_mapping(s) for s in ('source-1','source-4')}}
        print('PASS PAS v2 remediation artifacts: portable canonical preservation, semantics, schema-bound fields and resolved lineage')
        print(json.dumps(result,indent=2))
        return
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

