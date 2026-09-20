#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from collections import Counter
import json
import re

from preos_common import open_source_zip

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "references" / "readiness"
EXPECTED_QUESTION_COUNT = 1300
EXPECTED_SOURCE2_UNITS = 1148
EXPECTED_CLASSES = {
    "framework_statement",
    "positive_keypoint",
    "negative_keypoint",
    "best_practice",
    "danger_item",
    "caution_item",
    "decision_gate",
    "required_evidence_item",
    "ownership_requirement",
    "applicability_rule",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail(message: str) -> None:
    print("FAIL readiness: " + message)
    raise SystemExit(1)


def validate_question_source() -> int:
    with open_source_zip() as zf:
        text = zf.read("master_production_readiness_questions.md").decode("utf-8")
    count = len(re.findall(r"^\d+\.\s+", text, re.M))
    if count != EXPECTED_QUESTION_COUNT:
        fail(f"expected {EXPECTED_QUESTION_COUNT} numbered questions, found {count}")
    return count


def validate_source2_units() -> dict[str, int]:
    path = READINESS / "source2-readiness-units.jsonl"
    if not path.is_file():
        fail("missing source2-readiness-units.jsonl")
    rows = load_jsonl(path)
    if len(rows) != EXPECTED_SOURCE2_UNITS:
        fail(f"expected {EXPECTED_SOURCE2_UNITS} Source 2 semantic units, found {len(rows)}")
    registry = load_json(READINESS / "domain-registry.json")
    domains = {item["id"] for item in registry.get("domains", [])}
    production = load_json(ROOT / "references" / "gates" / "production-gates.json")
    gates = {gate["id"] for gate in production.get("gates", [])}
    observed_domains: set[str] = set()
    classes: Counter[str] = Counter()
    seen: set[str] = set()
    for idx, row in enumerate(rows, 1):
        unit_id = row.get("source_unit_id")
        if not unit_id or unit_id in seen:
            fail(f"row {idx} has missing/duplicate source_unit_id")
        seen.add(unit_id)
        for field in (
            "source_location",
            "excerpt_sha256",
            "excerpt",
            "classification",
            "readiness_domain_id",
            "target_artifacts",
            "blueprint_lifecycle_stage",
            "blueprint_profile",
            "blueprint_artifact",
            "preos_gates",
            "preos_risk_ids",
            "preos_control_ids",
            "evidence_requirements",
            "gstack_specialist_route",
            "human_approval_boundary",
            "implementation_status",
            "validator",
        ):
            if row.get(field) in (None, "", []):
                if row.get("mapping_status") == "HUMAN_REVIEW_REQUIRED" and field in {"preos_gates", "preos_control_ids"}:
                    pass
                else:
                    fail(f"{unit_id} missing {field}")
        if row["classification"] not in EXPECTED_CLASSES:
            fail(f"{unit_id} has unsupported classification {row['classification']}")
        classes[row["classification"]] += 1
        observed_domains.add(row["readiness_domain_id"])
        if not set(row["preos_gates"]) <= gates:
            fail(f"{unit_id} maps to unknown PREOS gate")
        combined_ids = list(row["preos_control_ids"]) + list(row["preos_risk_ids"])
        if not all(re.fullmatch(r"FS-\d{3}|model2-contextual-risk-selection", item) for item in combined_ids):
            fail(f"{unit_id} has malformed risk/control mapping")
        if row["human_approval_boundary"] not in {"required", "not_required_by_unit"}:
            fail(f"{unit_id} has unsupported human approval boundary")
        if row["implementation_status"] not in {"IMPLEMENTED_BY_REMEDIATION", "DETERMINISTIC_SEMANTIC_MAPPING", "HUMAN_REVIEW_REQUIRED"}:
            fail(f"{unit_id} has unexpected implementation status")
    if not domains <= observed_domains:
        fail("Source 2 readiness ledger does not cover all 36 RD domains")
    if not EXPECTED_CLASSES <= set(classes):
        fail("Source 2 readiness ledger is missing one or more required classifications")
    return {"units": len(rows), "domains": len(observed_domains), "classifications": len(classes)}


def main() -> None:
    questions = validate_question_source()
    result = validate_source2_units()
    print(f"PASS readiness: {questions} production-readiness questions present in checksum-verified authoritative source package")
    print(f"PASS Source 2 readiness ledger: {result['units']} semantic units, {result['domains']} domain buckets, {result['classifications']} classifications")


if __name__ == "__main__":
    main()
