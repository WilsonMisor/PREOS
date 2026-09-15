#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
DEFAULT_DEFINITIONS = MODEL2 / "normalized-risk-definitions.jsonl"
DEFAULT_VARIANTS = MODEL2 / "risk-context-variants.jsonl"
DEFAULT_RELATIONSHIPS = MODEL2 / "risk-relationships.jsonl"
DEFAULT_TYPES = MODEL2 / "risk-relationship-types.json"
EXPECTED_VARIANTS = 4337
REQUIRED_TYPES = {
    "SAME_AS",
    "VARIANT_OF",
    "SPECIALIZES",
    "GENERALIZES",
    "OVERLAPS",
    "CAUSED_BY",
    "AMPLIFIES",
    "TRIGGERS",
    "MITIGATED_BY",
    "DEPENDS_ON",
    "SUPERSEDES",
    "RELATED_TO",
}


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def load_endpoint_ids(definitions_path: Path, variants_path: Path) -> dict[str, set[str]]:
    definitions: set[str] = set()
    for _, record in iter_jsonl(definitions_path):
        rid = record.get("risk_definition_id")
        version = record.get("definition_version")
        if not rid or not version:
            raise ValueError("normalized definition missing ID/version")
        definitions.add(str(rid))
        definitions.add(f"{rid}@{version}")

    variants: set[str] = set()
    source_records: set[str] = set()
    for _, record in iter_jsonl(variants_path):
        variant_id = record.get("risk_context_variant_id")
        source_risk_id = record.get("source_risk_id")
        rid = record.get("risk_definition_id")
        version = record.get("definition_version")
        if not variant_id or not source_risk_id or not rid or not version:
            raise ValueError("RiskContextVariant missing variant/source/definition binding")
        if variant_id in variants:
            raise ValueError(f"duplicate RiskContextVariant: {variant_id}")
        if source_risk_id in source_records:
            raise ValueError(f"duplicate source risk variant binding: {source_risk_id}")
        ref = f"{rid}@{version}"
        if ref not in definitions:
            raise ValueError(f"RiskContextVariant references missing definition: {ref}")
        variants.add(str(variant_id))
        source_records.add(str(source_risk_id))
    if len(variants) != EXPECTED_VARIANTS:
        raise ValueError(f"expected {EXPECTED_VARIANTS} RiskContextVariant rows, found {len(variants)}")
    return {"RISK_DEFINITION": definitions, "RISK_CONTEXT_VARIANT": variants}


def validate_relationships(
    definitions_path: Path = DEFAULT_DEFINITIONS,
    variants_path: Path = DEFAULT_VARIANTS,
    relationships_path: Path = DEFAULT_RELATIONSHIPS,
    types_path: Path = DEFAULT_TYPES,
) -> dict[str, int]:
    type_data = json.loads(types_path.read_text(encoding="utf-8"))
    supported = set(type_data.get("relationship_types", []))
    if not REQUIRED_TYPES <= supported:
        raise ValueError(f"relationship vocabulary missing {sorted(REQUIRED_TYPES - supported)}")
    endpoints = load_endpoint_ids(definitions_path, variants_path)

    count = 0
    seen: set[str] = set()
    rel_types: set[str] = set()
    for line_no, rel in iter_jsonl(relationships_path):
        count += 1
        rid = rel.get("relationship_id")
        if not rid:
            raise ValueError(f"{relationships_path}:{line_no}: missing relationship_id")
        if rid in seen:
            raise ValueError(f"duplicate relationship_id: {rid}")
        seen.add(str(rid))
        rel_type = str(rel.get("relationship_type") or "")
        if rel_type not in supported:
            raise ValueError(f"{relationships_path}:{line_no}: unsupported relationship type {rel_type}")
        rel_types.add(rel_type)
        for side in ("source", "target"):
            endpoint = rel.get(side)
            if not isinstance(endpoint, dict):
                raise ValueError(f"{relationships_path}:{line_no}: {side} endpoint missing")
            kind = str(endpoint.get("type") or "")
            value = str(endpoint.get("id") or "")
            if kind not in ("RISK_DEFINITION", "RISK_CONTEXT_VARIANT") or value not in endpoints[kind]:
                raise ValueError(f"{relationships_path}:{line_no}: orphan {side} endpoint {kind}:{value}")
    if count < EXPECTED_VARIANTS:
        raise ValueError("relationship dataset must include at least one relationship per context variant")
    if "VARIANT_OF" not in rel_types:
        raise ValueError("relationship dataset must include VARIANT_OF links")
    return {"relationships": count, "relationship_types_used": len(rel_types), "variants": EXPECTED_VARIANTS}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PREOS Model 2 relationship and context variant artifacts.")
    parser.add_argument("--definitions", default=str(DEFAULT_DEFINITIONS))
    parser.add_argument("--variants", default=str(DEFAULT_VARIANTS))
    parser.add_argument("--relationships", default=str(DEFAULT_RELATIONSHIPS))
    parser.add_argument("--types", default=str(DEFAULT_TYPES))
    args = parser.parse_args()
    try:
        result = validate_relationships(Path(args.definitions), Path(args.variants), Path(args.relationships), Path(args.types))
    except Exception as exc:
        raise SystemExit(f"FAIL risk relationship validation: {exc}")
    print(
        "PASS risk relationship validation: "
        f"{result['variants']} variants, "
        f"{result['relationships']} relationships, "
        f"{result['relationship_types_used']} relationship type(s) used"
    )


if __name__ == "__main__":
    main()
