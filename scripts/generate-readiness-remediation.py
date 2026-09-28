#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
READINESS = ROOT / "references" / "readiness"
TRACEABILITY = ROOT / "references" / "traceability"
UNITS = ROOT / "references" / "source-units" / "PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl"

POLICIES = [
    ("SOURCE2-CREDENTIAL-AI-PROMPT", ("credential", "secret", "prompt", "ai generated", "coding prompt", "source code", "iac", "configuration"), "security-and-ai-data-handling-review", ["G3", "G8", "G11"], ["FS-015", "FS-026"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-AUTHZ-TENANT", ("authorisation", "authorization", "authentication", "privileged", "tenant", "account takeover", "cross tenant"), "authorization-and-tenant-boundary-review", ["G3", "G8", "G10"], ["FS-015", "FS-026"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-DATA-FLOW-PRIVILEGE", ("personal data", "data flow", "privacy", "privilege", "security", "compliance", "accurate legal"), "data-flow-and-privacy-review", ["G3", "G8", "G10"], ["FS-026", "FS-015"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-DEPENDENCY-LICENSE", ("dependenc", "licen", "third party", "open source", "software bill", "unverified"), "dependency-and-licensing-review", ["G2", "G8", "G11"], ["FS-015"], "gstack-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-LEGAL-REGULATORY", ("law", "regulat", "contractual", "retained", "exported", "deleted", "lawful", "industry obligation"), "legal-regulatory-readiness-review", ["G3", "G9", "G11"], ["FS-026", "FS-015"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-PAYMENT-BILLING", ("payment", "billing", "money", "financial", "market where it is offered"), "payment-and-billing-control-review", ["G5", "G10", "G11"], ["FS-050"], "gstack-plan-ceo-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-BACKUP-RESTORE", ("backup", "restore", "restoration", "rollback", "incident", "continuity", "monitoring", "support"), "backup-restore-and-rollback-evidence", ["G6", "G10", "G11"], ["FS-061", "FS-064", "FS-073"], "gstack-qa", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-PERFORMANCE-CAPACITY", ("performance", "scalability", "capacity", "latency", "load"), "performance-and-capacity-evidence", ["G6", "G10"], ["FS-067"], "gstack-benchmark", "not_required_by_unit", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-ACCESSIBILITY", ("accessibility", "usability", "user experience"), "accessibility-conformance-review", ["G7", "G11"], ["FS-070"], "gstack-design-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
]
EXISTING_KEYWORDS = {
    "api": "FS-001",
    "validation": "FS-004",
    "test": "FS-004",
    "security": "FS-015",
    "privacy": "FS-026",
    "incident": "FS-073",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def stable_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16].upper()


def classify(text: str, mode: str) -> tuple[str, str]:
    upper = text.upper()
    if upper.startswith("BEST PRACTICE"):
        return "best_practice", "positive_keypoint"
    if upper.startswith("DANGER"):
        return "danger_item", "blocker_rule"
    if upper.startswith("CAUTION"):
        return "caution_item", "negative_keypoint"
    if upper.startswith("DECISION GATE"):
        return "decision_gate", "release_implication"
    if mode == "evidence":
        return "required_evidence_item", "artifact_requirement"
    if "APPROVAL" in upper or "OWNER" in upper:
        return "ownership_requirement", "human_approval_boundary"
    if "APPLICABLE" in upper or "CONDITIONAL" in upper:
        return "applicability_rule", "decision_gate"
    if mode == "positive":
        return "positive_keypoint", "best_practice"
    if mode == "negative":
        return "negative_keypoint", "blocker_rule"
    return "framework_statement", "readiness_context"


def semantic_policy(text: str, classification: str) -> dict[str, Any]:
    lower = text.lower()
    for policy_id, terms, artifact, gates, controls, route, approval, status in POLICIES:
        if any(term in lower for term in terms):
            return {
                "policy_id": policy_id,
                "blueprint_artifact": artifact,
                "preos_gates": gates,
                "preos_control_ids": controls,
                "gstack_specialist_route": route,
                "human_approval_boundary": approval,
                "implementation_status": status,
                "mapping_status": "DETERMINISTIC_SEMANTIC_MAPPING",
                "review_status": "VALIDATED_BY_RULE",
                "evidence_requirements": ["deterministic readiness mapping and gate evidence"],
            }
    found = [control for word, control in EXISTING_KEYWORDS.items() if word in lower]
    if found:
        return {
            "policy_id": "SOURCE2-EXISTING-KEYWORD-MAP",
            "blueprint_artifact": "requirements-traceability-matrix" if "requirement" in lower else "release-checklist",
            "preos_gates": ["G11"],
            "preos_control_ids": sorted(set(found)),
            "gstack_specialist_route": "gstack-qa" if classification in {"decision_gate", "required_evidence_item"} else "gstack-plan-eng-review",
            "human_approval_boundary": "required" if classification in {"decision_gate", "danger_item", "blocker_rule", "ownership_requirement"} else "not_required_by_unit",
            "implementation_status": "IMPLEMENTED_BY_REMEDIATION",
            "mapping_status": "DETERMINISTIC_SEMANTIC_MAPPING",
            "review_status": "VALIDATED_BY_RULE",
            "evidence_requirements": ["deterministic readiness mapping and gate evidence"],
        }
    return {
        "policy_id": "SOURCE2-HUMAN-REVIEW-NO-DETERMINISTIC-MAP",
        "blueprint_artifact": "release-checklist",
        "preos_gates": [],
        "preos_control_ids": [],
        "gstack_specialist_route": "gstack-plan-eng-review",
        "human_approval_boundary": "required",
        "implementation_status": "HUMAN_REVIEW_REQUIRED",
        "mapping_status": "HUMAN_REVIEW_REQUIRED",
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "evidence_requirements": ["Retain source unit and require accountable human mapping before control/gate claims."],
    }


def build_readiness(units_path: Path = UNITS, output_dir: Path = READINESS) -> int:
    units = [u for u in load_jsonl(units_path) if u["source_id"] == "source-2-readiness-framework"]
    domains = load_json(READINESS / "domain-registry.json")["domains"]
    by_section = {int(d["source_section"]): d for d in domains}
    current = {"id": "RD-GLOBAL", "name": "Global readiness doctrine", "source_section": 0}
    mode = "context"
    rows = []
    for unit in units:
        text = unit["text_excerpt"]
        match = re.match(r"^(\d+)\.\s+", text)
        if match and int(match.group(1)) in by_section:
            current = by_section[int(match.group(1))]
            mode = "context"
        elif text.lower() == "positive keypoints":
            mode = "positive"
        elif text.lower() == "negative keypoints":
            mode = "negative"
        elif text.lower() == "required evidence":
            mode = "evidence"
        primary, secondary = classify(text, mode)
        policy = semantic_policy(text + " " + current["name"], primary)
        rows.append({
            "source_unit_id": unit["semantic_unit_id"],
            "source_location": {"source_id": unit["source_id"], "source_path": unit["source_path"], "source_line_or_paragraph": unit["source_line_or_paragraph"]},
            "excerpt_sha256": unit["text_sha256"],
            "excerpt": text,
            "classification": primary,
            "secondary_classification": secondary,
            "readiness_domain_id": current["id"],
            "readiness_domain": current["name"],
            "target_repository": "PREOS" if policy["mapping_status"] != "HUMAN_REVIEW_REQUIRED" else "HUMAN_REVIEW_REQUIRED",
            "target_artifacts": ["PREOS/references/readiness/source2-readiness-units.jsonl", "PREOS/references/readiness/r0-r17-gates.json", "PREOS/references/readiness/domain-registry.json"],
            "blueprint_lifecycle_stage": "release-readiness" if primary in {"decision_gate", "blocker_rule"} else "discovery-to-verification",
            "blueprint_profile": "production-readiness",
            "blueprint_artifact": policy["blueprint_artifact"],
            "preos_gates": policy["preos_gates"],
            "preos_risk_ids": ["model2-contextual-risk-selection"],
            "preos_control_ids": policy["preos_control_ids"],
            "evidence_requirements": policy["evidence_requirements"],
            "gstack_specialist_route": policy["gstack_specialist_route"],
            "human_approval_boundary": policy["human_approval_boundary"],
            "implementation_status": policy["implementation_status"],
            "validator": "PREOS/scripts/validate-readiness.py",
            "mapping_inputs": ["excerpt", "readiness_domain", "classification"],
            "mapping_policy_id": policy["policy_id"],
            "mapping_status": policy["mapping_status"],
            "review_status": policy["review_status"],
        })
    write_jsonl(output_dir / "source2-readiness-units.jsonl", rows)
    return len(rows)


def build_traceability(output_dir: Path = TRACEABILITY) -> None:
    nodes = ["source_document", "source_item", "normalized_runtime_record", "risk_definition", "risk_assessment", "control", "requirement", "task_packet", "implementation", "test", "evidence", "gate", "release", "incident", "learning"]
    chain = {"chain_id": "PASV2-CHAIN-SENTINEL-A", "source_document": "source-1-five-dimension-risk-catalogue", "source_item": "4.1.21 Serialization Failure", "normalized_runtime_record": "semantic-review-ledger.jsonl::4.1.21", "risk_definition": stable_id("RDEF-", "Serialization Failure") + "@1.1.0", "risk_assessment": "concern-runtime-evidence.json::RAS-001", "control": "FS-004", "requirement": "MP-REQ-semantic-normalization-sentinel-a", "task_packet": "PASV2 bounded remediation task", "implementation": "PREOS/scripts/semantic-risk-validator.py", "test": "PREOS/tests/test_pasv2_bounded_remediation.py::test_semantic_sentinels_are_corrected_without_raw_overwrite", "evidence": "semantic-review-ledger.jsonl::SRV-S1-0021", "gate": "PREOS_MODEL2_CROSSWALK_APPROVAL remains HUMAN_REVIEW", "release": "NOT_APPLICABLE", "incident": "NOT_APPLICABLE", "learning": "PASV2 independent audit finding AUD-023", "applicability": {"release": "NOT_APPLICABLE", "incident": "NOT_APPLICABLE"}, "links": [{"from": a, "to": b} for a, b in zip(nodes, nodes[1:])]}
    write_json(output_dir / "pasv2-traceability-chain.json", {"schema_version": "pasv2-traceability-chain-v1", "chains": [chain]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--units", default=str(UNITS))
    parser.add_argument("--output-dir", default=str(READINESS))
    parser.add_argument("--traceability-output-dir", default=str(TRACEABILITY))
    parser.add_argument("--skip-traceability", action="store_true")
    args = parser.parse_args()
    print(json.dumps({"source2_readiness_units": build_readiness(Path(args.units), Path(args.output_dir))}, indent=2))
    if not args.skip_traceability:
        build_traceability(Path(args.traceability_output_dir))
