#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
DEFAULT_CORPUS = MODEL2 / "risk-corpus.jsonl"
DEFAULT_VARIANTS = MODEL2 / "risk-context-variants.jsonl"
DEFAULT_DEFINITIONS = MODEL2 / "normalized-risk-definitions.jsonl"
DEFAULT_RELATIONSHIPS = MODEL2 / "risk-relationships.jsonl"
MAX_LIMIT = 500
REL_TYPES = [
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
]


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_owner(record: dict[str, Any]) -> str:
    fields = record.get("fields", {})
    if not isinstance(fields, dict):
        return ""
    return text(fields.get("39") or fields.get("Field 39") or fields.get("Owner"))


def contains(value: Any, needle: str | None) -> bool:
    if not needle:
        return True
    return needle.lower() in text(value).lower()


def endpoint_keys(variant: dict[str, Any]) -> list[tuple[str, str]]:
    if not variant:
        return []
    rid = str(variant.get("risk_definition_id") or "")
    version = str(variant.get("definition_version") or "")
    keys = [("RISK_CONTEXT_VARIANT", str(variant.get("risk_context_variant_id") or ""))]
    if rid:
        keys.append(("RISK_DEFINITION", rid))
    if rid and version:
        keys.append(("RISK_DEFINITION", f"{rid}@{version}"))
    return keys


def make_indexes(args: argparse.Namespace) -> dict[str, Any]:
    variants = load_jsonl(Path(args.variants))
    definitions = load_jsonl(Path(args.definitions))
    relationships = load_jsonl(Path(args.relationships))
    variants_by_source = {str(v.get("source_risk_id")): v for v in variants}
    definitions_by_ref: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        rid = str(definition.get("risk_definition_id") or "")
        version = str(definition.get("definition_version") or "")
        if rid:
            definitions_by_ref[rid] = definition
        if rid and version:
            definitions_by_ref[f"{rid}@{version}"] = definition
    rel_by_endpoint: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rel in relationships:
        for side in ("source", "target"):
            endpoint = rel.get(side)
            if isinstance(endpoint, dict):
                rel_by_endpoint[(str(endpoint.get("type") or ""), str(endpoint.get("id") or ""))].append(rel)
    return {"variants_by_source": variants_by_source, "definitions_by_ref": definitions_by_ref, "rel_by_endpoint": rel_by_endpoint}


def variant_matches(variant: dict[str, Any], args: argparse.Namespace, rel_by_endpoint: dict[tuple[str, str], list[dict[str, Any]]]) -> bool:
    if args.source_variant_id and variant.get("risk_context_variant_id") != args.source_variant_id:
        return False
    if args.definition_id:
        ref = f"{variant.get('risk_definition_id')}@{variant.get('definition_version')}"
        if args.definition_id not in {variant.get("risk_definition_id"), ref}:
            return False
    context = variant.get("context", {}) if isinstance(variant.get("context"), dict) else {}
    filter_pairs = [
        ("industry", args.industry),
        ("product", args.product),
        ("jurisdiction", args.jurisdiction),
        ("architecture", args.architecture),
        ("feature", args.feature),
        ("actor", args.actor),
        ("maturity_stage", args.maturity_stage),
        ("threat_stage", args.threat_stage),
        ("money_movement", args.money_movement),
        ("data_sensitivity", args.data_sensitivity),
        ("tenant_model", args.tenant_model),
        ("control", args.control),
        ("gate", args.gate),
    ]
    for key, needle in filter_pairs:
        if needle and not contains(context.get(key), needle):
            return False
    for needle in (args.changed_component, args.task_packet_keyword):
        if needle and not contains({"variant": variant, "context": context}, needle):
            return False
    if args.relationship:
        related = []
        for key in endpoint_keys(variant):
            related.extend(rel_by_endpoint.get(key, []))
        if not any(rel.get("relationship_type") == args.relationship for rel in related):
            return False
    return True


def matches(record: dict[str, Any], args: argparse.Namespace, indexes: dict[str, Any]) -> bool:
    if args.risk_id and record.get("risk_id") != args.risk_id:
        return False
    if args.dimension and record.get("dimension") != args.dimension:
        return False
    if args.category_contains and args.category_contains.lower() not in text(record.get("category")).lower():
        return False
    if args.owner_contains and args.owner_contains.lower() not in record_owner(record).lower():
        return False
    variant = indexes["variants_by_source"].get(str(record.get("risk_id")), {})
    variant_filter_names = [
        "source_variant_id",
        "definition_id",
        "industry",
        "product",
        "jurisdiction",
        "architecture",
        "feature",
        "actor",
        "maturity_stage",
        "threat_stage",
        "money_movement",
        "data_sensitivity",
        "tenant_model",
        "control",
        "gate",
        "relationship",
        "changed_component",
        "task_packet_keyword",
    ]
    variant_filters = any(getattr(args, name) for name in variant_filter_names)
    if variant_filters and not variant:
        return False
    if variant and not variant_matches(variant, args, indexes["rel_by_endpoint"]):
        return False
    if args.keyword:
        haystack = " ".join([text(record), text(variant)]).lower()
        if args.keyword.lower() not in haystack:
            return False
    return True


def project_record(record: dict[str, Any], args: argparse.Namespace, indexes: dict[str, Any]) -> dict[str, Any]:
    variant = indexes["variants_by_source"].get(str(record.get("risk_id")), {})
    ref = f"{variant.get('risk_definition_id')}@{variant.get('definition_version')}" if variant else None
    definition = indexes["definitions_by_ref"].get(ref or "", {})
    result: dict[str, Any] = {
        "risk_id": record.get("risk_id"),
        "canonical_name": record.get("canonical_name"),
        "dimension": record.get("dimension"),
        "category": record.get("category"),
    }
    if variant:
        result["risk_definition_id"] = variant.get("risk_definition_id")
        result["definition_version"] = variant.get("definition_version")
    if args.retrieval_level >= 2:
        result.update({
            "risk_context_variant_id": variant.get("risk_context_variant_id"),
            "context": variant.get("context", {}),
            "owner": record_owner(record),
            "source_location": variant.get("source_location") or {"source_heading_name": record.get("source_heading_name"), "source_line_start": record.get("source_line_start")},
        })
    if args.retrieval_level >= 3:
        result["normalized_definition"] = definition.get("normalized_definition")
        result["semantic_review_status"] = definition.get("semantic_review_status")
        result["definition_content_sha256"] = definition.get("definition_content_sha256")
    if args.retrieval_level >= 4:
        related = []
        seen_relationships: set[str] = set()
        for key in endpoint_keys(variant):
            for rel in indexes["rel_by_endpoint"].get(key, []):
                rel_id = str(rel.get("relationship_id") or json.dumps(rel, sort_keys=True))
                if rel_id not in seen_relationships:
                    seen_relationships.add(rel_id)
                    related.append(rel)
        result["relationships"] = related
        result["raw_record"] = record
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select PREOS model2 risk records without unbounded context loading.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--variants", default=str(DEFAULT_VARIANTS))
    parser.add_argument("--definitions", default=str(DEFAULT_DEFINITIONS))
    parser.add_argument("--relationships", default=str(DEFAULT_RELATIONSHIPS))
    parser.add_argument("--id", dest="risk_id")
    parser.add_argument("--definition-id")
    parser.add_argument("--source-variant-id")
    parser.add_argument("--dimension", choices=["universal", "industry", "product", "jurisdiction", "architecture"])
    parser.add_argument("--category-contains")
    parser.add_argument("--owner-contains")
    parser.add_argument("--keyword")
    parser.add_argument("--industry")
    parser.add_argument("--product")
    parser.add_argument("--jurisdiction")
    parser.add_argument("--architecture")
    parser.add_argument("--feature")
    parser.add_argument("--actor")
    parser.add_argument("--maturity-stage")
    parser.add_argument("--threat-stage")
    parser.add_argument("--money-movement")
    parser.add_argument("--data-sensitivity")
    parser.add_argument("--tenant-model")
    parser.add_argument("--control")
    parser.add_argument("--gate")
    parser.add_argument("--relationship", choices=REL_TYPES)
    parser.add_argument("--changed-component")
    parser.add_argument("--task-packet-keyword")
    parser.add_argument("--retrieval-level", type=int, choices=[1, 2, 3, 4], default=2)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--allow-unbounded", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.limit > MAX_LIMIT and not args.allow_unbounded:
        raise SystemExit(f"--limit above {MAX_LIMIT} requires --allow-unbounded")
    corpus = Path(args.corpus)
    if not corpus.is_file():
        raise SystemExit("model2 risk corpus is not installed; run migration gates before using this selector")
    indexes = make_indexes(args)
    selected = []
    with corpus.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if matches(record, args, indexes):
                selected.append(project_record(record, args, indexes))
                if len(selected) >= args.limit:
                    break
    print(json.dumps({"count": len(selected), "retrieval_level": args.retrieval_level, "records": selected}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
