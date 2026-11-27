#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import re
import shutil
from canonical_sources import source_bytes, SOURCES
from four_source_audit import docx_paragraphs

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
READINESS = ROOT / "references" / "readiness"
TRACEABILITY = ROOT / "references" / "traceability"
UNITS = ROOT / "references" / "source-units" / "PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl"

POLICIES = [
    ("SOURCE2-CREDENTIAL-AI-PROMPT", ("credential", "secret", "prompt", "ai generated", "coding prompt", "source code", "iac", "configuration"), "references/core/security.md", ["G3", "G8", "G11"], ["FS-075"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-AUTHZ-TENANT", ("authorisation", "authorization", "authentication", "privileged", "tenant", "account takeover", "cross tenant"), "references/core/security.md", ["G3", "G11"], ["FS-074", "FS-075"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-DATA-FLOW-PRIVILEGE", ("personal data", "data flow", "privacy", "privilege", "security"), "references/core/privacy.md", ["G3", "G4", "G10", "G11"], ["FS-075"], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-DEPENDENCY-LICENSE", ("dependenc", "licen", "third party", "open source", "software bill", "unverified"), "references/core/architecture.md", ["G2", "G3", "G7", "G11"], ["FS-054", "FS-055", "FS-075"], "gstack-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-LEGAL-REGULATORY", ("law", "legal", "regulat", "contractual", "compliance", "lawful", "industry obligation"), "references/core/human-approval-gates.md", ["G10", "G11"], [], "gstack-cso", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-PAYMENT-BILLING", ("payment", "billing", "money", "financial"), "references/core/data-architecture.md", ["G4", "G5", "G11"], ["FS-012", "FS-027", "FS-028"], "gstack-plan-eng-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-BACKUP-RESTORE", ("backup", "restore", "restoration", "rollback", "incident", "continuity", "monitoring", "support"), "references/core/incident-response.md", ["G7", "G9", "G11"], ["FS-061", "FS-066", "FS-072", "FS-073"], "gstack-qa", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-PERFORMANCE-CAPACITY", ("performance", "scalability", "capacity", "latency", "load"), "references/core/testing.md", ["G6", "G11"], ["FS-059", "FS-060", "FS-067", "FS-068"], "gstack-benchmark", "not_required_by_unit", "DETERMINISTIC_SEMANTIC_MAPPING"),
    ("SOURCE2-ACCESSIBILITY", ("accessibility", "usability", "user experience"), "references/core/accessibility.md", ["G10", "G11"], [], "gstack-design-review", "required", "DETERMINISTIC_SEMANTIC_MAPPING"),
]
EXISTING_KEYWORDS = {
    "api": "FS-001",
    "validation": "FS-004",
    "test": "FS-004",
    "security": "FS-075",
    "privacy": "FS-075",
    "incident": "FS-073",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


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
            "blueprint_artifact": "references/core/traceability.md" if "requirement" in lower else "references/core/testing.md",
            "preos_gates": ["G11"],
            "preos_control_ids": sorted(set(found)),
            "gstack_specialist_route": "gstack-qa" if classification in {"decision_gate", "required_evidence_item"} else "gstack-plan-eng-review",
            "human_approval_boundary": "required" if classification in {"decision_gate", "danger_item", "blocker_rule", "ownership_requirement"} else "not_required_by_unit",
            "implementation_status": "DETERMINISTIC_SEMANTIC_MAPPING",
            "mapping_status": "DETERMINISTIC_SEMANTIC_MAPPING",
            "review_status": "VALIDATED_BY_RULE",
            "evidence_requirements": ["deterministic readiness mapping and gate evidence"],
        }
    return {
        "policy_id": "SOURCE2-CONTEXTUAL-REQUIREMENT",
        "blueprint_artifact": "references/core/traceability.md",
        "preos_gates": ["G11"],
        "preos_control_ids": [],
        "gstack_specialist_route": "gstack-plan-eng-review",
        "human_approval_boundary": "required",
        "implementation_status": "DETERMINISTIC_SEMANTIC_MAPPING",
        "mapping_status": "DETERMINISTIC_SEMANTIC_MAPPING",
        "review_status": "VALIDATED_BY_RULE",
        "evidence_requirements": ["Preserved supplemental requirement; evaluate applicability and objective evidence in project context before G11. No equivalent baseline control is inferred."],
    }


def build_readiness(units_path: Path = UNITS, output_dir: Path = READINESS) -> int:
    canonical = READINESS / "source2-readiness-units.jsonl"
    target = output_dir / "source2-readiness-units.jsonl"
    units = [u for u in load_jsonl(units_path) if u["source_id"] == "source-2-readiness-framework"]
    paragraphs = docx_paragraphs(source_bytes('source-2'))
    if len(units)!=len(paragraphs): raise ValueError('Source 2 unit/paragraph mismatch')
    domains = load_json(READINESS / "domain-registry.json")["domains"]
    by_section = {int(d["source_section"]): d for d in domains}
    current = {"id": "RD-GLOBAL", "name": "Global readiness doctrine", "source_section": 0}
    mode = "context"
    rows = []
    for unit,text in zip(units,paragraphs,strict=True):
        match = re.fullmatch(r"(\d+)\.\s+(.+)", text)
        if match and int(match.group(1)) in by_section and match.group(2)==by_section[int(match.group(1))]['name']:
            current = by_section[int(match.group(1))]
            mode = "context"
        elif match and int(match.group(1))>=40:
            current = {"id":"RD-GLOBAL","name":"Global readiness doctrine","source_section":0}
            mode='context'
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
            "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "source_sha256": SOURCES['source-2'][1],
            "excerpt": text,
            "classification": primary,
            "secondary_classification": secondary,
            "readiness_domain_id": current["id"],
            "readiness_domain": current["name"],
            "target_repository": "PREOS",
            "target_artifacts": ["PREOS/references/readiness/source2-readiness-units.jsonl", "PREOS/references/readiness/r0-r17-gates.json", "PREOS/references/readiness/domain-registry.json"],
            "blueprint_lifecycle_stage": "release-readiness" if primary in {"decision_gate", "blocker_rule"} else "discovery-to-verification",
            "blueprint_profile": "production-readiness",
            "blueprint_artifact": policy["blueprint_artifact"],
            "supplemental_requirement_id": unit['semantic_unit_id'],
            "control_mapping_scope": "Supporting baseline controls only; the complete source requirement and its own evidence remain independently mandatory when applicable.",
            "preos_gates": policy["preos_gates"],
            "preos_risk_ids": ["model2-contextual-risk-selection"],
            "preos_control_ids": policy["preos_control_ids"],
            "evidence_requirements": ["Objective evidence addressing Source 2 unit "+unit['semantic_unit_id']+": "+text],
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
    from catalogue_traceability import generate, generate_sentinels
    output_dir.mkdir(parents=True,exist_ok=True)
    generate(output_dir/'pasv2-traceability-graph.jsonl')
    generate_sentinels(output_dir/'pasv2-traceability-chain.json')


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
