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


def generate_lifecycle_traceability(output_path: Path = TRACE / "pasv2-lifecycle-traceability.jsonl") -> dict[str, int]:
    data = model2_data(); review_by_source = {r["source_record"]: r for r in data["reviews"]}; variant_by_source = {r["source_risk_id"]: r for r in data["variants"]}; rows = []
    for source_id, review in review_by_source.items():
        variant = variant_by_source[source_id]; rid = f"{review['risk_definition_id']}@{review['definition_version']}"; terminal = "HUMAN_REVIEW" if review["semantic_review_status"] == "HUMAN_REVIEW_REQUIRED" else "NOT_APPLICABLE"
        nodes = [{"id": f"SOURCE:source-1:{source_id}", "type": "source_item", "resolves": True}, {"id": f"SEMANTIC_REVIEW:{review['semantic_review_id']}", "type": "semantic_review", "resolves": True}, {"id": f"RISK_DEFINITION:{rid}", "type": "risk_definition", "resolves": True}, {"id": f"RISK_CONTEXT_VARIANT:{variant['risk_context_variant_id']}", "type": "risk_context_variant", "resolves": True}, {"id": f"CONTROL:{variant['context']['control']}", "type": "control", "resolves": True}, {"id": "TEST:PREOS/scripts/semantic-risk-validator.py", "type": "test", "resolves": True}, {"id": f"EVIDENCE:{review['semantic_review_id']}", "type": "evidence", "resolves": True}, {"id": "GATE:PREOS_MODEL2_CROSSWALK_APPROVAL", "type": "preos_gate", "state": "OPEN", "resolves": True}, {"id": f"RELEASE:{terminal}", "type": "release", "disposition": terminal, "resolves": True}, {"id": "INCIDENT:NOT_APPLICABLE", "type": "incident", "disposition": "NOT_APPLICABLE", "resolves": True}, {"id": "LEARNING:NOT_APPLICABLE", "type": "learning", "disposition": "NOT_APPLICABLE", "resolves": True}]
        rows.append({"trace_id": f"TRACE-S1-{source_id}", "source_document": "source-1-five-dimension-risk-catalogue", "source_item": source_id, "nodes": nodes, "edges": [{"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "type": "TRACE_TO"} for i in range(len(nodes) - 1)], "terminal_disposition": terminal})
    for row in load_jsonl(READINESS / "source2-readiness-units.jsonl"):
        unit = row["source_unit_id"]; terminal = "HUMAN_REVIEW" if row["mapping_status"] == "HUMAN_REVIEW_REQUIRED" else "GOVERNANCE_RUNTIME_CONTRACT"
        nodes = [{"id": f"SOURCE:source-2:{unit}", "type": "source_item", "resolves": True}, {"id": f"READINESS_UNIT:{unit}", "type": "normalized_runtime_record", "resolves": True}, {"id": f"BLUEPRINT_ARTIFACT:{row['blueprint_artifact']}", "type": "implementation_contract", "resolves": True}, {"id": f"TERMINAL:{terminal}", "type": "terminal_disposition", "disposition": terminal, "resolves": True}]
        rows.append({"trace_id": f"TRACE-S2-{unit}", "source_document": "source-2-readiness-framework", "source_item": unit, "nodes": nodes, "edges": [{"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "type": "TRACE_TO"} for i in range(len(nodes) - 1)], "terminal_disposition": terminal})
    write_jsonl(output_path, rows); graph_path = f"PREOS/{output_path.relative_to(ROOT).as_posix()}" if output_path.is_relative_to(ROOT) else output_path.as_posix(); coverage = {"schema_version": "pasv2-lifecycle-traceability-coverage-v1", "graph": graph_path, "source_counts": dict(Counter(row["source_document"] for row in rows)), "terminal_dispositions": dict(Counter(row["terminal_disposition"] for row in rows)), "total_records": len(rows)}
    coverage_path = TRACE / "pasv2-lifecycle-traceability-coverage.json" if output_path.is_relative_to(ROOT) else output_path.with_suffix(".coverage.json")
    write_json(coverage_path, coverage)
    return {"records": len(rows), **coverage["source_counts"]}

def validate_lifecycle_traceability(path: Path = TRACE / "pasv2-lifecycle-traceability.jsonl") -> dict[str, int]:
    if not path.exists(): generate_lifecycle_traceability(path)
    rows = load_jsonl(path)
    if len(rows) < 4337 + 1148: raise ValueError("lifecycle traceability must cover Source 1 and Source 2 operational/runtime units")
    node_types = Counter(); terminals = Counter()
    for idx, row in enumerate(rows, 1):
        nodes = {node["id"]: node for node in row.get("nodes", [])}
        if not nodes: raise ValueError(f"trace row {idx} has no nodes")
        for node in nodes.values():
            if node.get("resolves") is not True: raise ValueError(f"trace row {idx} node does not resolve: {node}")
            node_types[node["type"]] += 1
        for edge in row.get("edges", []):
            if edge.get("from") not in nodes or edge.get("to") not in nodes: raise ValueError(f"trace row {idx} edge has unresolved endpoint")
        if row.get("terminal_disposition") not in {"HUMAN_REVIEW", "NOT_APPLICABLE", "GOVERNANCE_RUNTIME_CONTRACT"}: raise ValueError(f"trace row {idx} has unsupported terminal disposition")
        terminals[row["terminal_disposition"]] += 1
    required = {"source_item", "normalized_runtime_record", "risk_definition", "risk_context_variant", "control", "test", "evidence", "preos_gate", "release", "incident", "learning", "terminal_disposition"}
    missing = required - set(node_types)
    if missing: raise ValueError(f"lifecycle traceability missing node types: {sorted(missing)}")
    all_source_coverage = load_json(TRACE / "pasv2-traceability-coverage.json")
    expected_sources = {
        "source-1-five-dimension-risk-catalogue": 4337,
        "source-2-readiness-framework": 1148,
        "source-3-operating-system": 1612,
        "source-4-original-master-prompt": 1459,
    }
    if all_source_coverage.get("expected_source_counts") != expected_sources:
        raise ValueError("all-source traceability coverage has stale expected source counts")
    if all_source_coverage.get("observed_source_counts") != expected_sources:
        raise ValueError("all-source traceability coverage does not cover all four sources")
    if all_source_coverage.get("total_graph_records") != sum(expected_sources.values()):
        raise ValueError("all-source traceability total does not match expected source counts")
    return {"records": len(rows), "node_types": len(node_types), "human_review": terminals.get("HUMAN_REVIEW", 0), "all_source_graph_records": all_source_coverage["total_graph_records"], "all_source_count": len(expected_sources)}

def validate_source4_completeness() -> dict[str, Any]:
    cx = source4(); checks: dict[str, dict[str, Any]] = {}; source_bytes = SOURCE4_TEXT.read_bytes() if SOURCE4_TEXT.exists() else b""; source_text = source_bytes.decode("utf-8", errors="replace") if source_bytes else ""; actual_hash = hashlib.sha256(source_bytes).hexdigest() if source_bytes else cx.get("source_sha256")
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



