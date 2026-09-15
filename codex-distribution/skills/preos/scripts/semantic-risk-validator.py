#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
DEFAULT_DEFINITIONS = MODEL2 / "normalized-risk-definitions.jsonl"
DEFAULT_REVIEWS = MODEL2 / "semantic-review-ledger.jsonl"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalized_body(record: dict[str, Any]) -> str:
    return text(record.get("normalized_definition", record)).lower()


def validate_semantics(definitions_path: Path = DEFAULT_DEFINITIONS, reviews_path: Path = DEFAULT_REVIEWS) -> dict[str, int]:
    definitions: dict[str, dict[str, Any]] = {}
    source_records: set[str] = set()
    for line_no, record in iter_jsonl(definitions_path):
        rid = record.get("risk_definition_id")
        version = record.get("definition_version")
        if not rid or not version:
            raise ValueError(f"{definitions_path}:{line_no}: missing risk_definition_id or definition_version")
        key = f"{rid}@{version}"
        if key in definitions:
            raise ValueError(f"{definitions_path}:{line_no}: duplicate definition {key}")
        definitions[key] = record
        records = record.get("source_records", [])
        if not isinstance(records, list) or not records:
            raise ValueError(f"{definitions_path}:{line_no}: definition has no source_records")
        for source_record in records:
            if source_record in source_records:
                raise ValueError(f"{definitions_path}:{line_no}: duplicate source record binding {source_record}")
            source_records.add(str(source_record))

    reviews = 0
    corrected = 0
    review_sources: set[str] = set()
    sentinel_status: dict[str, str] = {}
    for line_no, record in iter_jsonl(reviews_path):
        reviews += 1
        for field in ("semantic_review_id", "source_record", "risk_definition_id", "definition_version", "semantic_review_status", "change_rationale", "reviewer", "transformation_version", "confidence", "source_location"):
            if field not in record:
                raise ValueError(f"{reviews_path}:{line_no}: missing {field}")
        source_record = str(record["source_record"])
        if source_record in review_sources:
            raise ValueError(f"{reviews_path}:{line_no}: duplicate semantic review for {source_record}")
        review_sources.add(source_record)
        if record["semantic_review_status"] == "CORRECTED":
            corrected += 1
        if source_record in {"4.1.21", "5.6.17"}:
            sentinel_status[source_record] = str(record["semantic_review_status"])
    if review_sources != source_records:
        missing = sorted(source_records - review_sources)[:5]
        extra = sorted(review_sources - source_records)[:5]
        raise ValueError(f"semantic review/source record mismatch missing={missing} extra={extra}")

    by_source: dict[str, dict[str, Any]] = {}
    for record in definitions.values():
        for source_record in record.get("source_records", []):
            by_source[str(source_record)] = record

    sentinel_a = by_source.get("4.1.21")
    if not sentinel_a:
        raise ValueError("Sentinel A source record 4.1.21 missing from normalized definitions")
    body_a = normalized_body(sentinel_a)
    if not all(token in body_a for token in ("serialization", "encoding", "transformation")):
        raise ValueError("Sentinel A normalization must be serialization/encoding/transformation oriented")
    for forbidden in ("concurrent", "shared state", "lost update", "isolation strategy", "competing writes"):
        if forbidden in body_a:
            raise ValueError(f"Sentinel A retains incompatible concurrency language: {forbidden}")
    if sentinel_status.get("4.1.21") != "CORRECTED":
        raise ValueError("Sentinel A semantic review must be CORRECTED")

    sentinel_b = by_source.get("5.6.17")
    if not sentinel_b:
        raise ValueError("Sentinel B source record 5.6.17 missing from normalized definitions")
    body_b = normalized_body(sentinel_b)
    for required in ("pharmaceutical", "identifier", "package", "authenticity", "traceability", "regulatory"):
        if required not in body_b:
            raise ValueError(f"Sentinel B missing pharmaceutical serialization token: {required}")
    for forbidden in ("sensor", "control command", "control loop", "interlock", "fail safe"):
        if forbidden in body_b:
            raise ValueError(f"Sentinel B retains incompatible safety-control language: {forbidden}")
    if sentinel_status.get("5.6.17") != "CORRECTED":
        raise ValueError("Sentinel B semantic review must be CORRECTED")

    # The audit identified concrete conflation sentinels. Keep this check
    # bounded to those documented cases so unrelated domains are not rejected
    # merely because they legitimately mention similar technical vocabulary.
    sentinel_pairs = {
        "4.1.21": ("Serialization Failure", ("concurrent", "shared state", "lost update", "isolation strategy", "competing writes")),
        "5.6.17": ("Drug Serialization Failure", ("sensor", "control command", "control loop", "interlock", "fail safe")),
    }
    for source_id, (name, forbidden_terms) in sentinel_pairs.items():
        record = by_source[source_id]
        if text(record.get("canonical_name")) != name:
            raise ValueError(f"Sentinel {source_id} canonical name drifted")
        body = normalized_body(record)
        for forbidden in forbidden_terms:
            if forbidden in body:
                raise ValueError(f"Sentinel {source_id} retains incompatible semantic contamination: {forbidden}")

    return {"definitions": len(definitions), "reviews": reviews, "corrected": corrected}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PREOS Model 2 semantic normalization and sentinel corrections.")
    parser.add_argument("--definitions", default=str(DEFAULT_DEFINITIONS))
    parser.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    args = parser.parse_args()
    try:
        result = validate_semantics(Path(args.definitions), Path(args.reviews))
    except Exception as exc:
        raise SystemExit(f"FAIL semantic risk validation: {exc}")
    print(
        "PASS semantic risk validation: "
        f"{result['definitions']} normalized definitions, "
        f"{result['reviews']} semantic review records, "
        f"{result['corrected']} correction(s)"
    )


if __name__ == "__main__":
    main()
