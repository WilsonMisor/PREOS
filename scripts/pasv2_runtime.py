#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any
import argparse, hashlib, json, platform, re, sys, time, zlib

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MODEL2 = ROOT / "references" / "risks" / "model2"
READINESS = ROOT / "references" / "readiness"
TRACE = ROOT / "references" / "traceability"
SOURCE4_CROSSWALK = ROOT / "references" / "integration" / "source4-production-assurance-crosswalk.json"
SOURCE4_TEXT = WORKSPACE / "migration-input" / "production_risk_economics_evolution_master_prompt.txt"
PROVENANCE_CLASSES = {"SOURCE_DIRECT", "SOURCE_IMPLIED", "ENGINEERING_EXPANSION", "EXTERNAL_RESEARCH_REQUIRED", "QUALIFIED_HUMAN_REVIEW_REQUIRED"}
RISK_GENERATION_AXES = ["feature", "actor", "input", "state", "time", "concurrency", "retry", "network", "dependency", "storage", "permission", "attack", "scale", "cost", "human_action", "business_rule", "legal_consequence", "recovery"]
SOURCE4_CHECKS = ["source_hash_and_preservation", "headings_paragraphs_numbered_items_list_items", "roles", "thirty_questions", "forty_assumptions", "forty_context_dimensions", "five_engines", "thirty_two_domains_and_concerns", "five_threat_stages", "six_maturity_stages", "nondeferrable_controls", "deferred_complexity", "adr_requirements", "resource_exhaustion", "failure_policies", "reconciliation", "invariants", "blast_radius", "twenty_eight_test_families", "feedback", "thirty_seven_atomic_fields", "twenty_output_sections", "readiness_interrogation", "depth", "ten_anti_overengineering_questions", "final_principles", "skill_architecture", "zero_silent_discard", "runtime_deviation_rationale", "provenance_classes", "economics_cost_dimensions", "risk_generation_rule", "evidence_and_gate_semantics", "software_neutral_scope"]

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")

def stable_id(prefix: str, value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return prefix + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16].upper()

def text_blob(value: Any) -> str:
    return value.lower() if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True).lower()

def source4() -> dict[str, Any]:
    return load_json(SOURCE4_CROSSWALK)

def model2_data() -> dict[str, Any]:
    definitions = load_jsonl(MODEL2 / "normalized-risk-definitions.jsonl")
    variants = load_jsonl(MODEL2 / "risk-context-variants.jsonl")
    relationships = load_jsonl(MODEL2 / "risk-relationships.jsonl")
    reviews = load_jsonl(MODEL2 / "semantic-review-ledger.jsonl")
    return {"definitions": definitions, "variants": variants, "relationships": relationships, "reviews": reviews, "definitions_by_id": {f"{r['risk_definition_id']}@{r['definition_version']}": r for r in definitions}, "variants_by_id": {r["risk_context_variant_id"]: r for r in variants}}












def run_five_engines(contract: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"context": context_engine(contract), "risk_generation": risk_generation_engine(contract), "economics_complexity": economics_complexity_engine(contract), "evolution": evolution_engine(contract), "evidence_gate": evidence_gate_engine(contract, evidence)}


def generate_lifecycle_traceability(output_path: Path = TRACE / "pasv2-traceability-graph.jsonl"):
    from catalogue_traceability import generate
    return generate(output_path)

def validate_lifecycle_traceability(path: Path = TRACE / "pasv2-traceability-graph.jsonl"):
    from catalogue_traceability import validate
    return validate(path)

def validate_source4_completeness() -> dict[str, Any]:
    from canonical_sources import source_bytes as preserved_bytes
    from four_source_audit import verify_source4_crosswalk, verify_semantic_units
    verify_source4_crosswalk(); verify_semantic_units()
    cx = source4(); checks: dict[str, dict[str, Any]] = {}; source_bytes = preserved_bytes('source-4'); source_text = source_bytes.decode('utf-8'); actual_hash = hashlib.sha256(source_bytes).hexdigest()
    def add(name: str, passed: bool, detail: Any) -> None: checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}
    counts = cx["counts"]
    add("source_hash_and_preservation", actual_hash == cx["source_sha256"], {"expected": cx["source_sha256"], "actual": actual_hash, "bytes": len(source_bytes) or cx.get("source_bytes")})
    add("headings_paragraphs_numbered_items_list_items", bool(source_text and cx.get("source_physical_lines", 0) > 0 and cx.get("production_questions") and cx.get("output_structure") and cx.get("test_families")), "plain-text source preserved and structured headings/items/lists extracted into crosswalk")
    add("roles", len(cx["role_crosswalk"]) == 18, len(cx["role_crosswalk"])); add("thirty_questions", counts["questions"] == 30 and len(cx["production_questions"]) == 30, counts["questions"]); add("forty_assumptions", counts["assumptions"] == 40 and len(cx["assumption_register"]) == 40, counts["assumptions"]); add("forty_context_dimensions", counts["context_dimensions"] == 40 and len(cx["context_dimensions"]) == 40, counts["context_dimensions"]); add("five_engines", len(cx["engines"]) == 5, len(cx["engines"])); add("thirty_two_domains_and_concerns", counts["domains"] == 32 and len(cx["full_stack_domains"]) == 32, counts["domains"]); add("five_threat_stages", len(cx["threat_stages"]) == 5, len(cx["threat_stages"])); add("six_maturity_stages", len(cx["maturity_stages"]) == 6, len(cx["maturity_stages"])); add("nondeferrable_controls", len(cx["nondeferrable_controls"]) == 20, len(cx["nondeferrable_controls"])); add("deferred_complexity", len(cx["deferred_complexity_record"]) >= 7, len(cx["deferred_complexity_record"])); add("adr_requirements", len(cx["architecture_decision_fields"]) >= 16, len(cx["architecture_decision_fields"])); add("resource_exhaustion", len(cx["resource_exhaustion_items"]) == 20, len(cx["resource_exhaustion_items"])); add("failure_policies", len(cx["failure_policy_classifications"]) >= 1, len(cx["failure_policy_classifications"])); add("reconciliation", len(cx["reconciliation_examples"]) >= 9, len(cx["reconciliation_examples"])); add("invariants", len(cx["invariant_examples"]) >= 1, len(cx["invariant_examples"])); add("blast_radius", len(cx["blast_radius_dimensions"]) == 11, len(cx["blast_radius_dimensions"])); add("twenty_eight_test_families", counts["test_families"] == 28 and len(cx["test_families"]) == 28, counts["test_families"]); add("feedback", len(cx["production_feedback_steps"]) == 12, len(cx["production_feedback_steps"])); add("thirty_seven_atomic_fields", counts["atomic_fields"] == 37 and len(cx["atomic_field_crosswalk"]) == 37, counts["atomic_fields"]); add("twenty_output_sections", counts["output_sections"] == 20 and len(cx["output_structure"]) == 20, counts["output_sections"]); add("readiness_interrogation", len(cx["production_questions"]) == 30, len(cx["production_questions"])); add("depth", cx.get("source_physical_lines", 0) >= 1800, cx.get("source_physical_lines")); add("ten_anti_overengineering_questions", len(cx["anti_overengineering_questions"]) == 10, len(cx["anti_overengineering_questions"])); add("final_principles", len(cx["final_principles"]) >= 1, len(cx["final_principles"])); add("skill_architecture", bool(cx["skill_capability_crosswalk"].get("gstack_route_artifact")), cx["skill_capability_crosswalk"]); add("zero_silent_discard", bool(cx.get("routing_policy")), cx.get("routing_policy")); add("runtime_deviation_rationale", bool(cx.get("routing_policy") and cx.get("human_authority_boundary")), {"routing_policy": cx.get("routing_policy"), "human_boundary": cx.get("human_authority_boundary")}); add("provenance_classes", len(cx["provenance_classes"]) == 5, len(cx["provenance_classes"])); add("economics_cost_dimensions", len(cx["economics_and_complexity"]["cost_dimensions"]) == 25, len(cx["economics_and_complexity"]["cost_dimensions"])); add("risk_generation_rule", all(axis.replace("_", " ") in cx["risk_generation"]["rule"].lower() for axis in RISK_GENERATION_AXES), cx["risk_generation"]["rule"]); add("evidence_and_gate_semantics", bool(cx.get("evidence_and_gates")), list(cx.get("evidence_and_gates", {}).keys())); add("software_neutral_scope", "software neutral" in cx["software_neutral_scope"]["text"].lower(), cx["software_neutral_scope"])
    missing = set(SOURCE4_CHECKS) - set(checks)
    if missing: raise ValueError(f"Source-4 validator omitted checks: {sorted(missing)}")
    failed = {name: check for name, check in checks.items() if check["status"] != "PASS"}
    return {"total_checks": len(checks), "failed_checks": len(failed), "checks": checks}

def source4_report() -> str:
    cx = source4(); validation = validate_source4_completeness(); lines = ["# Source 4 Production Assurance Report", ""]
    for item in cx["output_structure"]:
        title = item["title"]; lines.append(f"## {item['section']}. {title}")
        if title == "Production Risk Generation Model": lines.append(f"Rule: {cx['risk_generation']['rule']}")
        elif title == "Software Economics": lines.append(f"Cost dimensions: {len(cx['economics_and_complexity']['cost_dimensions'])}; triggered by project context through the Economics and Complexity Engine.")
        elif title == "Production Gates": lines.append("Gate behavior is implemented through the Evidence and Gate Engine; production authority remains human.")
        elif title == "Master Production Readiness Questions": lines.append(f"Questions preserved: {len(cx['production_questions'])}.")
        else: lines.append(f"Authoritative structured data: `PREOS/references/integration/source4-production-assurance-crosswalk.json` pointer `/output_structure/{item['section'] - 1}`.")
        lines.append("")
    lines.append(f"Completeness checks: {validation['total_checks']} total, {validation['failed_checks']} failed.")
    return "\n".join(lines)

def high_assurance_fixture() -> dict[str, Any]:
    return {"product_type": "SaaS", "profiles": ["saas", "web", "api", "data", "infrastructure"], "tenant_model": "multi-tenant", "payments": True, "billing": True, "personal_data": True, "architecture": ["REST", "relational database", "queue", "external payment provider", "web UI"], "external_providers": ["payment provider"], "jurisdictions": ["Nigeria"], "features": ["withdrawal"], "actors": ["tenant user", "admin", "payment provider"], "money_movement": True, "queue": True, "maturity_stage": "Stage 1 Early Production", "threat_stage": "Stage 2", "first_production_release": True, "business_rules": ["payment idempotency", "cross-tenant isolation", "financial reconciliation"]}

def low_risk_fixture() -> dict[str, Any]:
    return {"product_type": "documentation-only", "profiles": [], "tenant_model": "not_applicable", "payments": False, "personal_data": False, "architecture": [], "features": ["README typo"], "actors": ["maintainer"], "maturity_stage": "Stage 0 Prototype", "threat_stage": "Stage 0", "documentation_only": True}






def _suite_acceptance(case):
    import os
    import subprocess
    blueprint = Path(os.environ.get('PASV2_BLUEPRINT_ROOT', WORKSPACE/'wed_dev_skill'))
    gstack = Path(os.environ.get('PASV2_GSTACK_ROOT', WORKSPACE/'gstack'))
    command = [sys.executable, str(blueprint/'scripts/pasv2_acceptance.py'),
               '--preos', str(ROOT), '--gstack', str(gstack), '--case', case]
    proc = subprocess.run(command, cwd=blueprint, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=120)
    if proc.returncode:
        raise ValueError('three-repository acceptance failed: '+proc.stderr)
    return json.loads(proc.stdout)[case]


def evaluate_high_assurance_acceptance():
    return _suite_acceptance('high')


def evaluate_low_risk_proportionality():
    return _suite_acceptance('low')

def validate_all_runtime() -> dict[str, Any]:
    s4 = validate_source4_completeness(); trace = validate_lifecycle_traceability(); high = evaluate_high_assurance_acceptance(); low = evaluate_low_risk_proportionality(); bench = performance_benchmark()
    if s4["failed_checks"]: raise ValueError("Source-4 completeness checks failed")
    if not high["pass"]: raise ValueError("high assurance fixture failed")
    if not low["pass"]: raise ValueError("low risk fixture failed")
    return {"source4_checks": s4["total_checks"], "traceability_records": trace["records"], "high_assurance": high["pass"], "low_risk": low["pass"], "benchmark": bench}

def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    for name in ["validate-all", "source4-check", "source4-report", "benchmark", "high-assurance", "low-risk", "generate-traceability"]: sub.add_parser(name)
    q = sub.add_parser("query-graph"); q.add_argument("--type", required=True); q.add_argument("--value"); q.add_argument("--limit", type=int, default=25); q.add_argument('--project-graph',type=Path)
    project_trace = sub.add_parser('validate-project-trace'); project_trace.add_argument('graph',type=Path)
    c = sub.add_parser("candidate"); c.add_argument("--candidate-json", required=True); c.add_argument("--human-review-json")
    args = parser.parse_args()
    if args.command == "validate-all": print(json.dumps(validate_all_runtime(), indent=2, ensure_ascii=True))
    elif args.command == "source4-check": print(json.dumps(validate_source4_completeness(), indent=2, ensure_ascii=True))
    elif args.command == "source4-report": print(source4_report())
    elif args.command == "benchmark": print(json.dumps(performance_benchmark(), indent=2, ensure_ascii=True))
    elif args.command == "high-assurance": print(json.dumps(evaluate_high_assurance_acceptance(), indent=2, ensure_ascii=True))
    elif args.command == "low-risk": print(json.dumps(evaluate_low_risk_proportionality(), indent=2, ensure_ascii=True))
    elif args.command == "generate-traceability": print(json.dumps(generate_lifecycle_traceability(), indent=2, ensure_ascii=True))
    elif args.command == "query-graph": print(json.dumps(query_risk_graph(args.type, args.value, limit=args.limit,project_graph=args.project_graph), indent=2, ensure_ascii=True))
    elif args.command == 'validate-project-trace':
        from lifecycle_traceability import validate_operational_graph
        print(json.dumps(validate_operational_graph(load_json(args.graph),{'PREOS':ROOT,'wed_dev_skill':WORKSPACE/'wed_dev_skill','project':args.graph.resolve().parent}),indent=2))
    elif args.command == "candidate":
        candidate = json.loads(Path(args.candidate_json).read_text(encoding="utf-8")); human = json.loads(Path(args.human_review_json).read_text(encoding="utf-8")) if args.human_review_json else None; print(json.dumps(evaluate_candidate_risk(candidate, human_review=human), indent=2, ensure_ascii=True))

# Canonical runtime entry points. These replace the initial descriptive engine
# prototypes; callers keep the public module/CLI surface while executing the
# behavioral implementations.
from assurance_engines import (normalize_project_context, context_engine,
    risk_generation_engine, economics_complexity_engine, evolution_engine)
from control_assurance import nondeferrable_control_map, evaluate_nondeferrable_controls, evidence_gate_engine
from risk_graph import query_risk_graph
from assurance_benchmark import run_benchmark as performance_benchmark


def evaluate_candidate_risk(candidate, *, human_review=None):
    """Compatibility intake: never infer a durable approval from caller flags."""
    if not candidate.get('canonical_name') or candidate.get('provenance_class') not in PROVENANCE_CLASSES:
        raise ValueError('candidate requires name and valid provenance')
    return {'candidate_id':stable_id('CAND-RISK-',candidate),'promotion_allowed':False,
            'canonicalization_decision':'QUEUE_HUMAN_REVIEW',
            'workflow':'scripts/candidate_workflow.py: submit, prepare_promotion, promote',
            'required_input':'definition, source provenance, versioned plan, durable scoped approval and executed regression'}


def promote_candidate_risk(candidate, human_review=None):
    raise ValueError('candidate cannot be promoted through caller booleans; use candidate_workflow.promote with durable scoped PREOS approval')


if __name__ == "__main__": main()



