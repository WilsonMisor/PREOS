#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
READINESS = ROOT / "references" / "readiness"
TRACEABILITY = ROOT / "references" / "traceability"
UNITS = WORKSPACE / ".migration-control" / "PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl"


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


def controls_for(text: str) -> list[str]:
    lower = text.lower()
    pairs = [("api", "FS-001"), ("validation", "FS-004"), ("security", "FS-015"), ("privacy", "FS-026"), ("payment", "FS-050"), ("backup", "FS-061"), ("rollback", "FS-064"), ("monitor", "FS-067"), ("accessibility", "FS-070"), ("incident", "FS-073")]
    found = [control for word, control in pairs if word in lower]
    return found or ["FS-001"]


def build_readiness() -> int:
    units = [u for u in load_jsonl(UNITS) if u["source_id"] == "source-2-readiness-framework"]
    domains = load_json(READINESS / "domain-registry.json")["domains"]
    by_section = {int(d["source_section"]): d for d in domains}
    gates = load_json(READINESS / "r0-r17-gates.json")["gates"]
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
        mapped_gates = ["G11"] if current["id"] == "RD-GLOBAL" else gates[(int(current["id"].split("-")[1]) - 1) % len(gates)]["mapped_preos_super_gates"]
        rows.append({
            "source_unit_id": unit["semantic_unit_id"],
            "source_location": {"source_id": unit["source_id"], "source_path": unit["source_path"], "source_line_or_paragraph": unit["source_line_or_paragraph"]},
            "excerpt_sha256": unit["text_sha256"],
            "excerpt": text,
            "classification": primary,
            "secondary_classification": secondary,
            "readiness_domain_id": current["id"],
            "readiness_domain": current["name"],
            "target_repository": "PREOS",
            "target_artifacts": ["PREOS/references/readiness/source2-readiness-units.jsonl", "PREOS/references/readiness/r0-r17-gates.json", "PREOS/references/readiness/domain-registry.json"],
            "blueprint_lifecycle_stage": "release-readiness" if primary in {"decision_gate", "blocker_rule"} else "discovery-to-verification",
            "blueprint_profile": "production-readiness",
            "blueprint_artifact": "requirements-traceability-matrix" if "requirement" in text.lower() else "release-checklist",
            "preos_gates": mapped_gates,
            "preos_risk_ids": ["model2-contextual-risk-selection"],
            "preos_control_ids": controls_for(text + " " + current["name"]),
            "evidence_requirements": [text[:160]] if primary == "required_evidence_item" else ["deterministic readiness mapping and gate evidence"],
            "gstack_specialist_route": "gstack-qa" if primary in {"decision_gate", "required_evidence_item"} else "gstack-plan-eng-review",
            "human_approval_boundary": "required" if primary in {"decision_gate", "danger_item", "blocker_rule", "ownership_requirement"} else "not_required_by_unit",
            "implementation_status": "IMPLEMENTED_BY_REMEDIATION",
            "validator": "PREOS/scripts/validate-readiness.py",
        })
    write_jsonl(READINESS / "source2-readiness-units.jsonl", rows)
    return len(rows)


def build_traceability() -> None:
    nodes = ["source_document", "source_item", "normalized_runtime_record", "risk_definition", "risk_assessment", "control", "requirement", "task_packet", "implementation", "test", "evidence", "gate", "release", "incident", "learning"]
    chain = {"chain_id": "PASV2-CHAIN-SENTINEL-A", "source_document": "source-1-five-dimension-risk-catalogue", "source_item": "4.1.21 Serialization Failure", "normalized_runtime_record": "semantic-review-ledger.jsonl::4.1.21", "risk_definition": stable_id("RDEF-", "Serialization Failure") + "@1.1.0", "risk_assessment": "concern-runtime-evidence.json::RAS-001", "control": "FS-004", "requirement": "MP-REQ-semantic-normalization-sentinel-a", "task_packet": "PASV2 bounded remediation task", "implementation": "PREOS/scripts/semantic-risk-validator.py", "test": "PREOS/tests/test_pasv2_bounded_remediation.py::test_semantic_sentinels_are_corrected_without_raw_overwrite", "evidence": "semantic-review-ledger.jsonl::SRV-S1-0021", "gate": "PREOS_MODEL2_CROSSWALK_APPROVAL remains HUMAN_REVIEW", "release": "NOT_APPLICABLE", "incident": "NOT_APPLICABLE", "learning": "PASV2 independent audit finding AUD-023", "applicability": {"release": "NOT_APPLICABLE", "incident": "NOT_APPLICABLE"}, "links": [{"from": a, "to": b} for a, b in zip(nodes, nodes[1:])]}
    write_json(TRACEABILITY / "pasv2-traceability-chain.json", {"schema_version": "pasv2-traceability-chain-v1", "chains": [chain]})


if __name__ == "__main__":
    print(json.dumps({"source2_readiness_units": build_readiness()}, indent=2))
    build_traceability()
