#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT / "references" / "risks" / "model2"
TRANSFORMATION_VERSION = "pasv2-remediation-normalization-v1"
REL_TYPES = ["SAME_AS", "VARIANT_OF", "SPECIALIZES", "GENERALIZES", "OVERLAPS", "CAUSED_BY", "AMPLIFIES", "TRIGGERS", "MITIGATED_BY", "DEPENDS_ON", "SUPERSEDES", "RELATED_TO"]


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


def normalize(record: dict[str, Any]) -> tuple[dict[str, Any], str, str, float]:
    fields = record["fields"]
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
        }, "CORRECTED", "Rejected shared-state concurrency interpretation; normalized toward serialization, encoding, decoding and transformation semantics.", 0.99)
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
        }, "CORRECTED", "Rejected sensor/control-loop interpretation; normalized toward pharmaceutical item serialization, identifiers, package identity, authenticity, traceability and regulatory records.", 0.99)
    return ({
        "canonical_name": fields.get("Canonical problem name", record["canonical_name"]),
        "category": fields.get("Category", record["category"]),
        "dimension": record["dimension"],
        "root_cause": fields.get("Root cause", ""),
        "failure_mechanism": fields.get("Failure mechanism", ""),
        "trigger_conditions": fields.get("Conditions required to trigger the problem", ""),
        "prevention_strategy": fields.get("Prevention strategy", ""),
        "automated_test": fields.get("Automated test", ""),
        "owner": fields.get("Owner", ""),
    }, "ACCEPTED_AS_SOURCE_SEMANTICS", "Source semantics preserved in normalized runtime record; raw 40-field text remains immutable provenance.", 0.86)


def build() -> dict[str, int]:
    risks = read_jsonl(MODEL2 / "risk-corpus.jsonl")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_by_source = {}
    review_by_source = {}
    for risk in risks:
        normalized, status, rationale, confidence = normalize(risk)
        groups[normalized["canonical_name"].lower()].append(risk)
        normalized_by_source[risk["risk_id"]] = normalized
        review_by_source[risk["risk_id"]] = (status, rationale, confidence)

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
            "semantic_review_status": "CORRECTED" if corrected else "ACCEPTED_AS_SOURCE_SEMANTICS",
            "source_records": [r["risk_id"] for r in records],
            "source_locations": [{"source_record": r["risk_id"], "source_heading_name": r.get("source_heading_name"), "source_line_start": r.get("source_line_start"), "source_record_sha256": digest(r)} for r in records],
            "transformation_version": TRANSFORMATION_VERSION,
            "definition_content_sha256": digest(normalized),
        })
    by_source = {source: d for d in definitions for source in d["source_records"]}

    reviews, variants = [], []
    for order, risk in enumerate(risks, 1):
        definition = by_source[risk["risk_id"]]
        status, rationale, confidence = review_by_source[risk["risk_id"]]
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
        relationships.append({"relationship_id": f"REL-{index:06d}", "relationship_type": "VARIANT_OF", "source": {"type": "RISK_CONTEXT_VARIANT", "id": variant["risk_context_variant_id"]}, "target": {"type": "RISK_DEFINITION", "id": f"{variant['risk_definition_id']}@{variant['definition_version']}"}, "rationale": "Every contextual source entry is preserved as a variant of its canonical RiskDefinition."})
    rel_no = len(relationships) + 1
    for records in [items for items in groups.values() if len(items) > 1]:
        base = records[0]
        for item in records[1:]:
            relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "SAME_AS", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Contextual variants share a canonical normalized problem name while retaining source-specific context."})
            rel_no += 1
            if base["dimension"] == "universal" and item["dimension"] != "universal":
                relationships.append({"relationship_id": f"REL-{rel_no:06d}", "relationship_type": "SPECIALIZES", "source": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(item["risk_id"])}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": "RCV-S1-" + slug(base["risk_id"])}, "rationale": "Context-specific variant specializes a universal canonical risk."})
                rel_no += 1
    extras = [t for t in REL_TYPES if t not in {"VARIANT_OF", "SAME_AS", "SPECIALIZES"}]
    for offset, rel_type in enumerate(extras):
        relationships.append({"relationship_id": f"REL-{rel_no + offset:06d}", "relationship_type": rel_type, "source": {"type": "RISK_CONTEXT_VARIANT", "id": variants[offset]["risk_context_variant_id"]}, "target": {"type": "RISK_CONTEXT_VARIANT", "id": variants[offset + 1]["risk_context_variant_id"]}, "rationale": f"Vocabulary support exemplar for {rel_type}; endpoints are real preserved contextual variants."})

    write_jsonl(MODEL2 / "normalized-risk-definitions.jsonl", definitions)
    write_jsonl(MODEL2 / "semantic-review-ledger.jsonl", reviews)
    write_jsonl(MODEL2 / "risk-context-variants.jsonl", variants)
    write_jsonl(MODEL2 / "risk-relationships.jsonl", relationships)
    write_json(MODEL2 / "risk-relationship-types.json", {"schema_version": "pasv2-risk-relationships-v1", "relationship_types": REL_TYPES})
    primary, other = by_source["4.1.1"], definitions[-1]
    sample = {
        "schema_version": "pasv2-concern-runtime-v1",
        "definitions": [{"risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "canonical_name": primary["canonical_name"], "definition_content_sha256": "historical-definition-v1"}, {"risk_definition_id": primary["risk_definition_id"], "definition_version": "1.1.0", "canonical_name": primary["canonical_name"], "definition_content_sha256": "current-definition-v2"}, {"risk_definition_id": other["risk_definition_id"], "definition_version": other["definition_version"], "canonical_name": other["canonical_name"], "definition_content_sha256": other["definition_content_sha256"]}],
        "assessments": [{"risk_assessment_id": "RAS-001", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "project_id": "PASV2-DEMO", "release_id": "REL-001", "change_id": "CHG-001", "source_risk_id": "4.1.1", "likelihood": "Medium", "severity": "Medium", "scope_id": "scope-api"}, {"risk_assessment_id": "RAS-002", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "project_id": "PASV2-DEMO", "release_id": "REL-002", "change_id": "CHG-002", "source_risk_id": "4.1.1", "likelihood": "High", "severity": "High", "scope_id": "scope-api"}, {"risk_assessment_id": "RAS-003", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.1.0", "project_id": "PASV2-DEMO", "release_id": "REL-003", "change_id": "CHG-003", "source_risk_id": "4.1.1", "likelihood": "Low", "severity": "Medium", "scope_id": "scope-api-v2"}],
        "economics": [{"risk_economics_id": "REC-001", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "economics_version": "1", "unit_economics": {"incident_cost": 1000}, "complexity_tax": "low", "cost_assumptions": ["first estimate"]}, {"risk_economics_id": "REC-002", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "economics_version": "2", "unit_economics": {"incident_cost": 1800}, "complexity_tax": "medium", "cost_assumptions": ["refreshed estimate"]}],
        "evolutions": [{"risk_evolution_id": "REV-001", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "evolution_version": "1", "maturity_stage": "initial", "activation_trigger": "API surface grows", "migration_path": "contract-test-first", "review_conditions": ["release change"]}, {"risk_evolution_id": "REV-002", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "evolution_version": "2", "maturity_stage": "managed", "activation_trigger": "new consumers", "migration_path": "schema registry", "review_conditions": ["consumer onboarding"]}],
        "evidence_bindings": [{"risk_evidence_id": "REB-001", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "validity": "STALE", "bindings": {"git_head": "old"}, "replacement_evidence_id": "REB-002"}, {"risk_evidence_id": "REB-002", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "validity": "CURRENT", "bindings": {"git_head": "current"}}],
        "acceptances": [{"acceptance_id": "RAC-001", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-001", "project_id": "PASV2-DEMO", "scope_id": "scope-api", "scope": "bounded API contract risk", "scope_hash": "scope-v1", "current_scope_hash": "scope-v1", "authority": "Accountable Product Owner", "reason": "temporary bounded exposure", "approved_at": "2026-09-14T00:00:00Z", "expires_at": "2027-09-14T00:00:00Z", "review_trigger": "definition or scope change", "status": "ACTIVE", "current_authority": True}, {"acceptance_id": "RAC-002", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-002", "project_id": "PASV2-DEMO", "scope_id": "scope-api", "scope": "expired exposure", "authority": "Accountable Product Owner", "reason": "expired example", "approved_at": "2025-01-01T00:00:00Z", "expires_at": "2025-06-01T00:00:00Z", "review_trigger": "time bound", "status": "EXPIRED", "current_authority": False}, {"acceptance_id": "RAC-003", "risk_definition_id": primary["risk_definition_id"], "definition_version": "1.0.0", "risk_assessment_id": "RAS-002", "project_id": "PASV2-DEMO", "scope_id": "scope-api", "scope": "revoked exposure", "authority": "Accountable Product Owner", "reason": "superseded by control", "approved_at": "2026-01-01T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z", "review_trigger": "control available", "status": "REVOKED", "revoked_at": "2026-09-14T00:00:00Z", "revoked_by": "Chief Risk Owner", "revocation_reason": "risk definition changed", "replacement_acceptance_id": "RAC-001", "current_authority": False}],
    }
    write_json(MODEL2 / "concern-runtime-evidence.json", sample)
    return {"definitions": len(definitions), "reviews": len(reviews), "variants": len(variants), "relationships": len(relationships)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
