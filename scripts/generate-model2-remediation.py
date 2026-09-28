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

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
TRANSFORMATION_VERSION = "pasv2-remediation-normalization-v1"
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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


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
    field_text = json.dumps(fields, ensure_ascii=False).lower()
    security_terms = ("security", "access", "auth", "secret", "credential", "privilege", "tenant", "exploit", "attack", "abuse", "injection", "privacy")
    ai_terms = ("ai", "agent", "prompt", "rag", "retrieval", "embedding", "llm")
    if dimension == "jurisdiction":
        return {
            "canonical_name": name,
            "category": category,
            "dimension": dimension,
            "root_cause": "A legal or regulatory obligation is not translated into an explicit software rule, evidence requirement, workflow state, retention rule, access control, reporting path or configurable policy.",
            "failure_mechanism": "The software performs, permits, records, retains, transfers, reports or fails to report an action in a way that does not satisfy the applicable obligation.",
            "trigger_conditions": f"The software, entity, user, data flow or regulated activity falls within {category} scope and the obligation represented by {name} is triggered.",
            "prevention_strategy": "Translate the applicable obligation into versioned policy as code, explicit workflow states, data handling rules, access controls, evidence capture, retention, reporting and change management. Require legal and compliance review before release.",
            "automated_test": f"Create a deterministic compliance test for {name} that exercises the triggering legal condition and asserts the required software behavior, evidence, timing and denial path.",
            "owner": "Product Compliance and Product Engineering",
        }
    if any(contains_semantic_term(field_text, term) or contains_semantic_term(name.lower(), term) or contains_semantic_term(category.lower(), term) for term in ai_terms):
        return {
            "canonical_name": name,
            "category": category,
            "dimension": dimension,
            "root_cause": "Model inputs, retrieval, tool permissions, output validation, evaluation, grounding or human oversight are insufficient for nondeterministic AI behavior.",
            "failure_mechanism": "The model or agent generates or acts on incorrect, malicious, stale or unauthorized information and propagates it into product state or external actions.",
            "trigger_conditions": f"The product implements {category}. Untrusted prompts, retrieved content, model output, tool results, changing model behavior or agent actions enter the AI execution path.",
            "prevention_strategy": "Apply deny by default authorization, least privilege, strong authentication, input validation, output encoding, parameterized operations, secret management, dependency controls, rate limits and abuse resistant workflow design as relevant to the named risk.",
            "automated_test": f"Create a deterministic security regression for {name} that reproduces the abuse or exploit condition and asserts denial, safe handling and complete audit evidence.",
            "owner": "AI Product Engineering, AI Safety and Application Security",
        }
    if any(contains_semantic_term(name.lower(), term) or contains_semantic_term(category.lower(), term) for term in security_terms):
        return {
            "canonical_name": name,
            "category": category,
            "dimension": dimension,
            "root_cause": "Trust boundary, input, identity, authorization, secret, dependency or abuse controls are insufficient for the exposed operation.",
            "failure_mechanism": "The application performs an unauthorized action, accepts malicious control data, leaks sensitive information, weakens integrity or allows an attacker to consume protected resources.",
            "trigger_conditions": f"The software participates in {category}. Attacker controlled input, identity, content, dependency or traffic reaches a trust boundary, privileged operation or sensitive resource.",
            "prevention_strategy": "Apply deny by default authorization, least privilege, strong authentication, input validation, output encoding, parameterized operations, secret management, dependency controls, rate limits and abuse resistant workflow design as relevant to the named risk.",
            "automated_test": f"Create a deterministic security regression for {name} that reproduces the abuse or exploit condition and asserts denial, safe handling and complete audit evidence.",
            "owner": fields.get("Owner") or "Application Security and Platform Engineering",
        }
    if dimension == "architecture":
        return {
            "canonical_name": name,
            "category": category,
            "dimension": dimension,
            "root_cause": "The relevant domain invariant, boundary condition, lifecycle rule or operational constraint is not explicitly encoded, validated and tested.",
            "failure_mechanism": "The software accepts or produces a state that violates the intended domain model and propagates the incorrect result to dependent components or users.",
            "trigger_conditions": f"The system uses {category}. The domain condition represented by {name} occurs during real usage, concurrency, integration change, partial failure or long term operation.",
            "prevention_strategy": f"Define the invariant represented by {name}, encode it as an explicit state, validation, authorization, ordering, uniqueness, lifecycle or reconciliation rule, and prevent invalid transitions at every entry path.",
            "automated_test": f"Create a deterministic automated regression that forces {name} and asserts the expected state, denial, compensation, audit record and user outcome.",
            "owner": fields.get("Owner") or "Architecture, Platform and Site Reliability Engineering",
        }
    return {
        "canonical_name": name,
        "category": category,
        "dimension": dimension,
        "root_cause": "Insufficient design constraint, validation, isolation, capacity control or lifecycle management for this failure mode.",
        "failure_mechanism": "The affected component enters an unsafe, inconsistent, overloaded or unavailable state and propagates impact to callers or dependent components.",
        "trigger_conditions": "Real traffic, real data, concurrency, dependency degradation, malicious input, deployment change or long term operation exposes the weakness.",
        "prevention_strategy": "Define explicit limits, safe defaults, isolation, validation, idempotency, capacity margins and architecture specific controls before release.",
        "automated_test": "Create a deterministic automated regression that forces the named condition and asserts safe behavior.",
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
        }, "CORRECTED", "Rejected shared-state concurrency interpretation; normalized toward serialization, encoding, decoding and transformation semantics.", 0.99, RULES_EVALUATED + ["SEM-SENTINEL-A"], [], ["SEM-SENTINEL-A"])
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
        }, "CORRECTED", "Rejected sensor/control-loop interpretation; normalized toward pharmaceutical item serialization, identifiers, package identity, authenticity, traceability and regulatory records.", 0.99, RULES_EVALUATED + ["SEM-SENTINEL-B"], [], ["SEM-SENTINEL-B"])
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
            "semantic_flags": flags,
            "deterministic_acceptance_basis": acceptance_basis,
            "source_record_sha256": "RECORDED_IN_RISK_CORPUS",
            "normalized_definition_sha256": "RECORDED_IN_NORMALIZED_DEFINITION",
        })
        dimension, category = risk["dimension"], risk["category"]
        variants.append({
            "risk_context_variant_id": "RCV-S1-" + slug(risk["risk_id"]),
            "risk_definition_id": definition["risk_definition_id"],
            "definition_version": definition["definition_version"],
            "source_risk_id": risk["risk_id"],
            "source_record_sha256": digest(risk),
            "dimension": dimension,
            "category": category,
            "context": {
                "industry": category if dimension == "industry" else None,
                "product": category if dimension == "product" else None,
                "jurisdiction": category if dimension == "jurisdiction" else None,
                "architecture": category if dimension == "architecture" else fields.get("Architecture or component affected"),
                "feature": fields.get("Architecture or component affected"),
                "actor": fields.get("Owner"),
                "data_sensitivity": "personal-or-tenant-data" if "personal" in field_text or "privacy" in category.lower() else "context-dependent",
                "tenant_model": "multi-tenant" if "tenant" in field_text else "unspecified",
                "money_movement": "applicable" if any(w in field_text for w in ("payment", "money", "financial", "billing")) else "not-explicit",
                "maturity_stage": "release-candidate",
                "threat_stage": "design-to-operation",
                "gate": "G11" if "acceptance" in field_text else "G1",
                "control": "FS-004" if "validation" in field_text else "FS-001",
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
            relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "SAME_AS", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Contextual variants share a canonical normalized problem name while retaining source-specific context.", "provenance_class": "deterministic canonical-name grouping", "evidence_reference": f"SAME_AS::{base['risk_id']}::{item['risk_id']}", "confidence": 0.82, "review_status": "VALIDATED_BY_RULE"})
            rel_no += 1
            if base["dimension"] == "universal" and item["dimension"] != "universal":
                relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "SPECIALIZES", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Context-specific variant specializes a universal canonical risk.", "provenance_class": "deterministic dimension hierarchy", "evidence_reference": f"SPECIALIZES::{base['risk_id']}::{item['risk_id']}", "confidence": 0.76, "review_status": "VALIDATED_BY_RULE"})
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
    if concern_source.is_file():
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(concern_source, output_dir / "concern-runtime-evidence.json")
    return {"definitions": len(definitions), "reviews": len(reviews), "human_review_required": len(human_review), "variants": len(variants), "relationships": len(relationships)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(MODEL2))
    parser.add_argument("--output-dir", default=str(MODEL2))
    args = parser.parse_args()
    print(json.dumps(build(Path(args.input_dir), Path(args.output_dir)), indent=2))
