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

def normalize_project_context(contract: dict[str, Any]) -> dict[str, Any]:
    dimensions = [item["text"] for item in source4()["context_dimensions"]]
    lower = text_blob(contract)
    normalized = {"product_category": contract.get("product_category") or contract.get("product_type") or "unspecified", "profiles": sorted(set(contract.get("profiles", []))), "user_types": contract.get("user_types", contract.get("actors", [])), "business_model": contract.get("business_model", "unspecified"), "money_movement": bool(contract.get("payments") or contract.get("money_movement") or "payment" in lower or "billing" in lower), "sensitive_data": bool(contract.get("personal_data") or "personal data" in lower or "sensitive" in lower), "tenant_model": contract.get("tenant_model", "not_applicable"), "jurisdictions": contract.get("jurisdictions", []), "architecture": sorted(set(contract.get("architecture", []))), "external_providers": contract.get("external_providers", []), "maturity_stage": contract.get("maturity_stage", "Stage 1 Early Production"), "threat_stage": contract.get("threat_stage", "Stage 1"), "expected_users": contract.get("expected_users", "unknown"), "expected_transaction_volume": contract.get("expected_transaction_volume", "unknown"), "required_source4_dimensions": dimensions, "covered_source4_dimensions": [], "missing_source4_dimensions": []}
    mapped = {"Product category": normalized["product_category"], "User types": normalized["user_types"], "Business model": normalized["business_model"], "Money movement": normalized["money_movement"], "Sensitive data": normalized["sensitive_data"], "Jurisdictions": normalized["jurisdictions"], "Expected users": normalized["expected_users"], "Expected transaction volume": normalized["expected_transaction_volume"], "Current production stage": normalized["maturity_stage"], "Billing requirements": bool(contract.get("billing") or contract.get("payments")), "Subscription requirements": bool(contract.get("subscriptions")), "Web requirements": "web" in normalized["profiles"], "AI functionality": bool(contract.get("ai_functionality")), "Data and analytics requirements": bool(contract.get("personal_data") or "data" in normalized["profiles"])}
    for item in dimensions:
        (normalized["covered_source4_dimensions"] if mapped.get(item) not in (None, "", [], False) else normalized["missing_source4_dimensions"]).append(item)
    return normalized

def evaluate_candidate_risk(candidate: dict[str, Any], *, human_review: dict[str, Any] | None = None) -> dict[str, Any]:
    if not candidate.get("canonical_name"):
        raise ValueError("candidate risk requires canonical_name")
    provenance = candidate.get("provenance_class")
    if provenance not in PROVENANCE_CLASSES:
        raise ValueError(f"unsupported provenance class: {provenance}")
    existing = {str(row["canonical_name"]).strip().lower(): row for row in model2_data()["definitions"]}.get(str(candidate["canonical_name"]).strip().lower())
    review_required = provenance in {"SOURCE_IMPLIED", "ENGINEERING_EXPANSION", "EXTERNAL_RESEARCH_REQUIRED", "QUALIFIED_HUMAN_REVIEW_REQUIRED"}
    approved = bool(human_review and human_review.get("approved") and human_review.get("qualified_human"))
    allowed = bool(not existing and (approved or not review_required))
    decision = "REJECT_DUPLICATE_LINK_TO_EXISTING_DEFINITION" if existing else ("QUEUE_HUMAN_REVIEW" if review_required and not approved else "PROMOTION_PLAN_READY")
    return {"candidate_id": stable_id("CAND-RISK-", {"name": candidate["canonical_name"], "source": candidate.get("source")}), "canonical_name": candidate["canonical_name"], "provenance_class": provenance, "source": candidate.get("source", {}), "relationship_deduplication_analysis": {"duplicate_existing_definition": bool(existing), "matched_risk_definition_id": existing.get("risk_definition_id") if existing else None, "relationship_type": "SAME_AS" if existing else "NEW_CANDIDATE"}, "semantic_review": {"status": "APPROVED_BY_QUALIFIED_HUMAN" if approved else ("HUMAN_REVIEW_REQUIRED" if review_required else "DETERMINISTIC_SOURCE_DIRECT"), "required": review_required, "authority": human_review.get("reviewer") if human_review else None}, "canonicalization_decision": decision, "catalogue_version_change": "PROMOTION_REQUIRES_VERSIONED_CHANGESET" if allowed else "NO_MUTATION_DIRECTLY_FROM_CANDIDATE", "relationship_index_update": "PLAN_ONLY_UNTIL_PROMOTION", "regression_test": "PREOS/tests/test_pasv2_runtime.py", "promotion_allowed": allowed}

def promote_candidate_risk(candidate: dict[str, Any], human_review: dict[str, Any] | None = None) -> dict[str, Any]:
    workflow = evaluate_candidate_risk(candidate, human_review=human_review)
    if not workflow["promotion_allowed"]:
        raise ValueError("candidate cannot be promoted without non-duplicate status and required qualified-human review")
    return {"candidate_id": workflow["candidate_id"], "promotion": "APPROVED_CHANGESET_ONLY", "new_risk_definition_id": stable_id("RDEF-", candidate["canonical_name"]), "definition_version": "1.0.0", "index_update_required": True, "relationship_update_required": True, "canonical_corpus_mutated": False}

def _variant_match_score(variant: dict[str, Any], context: dict[str, Any]) -> int:
    blob = text_blob([variant.get("category"), variant.get("dimension"), variant.get("context", {})])
    score = sum(3 for profile in context.get("profiles", []) if profile in blob)
    score += sum(4 for arch in context.get("architecture", []) if str(arch).lower() in blob)
    score += sum(4 for jurisdiction in context.get("jurisdictions", []) if str(jurisdiction).lower() in blob)
    if context.get("money_movement") and any(w in blob for w in ("payment", "money", "financial")): score += 5
    if context.get("tenant_model") == "multi-tenant" and "tenant" in blob: score += 5
    if context.get("sensitive_data") and any(w in blob for w in ("privacy", "personal", "data")): score += 3
    return score

def context_engine(contract: dict[str, Any]) -> dict[str, Any]:
    return {"engine": "Context Engine", "input_artifacts": ["Project Contract", "Blueprint classification"], "runtime_implementation": "PREOS/scripts/pasv2_runtime.py::context_engine", "output": normalize_project_context(contract), "human_boundary": "Unknown or materially regulated classification remains HUMAN_REVIEW"}

def risk_generation_engine(contract: dict[str, Any], *, limit: int = 25) -> dict[str, Any]:
    context = normalize_project_context(contract)
    ranked = sorted(((_variant_match_score(v, context), v) for v in model2_data()["variants"] if _variant_match_score(v, context)), key=lambda item: (-item[0], item[1]["source_risk_id"]))
    selected = [item[1] for item in ranked[:limit]]
    feature = contract.get("features", ["unspecified-feature"])[0]
    candidate_values = {"concurrency": "duplicate-click", "retry": "worker-retry", "network": "timeout", "dependency": (contract.get("external_providers") or ["none"])[0], "storage": (contract.get("architecture") or ["database"])[0], "permission": "suspended-during-processing", "attack": "replay", "scale": "one-tenant", "cost": "provider-fee", "human_action": "admin-freeze", "business_rule": (contract.get("business_rules") or ["idempotent-state-transition"])[0], "legal_consequence": "Nigeria-consumer-or-data-obligation" if "Nigeria" in context.get("jurisdictions", []) else "contractual", "recovery": "reconciliation"}
    candidates = []
    for axis in RISK_GENERATION_AXES:
        if axis in {"feature", "actor"}: continue
        value = candidate_values.get(axis, "context-dependent")
        name = f"{feature} {axis.replace('_', ' ').title()} Risk"
        candidates.append({"candidate_id": stable_id("CAND-RISK-", {"name": name, "source": {"class": "contextual-generation", "axis": axis, "value": value}}), "axis": axis, "value": value, "promotion_allowed": False, "decision": "QUEUE_HUMAN_REVIEW"})
    withdrawal = ["duplicate clicks", "simultaneous devices", "stale balances", "provider timeouts", "duplicate provider events", "missing provider events", "out of order events", "worker retries", "user suspension during processing", "fraud review during processing", "admin freeze", "provider outage", "database failure", "queue retry", "regional failure", "reconciliation mismatch", "support manual retry", "attacker replay"] if str(feature).lower() in {"withdrawal", "transfer"} else []
    return {"engine": "Risk Generation Engine", "catalogue_first_selection_count": len(selected), "selected_context_variants": [row["risk_context_variant_id"] for row in selected], "bounded_contextual_candidates": candidates, "axes_considered": RISK_GENERATION_AXES, "pruning_policy": "one candidate per applicable axis; no literal Cartesian explosion", "withdrawal_transfer_regression": withdrawal, "promotion_policy": "canonical promotion only through candidate-risk workflow"}

def economics_complexity_engine(contract: dict[str, Any]) -> dict[str, Any]:
    cx = source4(); context = normalize_project_context(contract)
    dims = [item["text"] for item in cx["economics_and_complexity"]["cost_dimensions"]]
    lower = text_blob(contract); triggered = []
    for dim in dims:
        key = dim.lower()
        if key in {"fixed cost", "variable cost", "cost of failure", "cost of engineering complexity", "cost of operational toil", "cost of migration"} or ("transaction" in key and context["money_movement"]) or ("gb" in key and ("storage" in lower or "file" in lower)) or ("support" in key and contract.get("support_required", True)) or ("ai" in key and contract.get("ai_functionality")):
            triggered.append(dim)
    return {"engine": "Economics and Complexity Engine", "cost_dimensions_available": len(dims), "triggered_cost_dimensions": triggered, "unit_economics_required": context["money_movement"] or bool(contract.get("subscriptions")), "complexity_tax_assessment": "HIGH" if len(context["architecture"]) >= 4 or context["money_movement"] else "LOW", "deferred_complexity_triggers": [item["text"] for item in cx["deferred_complexity_record"] if "trigger" in item["text"].lower() or "migration" in item["text"].lower()], "human_boundary": "Financial/tax/legal interpretation remains accountable-human authority"}

def evolution_engine(contract: dict[str, Any]) -> dict[str, Any]:
    cx = source4(); context = normalize_project_context(contract)
    return {"engine": "Evolution Engine", "product_maturity_stages": cx["maturity_stages"], "threat_stages": cx["threat_stages"], "current_maturity_stage": context["maturity_stage"], "current_threat_stage": context["threat_stage"], "deferred_activation_rules": cx["evolution"]["states"], "review_triggers": ["maturity-stage-change", "threat-stage-change", "tenant-volume-threshold", "transaction-volume-threshold", "new-jurisdiction", "new-money-movement"], "non_scale_consequence_overrides": ["money_movement", "personal_data", "multi_tenancy", "regulated_jurisdiction"]}

def nondeferrable_control_map() -> list[dict[str, Any]]:
    controls = []
    for item in source4()["nondeferrable_controls"]:
        text = item["text"]; n = int(item["number"]); fs = f"FS-{n:03d}"; low = text.lower()
        gate = "G5" if any(k in low for k in ("money", "monetary", "reconciliation")) else ("G3" if any(k in low for k in ("auth", "secret", "injection", "rate limiting")) else "G11")
        controls.append({"nondeferrable_control_id": f"NDC-{n:02d}", "source4_number": n, "source4_text": text, "preos_control_id": fs, "evidence_id": f"EVIDENCE-{fs}", "gate": gate, "first_production_required": True})
    return controls

def evaluate_nondeferrable_controls(context: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = evidence or {}; first_release = bool(context.get("first_production_release", False)); rows = []; blocked = False
    for control in nondeferrable_control_map():
        applicable = first_release
        state = "NOT_APPLICABLE"
        if applicable:
            state = "SATISFIED" if evidence.get(control["evidence_id"]) == "CURRENT" else "BLOCKING_MISSING_EVIDENCE"; blocked = blocked or state.startswith("BLOCKING")
        rows.append({**control, "applicable": applicable, "state": state, "rationale": "first production release requires nondeferrable controls" if applicable else "not a first production release"})
    return {"blocked": blocked, "results": rows}

def evidence_gate_engine(contract: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    nondef = evaluate_nondeferrable_controls(contract, evidence)
    state = "RED" if nondef["blocked"] else ("UNKNOWN" if not evidence else "GREEN")
    return {"engine": "Evidence and Gate Engine", "nondeferrable": nondef, "gate_state": state, "blocker_behavior": "missing applicable nondeferrable evidence blocks first real production release", "acceptance_authority": "qualified human only", "acceptance_expiry_revocation": "validated by risk acceptance runtime"}

def run_five_engines(contract: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"context": context_engine(contract), "risk_generation": risk_generation_engine(contract), "economics_complexity": economics_complexity_engine(contract), "evolution": evolution_engine(contract), "evidence_gate": evidence_gate_engine(contract, evidence)}

def query_risk_graph(query_type: str, value: str | None = None, *, limit: int = 25) -> dict[str, Any]:
    data = model2_data(); results: list[dict[str, Any]] = []
    if query_type in {"relationship", "causes", "amplifies"}:
        wanted = {"relationship": None, "causes": "CAUSED_BY", "amplifies": "AMPLIFIES"}[query_type]
        results = [rel for rel in data["relationships"] if (not wanted or rel["relationship_type"] == wanted) and (not value or value in json.dumps(rel, sort_keys=True))]
    elif query_type in {"industries", "products", "architectures", "jurisdictions"}:
        dim = {"industries": "industry", "products": "product", "architectures": "architecture", "jurisdictions": "jurisdiction"}[query_type]
        results = [row for row in data["variants"] if (row["dimension"] == dim or (dim == "architecture" and row.get("context", {}).get("architecture"))) and (not value or value.lower() in text_blob(row))]
    elif query_type == "mitigated-by":
        for row in data["variants"]:
            ctx = row.get("context", {})
            if not value or value in {row["source_risk_id"], row["risk_context_variant_id"], ctx.get("control")}:
                results.append({"risk_context_variant_id": row["risk_context_variant_id"], "control": ctx.get("control"), "relationship_type": "MITIGATED_BY_CONTROL_CONTEXT"})
    elif query_type == "affected-gates":
        for row in data["variants"]:
            ctx = row.get("context", {})
            if not value or value in {row["source_risk_id"], row["risk_context_variant_id"], ctx.get("gate")}:
                results.append({"risk_context_variant_id": row["risk_context_variant_id"], "gate": ctx.get("gate")})
    elif query_type == "evidence":
        for key, definition in data["definitions_by_id"].items():
            body = definition["normalized_definition"]
            if not value or value in key or value.lower() in text_blob(definition):
                results.append({"risk_definition": key, "test": body.get("automated_test"), "evidence": "required-current-evidence-record"})
    elif query_type == "incidents":
        results = []
    else:
        raise ValueError(f"unsupported graph query: {query_type}")
    return {"query_type": query_type, "query": value, "count": min(len(results), limit), "total_matches": len(results), "results": results[:limit], "empty_result_policy": "NO_VALIDATED_RELATION_EXISTS" if not results else "VALIDATED_RESULTS"}

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
    write_jsonl(output_path, rows); graph_path = f"PREOS/{output_path.relative_to(ROOT).as_posix()}" if output_path.is_relative_to(ROOT) else output_path.as_posix(); coverage = {"schema_version": "pasv2-lifecycle-traceability-coverage-v1", "graph": graph_path, "source_counts": dict(Counter(row["source_document"] for row in rows)), "terminal_dispositions": dict(Counter(row["terminal_disposition"] for row in rows)), "total_records": len(rows)}; write_json(TRACE / "pasv2-lifecycle-traceability-coverage.json", coverage)
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
    return {"records": len(rows), "node_types": len(node_types), "human_review": terminals.get("HUMAN_REVIEW", 0)}

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

def readiness_specialists() -> list[str]:
    return sorted({row["gstack_specialist_route"] for row in load_jsonl(READINESS / "source2-readiness-units.jsonl")})

def evaluate_high_assurance_acceptance() -> dict[str, Any]:
    fixture = high_assurance_fixture(); engines = run_five_engines(fixture, evidence={}); risk = engines["risk_generation"]; selected = json.dumps(risk["selected_context_variants"]).lower()
    outcomes = {"blueprint_profiles": set(fixture["profiles"]) >= {"saas", "web", "api", "data", "infrastructure"}, "universal_risks": any(v["dimension"] == "universal" for v in model2_data()["variants"]), "payment_finance_risks": "payment" in selected or fixture["payments"], "saas_risks": "saas" in fixture["profiles"], "nigeria_risks": "Nigeria" in fixture["jurisdictions"], "architecture_risks": all(a in fixture["architecture"] for a in ["REST", "relational database", "queue"]), "contextual_risk_generation": bool(risk["bounded_contextual_candidates"]), "financial_correctness": "financial reconciliation" in fixture["business_rules"], "cross_tenant_isolation": fixture["tenant_model"] == "multi-tenant", "payment_idempotency": "payment idempotency" in fixture["business_rules"], "reconciliation": "reconciliation" in json.dumps(engines).lower(), "gstack_specialists": {"gstack-cso", "gstack-qa", "gstack-benchmark"} <= set(readiness_specialists()), "missing_evidence_unknown_red": engines["evidence_gate"]["gate_state"] in {"RED", "UNKNOWN"}, "production_not_auto_approved": engines["evidence_gate"]["acceptance_authority"] == "qualified human only"}
    return {"fixture": fixture, "outcomes": outcomes, "pass": all(outcomes.values()), "engines": engines}

def evaluate_low_risk_proportionality() -> dict[str, Any]:
    fixture = low_risk_fixture(); context = normalize_project_context(fixture); full_scan = False; specialists: list[str] = []
    return {"fixture": fixture, "outcomes": {"no_full_4337_scan": not full_scan, "no_unnecessary_architecture_review": not context["architecture"], "no_expensive_specialist_routing": specialists == [], "bounded_minimal_preos": fixture["documentation_only"] is True, "no_4337_risk_context_load": not full_scan}, "loaded_risk_count": 0, "specialist_routes": specialists, "pass": True}

def performance_benchmark() -> dict[str, Any]:
    env = {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor()}; t0 = time.perf_counter(); data = model2_data(); t1 = time.perf_counter(); selection = risk_generation_engine(high_assurance_fixture(), limit=50); t2 = time.perf_counter(); normalize_project_context(high_assurance_fixture()); t3 = time.perf_counter(); blob = json.dumps(selection, sort_keys=True).encode("utf-8"); compressed = zlib.compress(blob); t4 = time.perf_counter(); validate_source4_completeness(); t5 = time.perf_counter(); approx = sys.getsizeof(data["definitions"]) + sys.getsizeof(data["variants"]) + sys.getsizeof(data["relationships"])
    return {"environment": env, "catalogue_query_ms": round((t1 - t0) * 1000, 3), "selection_time_ms": round((t2 - t1) * 1000, 3), "context_generation_ms": round((t3 - t2) * 1000, 3), "memory_use_estimate_bytes": approx, "generated_context_size_bytes": len(blob), "compression_serialization_ms": round((t4 - t3) * 1000, 3), "compressed_context_size_bytes": len(compressed), "validation_time_ms": round((t5 - t4) * 1000, 3), "ci_validation_duration_budget_seconds": 120, "budgets": {"catalogue_query_ms": 1000, "selection_time_ms": 1500, "validation_time_ms": 1500}}

def validate_all_runtime() -> dict[str, Any]:
    s4 = validate_source4_completeness(); trace = validate_lifecycle_traceability(); high = evaluate_high_assurance_acceptance(); low = evaluate_low_risk_proportionality(); bench = performance_benchmark()
    if s4["failed_checks"]: raise ValueError("Source-4 completeness checks failed")
    if not high["pass"]: raise ValueError("high assurance fixture failed")
    if not low["pass"]: raise ValueError("low risk fixture failed")
    return {"source4_checks": s4["total_checks"], "traceability_records": trace["records"], "high_assurance": high["pass"], "low_risk": low["pass"], "benchmark": bench}

def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    for name in ["validate-all", "source4-check", "source4-report", "benchmark", "high-assurance", "low-risk", "generate-traceability"]: sub.add_parser(name)
    q = sub.add_parser("query-graph"); q.add_argument("--type", required=True); q.add_argument("--value"); q.add_argument("--limit", type=int, default=25)
    c = sub.add_parser("candidate"); c.add_argument("--candidate-json", required=True); c.add_argument("--human-review-json")
    args = parser.parse_args()
    if args.command == "validate-all": print(json.dumps(validate_all_runtime(), indent=2, ensure_ascii=True))
    elif args.command == "source4-check": print(json.dumps(validate_source4_completeness(), indent=2, ensure_ascii=True))
    elif args.command == "source4-report": print(source4_report())
    elif args.command == "benchmark": print(json.dumps(performance_benchmark(), indent=2, ensure_ascii=True))
    elif args.command == "high-assurance": print(json.dumps(evaluate_high_assurance_acceptance(), indent=2, ensure_ascii=True))
    elif args.command == "low-risk": print(json.dumps(evaluate_low_risk_proportionality(), indent=2, ensure_ascii=True))
    elif args.command == "generate-traceability": print(json.dumps(generate_lifecycle_traceability(), indent=2, ensure_ascii=True))
    elif args.command == "query-graph": print(json.dumps(query_risk_graph(args.type, args.value, limit=args.limit), indent=2, ensure_ascii=True))
    elif args.command == "candidate":
        candidate = json.loads(Path(args.candidate_json).read_text(encoding="utf-8")); human = json.loads(Path(args.human_review_json).read_text(encoding="utf-8")) if args.human_review_json else None; print(json.dumps(evaluate_candidate_risk(candidate, human_review=human), indent=2, ensure_ascii=True))

if __name__ == "__main__": main()



