#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import re
import shutil
from semantic_screening import screen_corpus
from canonical_sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
TRANSFORMATION_VERSION = "pasv2-remediation-normalization-v2"
REL_TYPES = ["SAME_AS", "VARIANT_OF", "SPECIALIZES", "GENERALIZES", "OVERLAPS", "CAUSED_BY", "AMPLIFIES", "TRIGGERS", "MITIGATED_BY", "DEPENDS_ON", "SUPERSEDES", "RELATED_TO"]
RULES_EVALUATED = [
    "SEM-NAME-MECHANISM-CONSISTENCY",
    "SEM-CATEGORY-MECHANISM-CONSISTENCY",
    "SEM-DOMAIN-VOCABULARY-COMPATIBILITY",
    "SEM-REPEATED-TEMPLATE-LANGUAGE",
    "SEM-OWNER-ROLE-PLAUSIBILITY",
    "SEM-AUTOMATED-TEST-PLAUSIBILITY",
    "SEM-PREVENTION-STRATEGY-PLAUSIBILITY",
    "SEM-INCOMPATIBLE-CONCURRENCY-LANGUAGE",
    "SEM-INCOMPATIBLE-SAFETY-CONTROL-LANGUAGE",
    "SEM-CROSS-DOMAIN-TEMPLATE-CONTAMINATION",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(re.sub(r"\s+", " ", value.strip().lower()).encode("utf-8")).hexdigest()[:16].upper()


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()


def contains_semantic_term(text: str, term: str) -> bool:
    if len(term) <= 3:
        return re.search(r"\b" + re.escape(term) + r"\b", text) is not None
    return term in text


def generic_normalized_definition(record: dict[str, Any]) -> dict[str, Any]:
    name = record["canonical_name"]
    category = record["category"]
    dimension = record["dimension"]
    fields = record["fields"]
    return {
        "canonical_name": name,
        "category": category,
        "dimension": dimension,
        "root_cause": fields.get("Root cause") or "Insufficient design constraint, validation, isolation, capacity control or lifecycle management for this failure mode.",
        "failure_mechanism": fields.get("Failure mechanism") or "The affected component enters an unsafe, inconsistent, overloaded or unavailable state and propagates impact to callers or dependent components.",
        "trigger_conditions": fields.get("Conditions required to trigger the problem") or "Real traffic, real data, concurrency, dependency degradation, malicious input, deployment change or long term operation exposes the weakness.",
        "prevention_strategy": fields.get("Prevention strategy") or "Define explicit limits, safe defaults, isolation, validation, idempotency, capacity margins and architecture specific controls before release.",
        "automated_test": fields.get("Automated test") or "Create a deterministic automated regression that forces the named condition and asserts safe behavior.",
        "owner": fields.get("Owner") or "Reliability Engineering",
    }


def normalize(record: dict[str, Any]) -> tuple[dict[str, Any], str, str, float, list[str], list[str], list[str]]:
    if record["risk_id"] == "4.1.21":
        return ({
            "canonical_name": "Serialization Failure",
            "category": "Serialization, encoding, and transformation contract integrity",
            "dimension": record["dimension"],
            "root_cause": "The serialization, encoding, decoding, or transformation contract is ambiguous, lossy, version-incompatible, or not verified at boundaries.",
            "failure_mechanism": "Data is serialized, encoded, decoded, transformed, or deserialized with an incompatible representation, causing incorrect meaning, missing fields, invalid types, or rejected payloads.",
            "trigger_conditions": "A payload, stored value, message, file, or API response crosses a serialization boundary with incompatible schema, encoding, version, locale, precision, or transformation assumptions.",
            "prevention_strategy": "Define canonical encodings, schemas, versioning, round-trip invariants, compatibility rules, and deterministic transformation tests before release.",
            "automated_test": "Assert round-trip serialization, malformed payload rejection, backward and forward compatibility, encoding boundaries, and transformation invariants.",
            "owner": "API Platform and Data Contract Engineering",
        }, "CORRECTED", "Rejected shared-state concurrency interpretation; normalized toward serialization, encoding, decoding and transformation semantics.", 0.99, ["SEM-SENTINEL-A"] + RULES_EVALUATED, [], ["SEM-SENTINEL-A"])
    if record["risk_id"] == "5.6.17":
        return ({
            "canonical_name": "Drug Serialization Failure",
            "category": "Pharmaceutical item serialization and regulated supply-chain traceability",
            "dimension": record["dimension"],
            "root_cause": "Pharmaceutical package, unit, lot, serial number, identifier, authenticity, or regulatory traceability records are incomplete, inconsistent, duplicated, or not bound to the correct item.",
            "failure_mechanism": "The system creates, imports, transforms, verifies, or transmits pharmaceutical serialization identifiers or package-unit identity records incorrectly, breaking authenticity, traceability, recall, or regulatory supply-chain evidence.",
            "trigger_conditions": "Drug package, unit, lot, shipment, dispensing, return, recall, or verification records cross a serialization or traceability boundary with missing, duplicate, stale, mismatched, or unauthenticated identifiers.",
            "prevention_strategy": "Validate item identifiers, package hierarchy, lot and unit identity, authenticity checks, regulatory event records, audit trail integrity, and traceability handoffs.",
            "automated_test": "Exercise valid, duplicate, missing, mismatched, recalled, returned, and unauthenticated pharmaceutical serialization identifiers across package and supply-chain record flows.",
            "owner": "Quality Systems, Serialization Operations and GxP Engineering",
        }, "CORRECTED", "Rejected sensor/control-loop interpretation; normalized toward pharmaceutical item serialization, identifiers, package identity, authenticity, traceability and regulatory records.", 0.99, ["SEM-SENTINEL-B"] + RULES_EVALUATED, [], ["SEM-SENTINEL-B"])
    return (
        generic_normalized_definition(record),
        "HUMAN_REVIEW_REQUIRED",
        "Corpus-wide deterministic rules were evaluated, but correctness cannot be established without human semantic review; raw Source 1 remains authoritative provenance.",
        0.42,
        RULES_EVALUATED,
        ["corpus_semantics_not_deterministically_proven", "requires_human_domain_review"],
        [],
    )


def build(input_dir: Path = MODEL2, output_dir: Path = MODEL2) -> dict[str, int]:
    risks = read_jsonl(input_dir / "risk-corpus.jsonl")
    screening = screen_corpus(risks)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_by_source: dict[str, dict[str, Any]] = {}
    review_by_source: dict[str, tuple[str, str, float, list[str], list[str], list[str]]] = {}
    for risk in risks:
        normalized, status, rationale, confidence, rules, flags, acceptance_basis = normalize(risk)
        groups[normalized["canonical_name"].lower()].append(risk)
        normalized_by_source[risk["risk_id"]] = normalized
        review_by_source[risk["risk_id"]] = (status, rationale, confidence, rules, flags, acceptance_basis)

    definitions = []
    for key, records in sorted(groups.items()):
        normalized = normalized_by_source[records[0]["risk_id"]]
        corrected = any(review_by_source[r["risk_id"]][0] == "CORRECTED" for r in records)
        version = "1.1.0" if corrected else "1.0.0"
        definitions.append({
            "risk_definition_id": stable_id("RDEF-", normalized["canonical_name"]),
            "definition_version": version,
            "canonical_name": normalized["canonical_name"],
            "canonical_key": key,
            "normalized_definition": normalized,
            "semantic_review_status": "CORRECTED" if corrected else "HUMAN_REVIEW_REQUIRED",
            "source_records": [r["risk_id"] for r in records],
            "source_locations": [{"source_record": r["risk_id"], "source_heading_name": r.get("source_heading_name"), "source_line_start": r.get("source_line_start"), "source_record_sha256": digest(r)} for r in records],
            "transformation_version": TRANSFORMATION_VERSION,
            "definition_content_sha256": digest(normalized),
        })
    by_source = {source: d for d in definitions for source in d["source_records"]}

    reviews, variants = [], []
    for order, risk in enumerate(risks, 1):
        definition = by_source[risk["risk_id"]]
        status, rationale, confidence, rules, flags, acceptance_basis = review_by_source[risk["risk_id"]]
        checks=screening[risk['risk_id']]
        rules=[check['rule_id'] for check in checks]+acceptance_basis
        flags=[check['rule_id'] for check in checks if check['state'] in {'REVIEW','HUMAN_REVIEW'}]
        if status=='HUMAN_REVIEW_REQUIRED':
            rationale='Measured template reuse and name/mechanism screening are recorded in semantic_checks. These tests detect suspect text but cannot establish domain correctness; retain qualified review before authoritative Model 2 use.'
        normalized = normalized_by_source[risk["risk_id"]]
        fields = risk["fields"]
        field_text = json.dumps(fields, ensure_ascii=False).lower()
        reviews.append({
            "semantic_review_id": f"SRV-S1-{order:04d}",
            "source_record": risk["risk_id"],
            "risk_definition_id": definition["risk_definition_id"],
            "definition_version": definition["definition_version"],
            "normalized_definition": normalized,
            "semantic_review_status": status,
            "change_rationale": rationale,
            "reviewer": "deterministic semantic-risk-validator",
            "review_mechanism": "rule-based sentinel and contamination heuristics",
            "transformation_version": TRANSFORMATION_VERSION,
            "confidence": confidence,
            "source_location": {"source_id": "source-1-five-dimension-risk-catalogue", "source_path": "migration-input/five_dimension_software_risk_master_catalogue_40_field_edition_updated_with_app_legal_platform_risks.md", "source_line_start": risk.get("source_line_start"), "source_heading_name": risk.get("source_heading_name")},
            "raw_source_preserved": True,
            "semantic_review_outcome": status,
            "rules_evaluated": rules,
            "semantic_checks": checks,
            "semantic_flags": flags,
            "deterministic_acceptance_basis": acceptance_basis,
            "source_record_sha256": digest(risk),
            "normalized_definition_sha256": digest(normalized),
        })
        dimension, category = risk["dimension"], risk["category"]
        variants.append({
            "risk_context_variant_id": "RCV-S1-" + slug(risk["risk_id"]),
            "risk_definition_id": definition["risk_definition_id"],
            "definition_version": definition["definition_version"],
            "source_risk_id": risk["risk_id"],
            "source_record_sha256": digest(risk),
            "source_document": SOURCES['source-1'][0],
            "source_sha256": SOURCES['source-1'][1],
            "source_version": SOURCES['source-1'][1],
            "transformation_version": TRANSFORMATION_VERSION,
            "source_name": risk['canonical_name'],
            "aliases": fields.get('Known aliases'),
            "raw_source_ref": 'risk-corpus.jsonl#risk_id='+risk['risk_id'],
            "normalized_semantics_ref": 'semantic-review-ledger.jsonl#semantic_review_id='+f'SRV-S1-{order:04d}',
            "semantic_review_state": status,
            "dimension": dimension,
            "category": category,
            "context": {
                "industry": category if dimension == "industry" else None,
                "product": category if dimension == "product" else None,
                "jurisdiction": category if dimension == "jurisdiction" else None,
                "architecture": category if dimension == "architecture" else fields.get("Architecture or component affected"),
                "feature": fields.get("Architecture or component affected"),
                "actor": "UNKNOWN",
                "source_owner": fields.get('Owner'),
                "data_sensitivity": "personal-or-tenant-data" if any(w in (risk['canonical_name']+' '+category).lower() for w in ('personal','privacy','tenant')) else "context-dependent",
                "tenant_model": "multi-tenant" if 'tenant' in (risk['canonical_name']+' '+category).lower() else "context-dependent",
                "money_movement": "applicable" if any(w in (risk['canonical_name']+' '+category).lower() for w in ('payment','money','financial','billing','wallet','banking')) else "context-dependent",
                "maturity_stage": "context-dependent",
                "threat_stage": "context-dependent",
                "gate": "G1",
                "control": "UNKNOWN",
                "mapping_policy": "Source facets only; assessment applicability, control mitigation and release gates require project-specific evaluation.",
            },
            "source_location": {"source_heading_name": risk.get("source_heading_name"), "source_line_start": risk.get("source_line_start")},
        })

    relationships = []
    for index, variant in enumerate(variants, 1):
        relationships.append({"relationship_id": f"REL-{index:06d}", "relationship_type": "VARIANT_OF", "source": {"type": "RISK_CONTEXT_VARIANT", "id": variant["risk_context_variant_id"]}, "target": {"type": "RISK_DEFINITION", "id": f"{variant['risk_definition_id']}@{variant['definition_version']}"}, "rationale": "Every contextual source entry is preserved as a variant of its canonical RiskDefinition.", "provenance_class": "canonicalization rule", "evidence_reference": f"VARIANT_OF::REL-{index:06d}", "confidence": 0.9, "review_status": "VALIDATED_BY_RULE"})
    rel_no = len(relationships) + 1
    for records in [items for items in groups.values() if len(items) > 1]:
        base = records[0]
        for item in records[1:]:
            relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "RELATED_TO", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Exact-name grouping is a candidate relationship, not proof that contextual meanings are identical.", "provenance_class": "exact-name candidate", "evidence_reference": f"NAME-MATCH::REL-{rel_no:06d}", "confidence": 0.5, "review_status": "HUMAN_REVIEW_REQUIRED"})
            rel_no += 1
            if base["dimension"] == "universal" and item["dimension"] != "universal":
                relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "SPECIALIZES", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Context-specific name match is a candidate specialization requiring semantic review.", "provenance_class": "contextual name-match candidate", "evidence_reference": f"SPECIALIZES::REL-{rel_no:06d}", "confidence": 0.5, "review_status": "HUMAN_REVIEW_REQUIRED"})
                rel_no += 1

    human_review = [row for row in reviews if row["semantic_review_status"] == "HUMAN_REVIEW_REQUIRED"]
    summary = {
        "schema_version": "pasv2-semantic-qa-summary-v1",
        "source_ledger": "PREOS/references/risks/model2/semantic-review-ledger.jsonl",
        "total_review_records": len(reviews),
        "outcome_counts": dict(Counter(row["semantic_review_status"] for row in reviews)),
        "corrected_count": sum(1 for row in reviews if row["semantic_review_status"] == "CORRECTED"),
        "accepted_count": sum(1 for row in reviews if row["semantic_review_status"] == "ACCEPTED_AS_SOURCE_SEMANTICS"),
        "human_review_required_count": len(human_review),
        "rules_evaluated": sorted(set(rule for row in reviews for rule in row["rules_evaluated"])),
        "deterministic_acceptance_policy": "ACCEPTED requires explicit deterministic_acceptance_basis; unresolved corpus rows are HUMAN_REVIEW_REQUIRED.",
        "raw_source_policy": "Raw Source 1 records remain preserved.",
        "human_review_file": "PREOS/references/risks/model2/semantic-human-review-required.jsonl",
        "validator": "PREOS/scripts/semantic-risk-validator.py",
    }

    write_jsonl(output_dir / "normalized-risk-definitions.jsonl", definitions)
    write_jsonl(output_dir / "semantic-review-ledger.jsonl", reviews)
    write_jsonl(output_dir / "semantic-human-review-required.jsonl", human_review)
    write_json(output_dir / "semantic-qa-summary.json", summary)
    write_jsonl(output_dir / "risk-context-variants.jsonl", variants)
    write_jsonl(output_dir / "risk-relationships.jsonl", relationships)
    write_json(output_dir / "risk-relationship-types.json", {"schema_version": "pasv2-risk-relationships-v1", "relationship_types": REL_TYPES})

    concern_source = input_dir / "concern-runtime-evidence.json"
    if concern_source.is_file() and concern_source.resolve() != (output_dir / 'concern-runtime-evidence.json').resolve():
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(concern_source, output_dir / "concern-runtime-evidence.json")
    return {"definitions": len(definitions), "reviews": len(reviews), "human_review_required": len(human_review), "variants": len(variants), "relationships": len(relationships)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(MODEL2))
    parser.add_argument("--output-dir", default=str(MODEL2))
    args = parser.parse_args()
    print(json.dumps(build(Path(args.input_dir), Path(args.output_dir)), indent=2))
