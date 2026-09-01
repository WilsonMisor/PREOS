#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from preos_common import iter_risks
from schema_validation import SchemaValidationError, load_schema, validate_instance

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = ROOT / "references" / "risks" / "migration"
MODEL2_DIR = ROOT / "references" / "risks" / "model2"
EXPECTED_MODEL2_COUNT = 4337
EXPECTED_DIMENSIONS = {"universal": 1406, "industry": 1450, "product": 753, "jurisdiction": 328, "architecture": 400}
EXPECTED_FIELD_COUNT = 40
CROSSWALK_SCHEMA = MIGRATION_DIR / "legacy-to-model2-crosswalk.schema.json"
CROSSWALK = MIGRATION_DIR / "legacy-to-model2-crosswalk.json"

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(message)


def legacy_ids() -> list[str]:
    return [risk["check_id"] for risk in iter_risks(ROOT)]


def validate_record_schema() -> None:
    path = MODEL2_DIR / "risk-record.schema.json"
    if not path.is_file():
        fail("missing model2 risk-record.schema.json")
    schema = load_json(path)
    required = schema.get("required", [])
    for key in ["risk_id", "canonical_name", "dimension", "category", "field_count", "fields"]:
        if key not in required:
            fail(f"model2 risk-record schema missing required key: {key}")
    dimensions = schema.get("properties", {}).get("dimension", {}).get("enum", [])
    if sorted(dimensions) != sorted(EXPECTED_DIMENSIONS):
        fail(f"model2 dimension enum mismatch: {dimensions}")
    field_count = schema.get("properties", {}).get("field_count", {})
    if field_count.get("const") != EXPECTED_FIELD_COUNT:
        fail("model2 field_count schema must require exactly 40")

def validate_crosswalk() -> dict[str, int]:
    if not CROSSWALK_SCHEMA.is_file():
        fail("missing legacy-to-model2 crosswalk schema")
    if not CROSSWALK.is_file():
        fail("missing legacy-to-model2 crosswalk")
    schema = load_schema(CROSSWALK_SCHEMA)
    rows = load_json(CROSSWALK)
    if not isinstance(rows, list):
        fail("legacy-to-model2 crosswalk must be a JSON array")
    expected_ids = legacy_ids()
    if len(rows) != len(expected_ids):
        fail(f"legacy-to-model2 crosswalk count mismatch: {len(rows)} != {len(expected_ids)}")
    seen = [row.get("v1_risk_id") for row in rows if isinstance(row, dict)]
    duplicates = sorted(risk_id for risk_id, count in Counter(seen).items() if count > 1)
    if duplicates:
        fail(f"legacy-to-model2 crosswalk duplicate legacy IDs: {duplicates[:5]}")
    if set(seen) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(seen))[:5]
        extra = sorted(set(seen) - set(expected_ids))[:5]
        fail(f"legacy-to-model2 crosswalk ID coverage mismatch missing={missing} extra={extra}")
    unresolved = 0
    human_review = 0
    linked = 0

    for index, row in enumerate(rows):
        try:
            validate_instance(row, schema, root_schema=schema, path=f"crosswalk[{index}]")
        except SchemaValidationError as exc:
            fail(str(exc))
        if row["review_status"] == "HUMAN_REVIEW_REQUIRED":
            human_review += 1
        if row["disposition"] == "UNRESOLVED":
            unresolved += 1
            if row["v2_risk_ids"]:
                fail("unresolved crosswalk rows must not bind model2 risk IDs")
            if row["review_status"] != "HUMAN_REVIEW_REQUIRED":
                fail("unresolved crosswalk rows require human review status")
        else:
            if not row["v2_risk_ids"]:
                fail("resolved crosswalk rows must bind at least one model2 risk ID")
            linked += len(row["v2_risk_ids"])
    return {"total": len(rows), "unresolved": unresolved, "human_review": human_review, "linked": linked}


def validate_optional_catalogue() -> dict[str, int | bool]:
    path = MODEL2_DIR / "risk-corpus.jsonl"
    if not path.exists():
        return {"installed": False}
    schema = load_schema(MODEL2_DIR / "risk-record.schema.json")
    seen: set[str] = set()
    dimensions: Counter[str] = Counter()
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            validate_instance(record, schema, root_schema=schema, path=f"risk[{line_number}]")
            risk_id = record.get("risk_id")
            if risk_id in seen:
                fail(f"duplicate model2 risk_id: {risk_id}")
            seen.add(risk_id)
            fields = record.get("fields")
            if record.get("field_count") != EXPECTED_FIELD_COUNT:
                fail(f"model2 record field_count mismatch at line {line_number}")
            if not isinstance(fields, dict) or len(fields) != EXPECTED_FIELD_COUNT:
                fail(f"model2 fields object must contain 40 fields at line {line_number}")
            dimension = record.get("dimension")
            if dimension not in EXPECTED_DIMENSIONS:
                fail(f"unexpected model2 dimension {dimension!r} at line {line_number}")
            dimensions[dimension] += 1
            total += 1

    if total != EXPECTED_MODEL2_COUNT:
        fail(f"model2 risk count mismatch: {total} != {EXPECTED_MODEL2_COUNT}")
    if dict(dimensions) != EXPECTED_DIMENSIONS:
        fail(f"model2 dimension counts mismatch: {dict(dimensions)}")
    index_path = MODEL2_DIR / "catalogue-index.json"
    if index_path.exists():
        index = load_json(index_path)
        if index.get("count") != EXPECTED_MODEL2_COUNT:
            fail("model2 catalogue index count mismatch")
        if index.get("field_count_expected") != EXPECTED_FIELD_COUNT:
            fail("model2 catalogue index field count mismatch")
        if index.get("dimensions") != EXPECTED_DIMENSIONS:
            fail("model2 catalogue index dimension mismatch")
    return {"installed": True, "total": total}


def validate_project_contract_schema() -> None:
    schema = load_json(ROOT / "schemas" / "project-contract.schema.json")
    if "risk_corpus" not in schema.get("required", []):
        fail("project contract schema must require risk_corpus declaration")
    prop = schema.get("properties", {}).get("risk_corpus", {})
    if prop.get("type") != "object":
        fail("project contract risk_corpus must be an object")
    enum = prop.get("properties", {}).get("version", {}).get("enum", [])
    if enum != ["legacy-v1", "model2"]:
        fail(f"project contract risk_corpus version enum mismatch: {enum}")
    template = load_json(ROOT / "templates" / "project-contract.json")
    if template.get("risk_corpus", {}).get("version") != "legacy-v1":
        fail("project contract template must default to legacy-v1")


def main() -> None:
    validate_record_schema()
    crosswalk = validate_crosswalk()
    catalogue = validate_optional_catalogue()
    validate_project_contract_schema()
    print(f"PASS PREOS risk model2 migration: {crosswalk['total']} legacy risks have explicit dispositions")
    if catalogue.get("installed"):
        print(f"PASS PREOS risk model2 catalogue: {catalogue['total']} records validated")
    else:
        print("PASS PREOS risk model2 catalogue: not installed before crosswalk gate")
    if crosswalk["unresolved"]:
        print(f"PASS PREOS risk model2 activation gate: disabled with {crosswalk['unresolved']} unresolved human-review rows")
    else:
        print("PASS PREOS risk model2 activation gate: crosswalk complete; human approval still required")


if __name__ == "__main__":
    main()
