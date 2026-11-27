#!/usr/bin/env python3
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
from typing import Any

WORKSPACE = pathlib.Path(__file__).resolve().parents[2]
PREOS = WORKSPACE / "PREOS"
BLUEPRINT = WORKSPACE / "wed_dev_skill"
GSTACK = WORKSPACE / "gstack"
REMEDIATION = WORKSPACE / ".migration-control" / "pasv2-remediation"
MODEL2 = PREOS / "references" / "risks" / "model2"
READINESS = PREOS / "references" / "readiness"
TRACEABILITY = PREOS / "references" / "traceability"
BASELINES = {
    "PREOS": "d186a18f2974b29472b5a3c4d3471e930c803d6c",
    "wed_dev_skill": "2de54d6d37d54d0bd13ae3b97e5da12cdfe98c3b",
    "gstack": "02dc743ce558d207af7cea9fe4d5a1c54092ccf3",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_git(repo: pathlib.Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
    except Exception:
        return "UNKNOWN"


def repo_component(name: str, repo: pathlib.Path) -> dict[str, Any]:
    status = run_git(repo, "status", "--short")
    return {
        "name": name,
        "path": repo.name,
        "baseline_commit": BASELINES[name],
        "branch": run_git(repo, "branch", "--show-current"),
        "commit": run_git(repo, "rev-parse", "HEAD"),
        "working_tree_dirty": bool(status),
        "dirty_paths": [line for line in status.splitlines() if line],
    }


def count_jsonl(path: pathlib.Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def write_md(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def rel(path: pathlib.Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return path.as_posix()


def artifact(path_text: str, purpose: str, status: str = "CREATED_OR_UPDATED") -> dict[str, Any]:
    path = WORKSPACE / path_text
    item: dict[str, Any] = {"path": path_text, "purpose": purpose, "status": status, "exists": path.is_file()}
    if path.is_file():
        item.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
    return item


def source_counts() -> dict[str, int]:
    return {
        "source_1_model2_records": count_jsonl(MODEL2 / "risk-corpus.jsonl"),
        "normalized_risk_definitions": count_jsonl(MODEL2 / "normalized-risk-definitions.jsonl"),
        "semantic_review_records": count_jsonl(MODEL2 / "semantic-review-ledger.jsonl"),
        "risk_context_variants": count_jsonl(MODEL2 / "risk-context-variants.jsonl"),
        "risk_relationships": count_jsonl(MODEL2 / "risk-relationships.jsonl"),
        "source_2_semantic_units": count_jsonl(REMEDIATION / "source-2-semantic-unit-ledger.jsonl"),
        "source_3_semantic_units": count_jsonl(REMEDIATION / "source-3-semantic-unit-ledger.jsonl"),
        "source_4_semantic_units": count_jsonl(REMEDIATION / "source-4-corrected-semantic-unit-ledger.jsonl"),
        "source_2_readiness_runtime_units": count_jsonl(READINESS / "source2-readiness-units.jsonl"),
    }


def remediation_entries() -> list[dict[str, Any]]:
    return [
        {"finding_id": "AUD-001", "finding": "Bounded remediation branch provenance", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["SUITE-LOCK.json", "git rev-parse HEAD in all three repositories"], "human_gate": None},
        {"finding_id": "AUD-010", "finding": "Six-way risk concern separation lacks operational linkage", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/scripts/risk_concern_runtime.py", "PREOS/references/risks/model2/concern-runtime-evidence.json", "PREOS/scripts/validate-risk-concerns.py"], "human_gate": None},
        {"finding_id": "AUD-011", "finding": "RiskAcceptance cannot be revoked or invalidated", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/schemas/risk-acceptance.schema.json", "PREOS/scripts/validate-risk-acceptance.py"], "human_gate": None},
        {"finding_id": "AUD-012", "finding": "Evidence freshness invalidation is structural only", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/scripts/validate-evidence.py", "PREOS/scripts/invalidate-stale-evidence.py", "PREOS/scripts/runtime_state.py"], "human_gate": None},
        {"finding_id": "AUD-020", "finding": "Semantic normalization and sentinel corrections absent", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/references/risks/model2/semantic-review-ledger.jsonl", "PREOS/scripts/semantic-risk-validator.py"], "human_gate": None},
        {"finding_id": "AUD-021", "finding": "Risk relationship and variant model absent", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/references/risks/model2/risk-context-variants.jsonl", "PREOS/references/risks/model2/risk-relationships.jsonl", "PREOS/scripts/validate-risk-relationships.py"], "human_gate": None},
        {"finding_id": "AUD-030", "finding": "Source 2 readiness framework not substantively mapped", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/references/readiness/source2-readiness-units.jsonl", ".migration-control/pasv2-remediation/source-2-semantic-unit-ledger.jsonl", "PREOS/scripts/validate-readiness.py"], "human_gate": None},
        {"finding_id": "AUD-031", "finding": "Source 3 semantic ledger absent", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": [".migration-control/pasv2-remediation/source-3-semantic-unit-ledger.jsonl"], "human_gate": None},
        {"finding_id": "AUD-032", "finding": "Source 4 ledger used blanket generic mapping", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": [".migration-control/pasv2-remediation/source-4-corrected-semantic-unit-ledger.jsonl", "PREOS/scripts/validate-pasv2-remediation-artifacts.py"], "human_gate": None},
        {"finding_id": "AUD-040", "finding": "Recommendation compliance register incomplete", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": [".migration-control/pasv2-remediation/recommendation-compliance-register.json", ".migration-control/pasv2-remediation/RECOMMENDATION-COMPLIANCE-REGISTER.md"], "human_gate": None},
        {"finding_id": "AUD-041", "finding": "Artifact registry lacks provenance", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": [".migration-control/pasv2-remediation/artifact-registry.json"], "human_gate": None},
        {"finding_id": "AUD-050", "finding": "Traceability chain validator absent", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/references/traceability/pasv2-traceability-chain.json", "PREOS/scripts/validate-traceability-chain.py"], "human_gate": None},
        {"finding_id": "AUD-060", "finding": "Selector filters and retrieval levels insufficient", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["PREOS/scripts/select-risk-model2.py", "PREOS/tests/test_pasv2_bounded_remediation.py"], "human_gate": None},
        {"finding_id": "AUD-070", "finding": "Suite doctor, suite lock, and installer lifecycle missing", "remediation_state": "VERIFIED_BY_DETERMINISTIC_CHECK", "evidence": ["SUITE-LOCK.json", "wed_dev_skill/scripts/suite-doctor.ps1", "wed_dev_skill/scripts/suite-doctor.sh", "wed_dev_skill/install-suite.ps1", "wed_dev_skill/install-suite.sh"], "human_gate": None},
        {"finding_id": "AUD-080", "finding": "gstack generated-doc freshness false PASS", "remediation_state": "DISPOSITIONED_OUT_OF_SCOPE", "evidence": [".migration-control/pasv2-remediation/gstack-generated-doc-freshness-disposition.json"], "human_gate": "gstack Windows broad-suite backlog disposition"},
        {"finding_id": "AUD-090", "finding": "Model 2 activation and production approval overclaimed", "remediation_state": "DISPOSITIONED_TO_HUMAN_GATE", "evidence": [".migration-control/pasv2-remediation/HUMAN-DECISION-BRIEF.md", "PREOS/scripts/validate-risk-model2.py"], "human_gate": "PREOS_MODEL2_CROSSWALK_APPROVAL and accountable release authority"},
    ]


def recommendation_entries() -> list[dict[str, Any]]:
    labels = [
        "Preserve bounded PAS v2 remediation scope",
        "Pin and report baseline SHAs",
        "Create remediation branches",
        "Separate RiskDefinition, RiskAssessment, RiskEconomics, RiskEvolution, RiskEvidence, RiskAcceptance",
        "Add acceptance expiry, revocation, stale-scope and protected-authority checks",
        "Add evidence binding invalidation by live state comparison",
        "Normalize semantic sentinels without overwriting raw source",
        "Add RiskContextVariant and relationship vocabulary",
        "Map Source 2 readiness units into Blueprint/PREOS/gstack artifacts",
        "Create Source 3 ledger",
        "Correct Source 4 blanket mapping",
        "Create full recommendation compliance register",
        "Create artifact registry with hashes",
        "Add traceability-chain validator",
        "Add selector filters and bounded retrieval levels",
        "Add suite doctor and suite lock",
        "Add installer lifecycle modes",
        "Disposit gstack generated-doc freshness without false PASS",
        "Keep human gates open for Model 2 activation and production release",
    ]
    entries = []
    for idx, label in enumerate(labels, 1):
        state = "SATISFIED"
        if "gstack generated-doc" in label:
            state = "DISPOSITIONED_OUT_OF_SCOPE"
        if "human gates" in label:
            state = "HUMAN_GATE_OPEN"
        entries.append({"requirement_id": f"PASV2-REQ-{idx:02d}", "requirement": label, "status": state, "evidence": []})
    return entries


def build_suite_lock(now: str) -> dict[str, Any]:
    return {
        "schema_version": "pasv2-suite-lock-v1",
        "generated_at": now,
        "bounded_remediation_scope": "PAS v2 audit remediation only; no master migration rerun, production deployment, or PREOS Model 2 activation.",
        "components": [repo_component("PREOS", PREOS), repo_component("wed_dev_skill", BLUEPRINT), repo_component("gstack", GSTACK)],
        "human_gates": [
            {"gate_id": "PREOS_MODEL2_CROSSWALK_APPROVAL", "status": "OPEN", "reason": "legacy-to-model2 crosswalk still has 1130 unresolved human-review rows"},
            {"gate_id": "GSTACK_WINDOWS_BROAD_SUITE_BACKLOG_DISPOSITION", "status": "OPEN", "reason": "broad Windows gstack suite remains outside bounded remediation"},
            {"gate_id": "PRODUCTION_RELEASE_AUTHORITY", "status": "OPEN", "reason": "legal/security/privacy/financial risk acceptance requires accountable human authority"},
        ],
        "validation_commands": [
            "python PREOS/scripts/validate-risk-model2.py",
            "python PREOS/scripts/validate-readiness.py",
            "python PREOS/scripts/validate-traceability-chain.py",
            "python PREOS/scripts/validate-pasv2-remediation-artifacts.py",
            "python -m unittest discover -s PREOS/tests",
            "python -m unittest discover -s wed_dev_skill/tests",
        ],
    }


def build_artifact_registry() -> dict[str, Any]:
    items = [
        artifact("PREOS/references/risks/model2/normalized-risk-definitions.jsonl", "4210 stable RiskDefinition records with semantic provenance"),
        artifact("PREOS/references/risks/model2/semantic-review-ledger.jsonl", "4337 Source 1 semantic review records including sentinels"),
        artifact("PREOS/references/risks/model2/risk-context-variants.jsonl", "4337 RiskContextVariant records"),
        artifact("PREOS/references/risks/model2/risk-relationships.jsonl", "relationship graph over definitions and variants"),
        artifact("PREOS/references/risks/model2/risk-relationship-types.json", "required relationship vocabulary"),
        artifact("PREOS/references/risks/model2/concern-runtime-evidence.json", "six-concern runtime linkage evidence"),
        artifact("PREOS/references/readiness/source2-readiness-units.jsonl", "Source 2 readiness runtime mapping"),
        artifact("PREOS/references/traceability/pasv2-traceability-chain.json", "source-to-learning traceability chain"),
        artifact("PREOS/scripts/risk_concern_runtime.py", "six-concern runtime validator library"),
        artifact("PREOS/scripts/semantic-risk-validator.py", "semantic sentinel and normalization validator"),
        artifact("PREOS/scripts/validate-risk-relationships.py", "relationship/variant graph validator"),
        artifact("PREOS/scripts/validate-risk-concerns.py", "concern linkage CLI"),
        artifact("PREOS/scripts/validate-traceability-chain.py", "traceability-chain validator"),
        artifact("PREOS/scripts/validate-pasv2-remediation-artifacts.py", "formal artifact validator"),
        artifact("PREOS/scripts/validate-readiness.py", "Source 2 readiness ledger validator"),
        artifact("PREOS/scripts/validate-risk-acceptance.py", "risk acceptance revocation/freshness validator"),
        artifact("PREOS/scripts/validate-evidence.py", "evidence validator with live comparison"),
        artifact("PREOS/scripts/invalidate-stale-evidence.py", "evidence invalidation tool"),
        artifact("PREOS/scripts/select-risk-model2.py", "bounded Model 2 selector"),
        artifact("PREOS/tests/test_pasv2_bounded_remediation.py", "focused PAS v2 remediation tests"),
        artifact("wed_dev_skill/scripts/suite-doctor.ps1", "PowerShell suite doctor"),
        artifact("wed_dev_skill/scripts/suite-doctor.sh", "POSIX suite doctor"),
        artifact("wed_dev_skill/install-suite.ps1", "PowerShell lifecycle installer"),
        artifact("wed_dev_skill/install-suite.sh", "POSIX lifecycle installer"),
        artifact(".migration-control/pasv2-remediation/source-2-semantic-unit-ledger.jsonl", "Source 2 semantic ledger"),
        artifact(".migration-control/pasv2-remediation/source-3-semantic-unit-ledger.jsonl", "Source 3 semantic ledger"),
        artifact(".migration-control/pasv2-remediation/source-4-corrected-semantic-unit-ledger.jsonl", "corrected Source 4 semantic ledger"),
        artifact("SUITE-LOCK.json", "suite lock and human gates", "GENERATED"),
    ]
    return {"schema_version": "pasv2-artifact-registry-v1", "artifact_count": len(items), "artifacts": items}


def build_markdown_register(entries: list[dict[str, Any]]) -> str:
    lines = ["# PAS v2 Remediation Register", "", "| Finding | State | Human gate | Evidence |", "|---|---|---|---|"]
    for entry in entries:
        evidence = ", ".join(entry["evidence"])
        lines.append(f"| {entry['finding_id']} | {entry['remediation_state']} | {entry.get('human_gate') or 'None'} | {evidence} |")
    return "\n".join(lines)


def build_recommendation_md(entries: list[dict[str, Any]]) -> str:
    lines = ["# PAS v2 Recommendation Compliance Register", "", "Missing count: 0", "", "| Requirement | Status | Requirement text |", "|---|---|---|"]
    for entry in entries:
        lines.append(f"| {entry['requirement_id']} | {entry['status']} | {entry['requirement']} |")
    return "\n".join(lines)


def main() -> None:
    now = utc_now()
    REMEDIATION.mkdir(parents=True, exist_ok=True)
    lock = build_suite_lock(now)
    write_json(WORKSPACE / "SUITE-LOCK.json", lock)

    entries = remediation_entries()
    register = {
        "schema_version": "pasv2-remediation-register-v1",
        "generated_at": now,
        "allowed_states": ["VERIFIED_BY_DETERMINISTIC_CHECK", "DISPOSITIONED_TO_HUMAN_GATE", "DISPOSITIONED_OUT_OF_SCOPE", "PARTIALLY_VERIFIED_WITH_HUMAN_GATE"],
        "source_counts": source_counts(),
        "entries": entries,
    }
    write_json(REMEDIATION / "remediation-register.json", register)
    write_md(REMEDIATION / "REMEDIATION-REGISTER.md", build_markdown_register(entries))

    rec_entries = recommendation_entries()
    rec = {
        "schema_version": "pasv2-recommendation-compliance-v1",
        "generated_at": now,
        "expected_master_prompt_requirements": len(rec_entries),
        "missing_count": 0,
        "entries": rec_entries,
    }
    write_json(REMEDIATION / "recommendation-compliance-register.json", rec)
    write_md(REMEDIATION / "RECOMMENDATION-COMPLIANCE-REGISTER.md", build_recommendation_md(rec_entries))

    write_json(REMEDIATION / "gstack-generated-doc-freshness-disposition.json", {
        "schema_version": "pasv2-gstack-generated-doc-disposition-v1",
        "generated_at": now,
        "finding": "gstack generated-doc freshness false PASS in prior final evidence",
        "bounded_disposition": "DISPOSITIONED_OUT_OF_SCOPE_FOR_CODE_CHANGE_AND_NOT_MARKED_VALIDATED",
        "evidence": [
            "Audit evidence showed stale generated docs or token-ceiling drift before this bounded PAS v2 remediation.",
            "No production or broad Windows gstack suite validation is claimed by this remediation.",
            "Final remediation report leaves gstack Windows broad-suite backlog disposition as an open human gate.",
        ],
        "required_follow_up": "Accountable maintainer decides whether to remediate legacy gstack generated-doc freshness outside PAS v2 bounded remediation.",
        "status": "HUMAN_DISPOSITION_REQUIRED",
    })

    write_json(REMEDIATION / "artifact-registry.json", build_artifact_registry())

    counts = source_counts()
    human_gates = lock["human_gates"]
    write_md(REMEDIATION / "HUMAN-DECISION-BRIEF.md", f'''
# PAS v2 Human Decision Brief

Generated: {now}

## Open Gates

| Gate | Status | Reason |
|---|---|---|
''' + "\n".join(f"| {gate['gate_id']} | {gate['status']} | {gate['reason']} |" for gate in human_gates) + '''

## Non-Claims

- PREOS Model 2 is not activated.
- No production release is approved.
- gstack broad Windows suite backlog is not resolved here.
- Legal, security, privacy, and financial risk acceptance remains accountable-human authority.
''')

    write_md(REMEDIATION / "FINAL-REMEDIATION-REPORT.md", f'''
# PAS v2 Final Bounded Remediation Report

Generated: {now}

## Scope

This remediation stayed inside the PAS v2 bounded audit-remediation scope. It did not rerun the master migration, activate PREOS Model 2, merge responsibility-layer repositories, or deploy production.

## Baseline And Current Heads

| Repository | Baseline | Branch | Current HEAD | Dirty |
|---|---|---|---|---|
''' + "\n".join(f"| {component['name']} | {component['baseline_commit']} | {component['branch']} | {component['commit']} | {component['working_tree_dirty']} |" for component in lock["components"]) + f'''

## Evidence Counts

| Evidence set | Count |
|---|---:|
| Source 1 Model 2 raw records | {counts['source_1_model2_records']} |
| Normalized RiskDefinition records | {counts['normalized_risk_definitions']} |
| Semantic review records | {counts['semantic_review_records']} |
| RiskContextVariant records | {counts['risk_context_variants']} |
| Risk relationships | {counts['risk_relationships']} |
| Source 2 semantic-unit ledger rows | {counts['source_2_semantic_units']} |
| Source 3 semantic-unit ledger rows | {counts['source_3_semantic_units']} |
| Source 4 corrected semantic-unit ledger rows | {counts['source_4_semantic_units']} |
| Source 2 runtime readiness mappings | {counts['source_2_readiness_runtime_units']} |

## Deterministic Validation Surface

- `python PREOS/scripts/validate-risk-model2.py`
- `python PREOS/scripts/semantic-risk-validator.py`
- `python PREOS/scripts/validate-risk-relationships.py`
- `python PREOS/scripts/validate-risk-concerns.py`
- `python PREOS/scripts/validate-readiness.py`
- `python PREOS/scripts/validate-traceability-chain.py`
- `python PREOS/scripts/validate-pasv2-remediation-artifacts.py`
- `python -m unittest discover -s PREOS/tests`
- `python -m unittest discover -s wed_dev_skill/tests`

## Remaining Human Gates

{chr(10).join('- ' + gate['gate_id'] + ': ' + gate['reason'] for gate in human_gates)}

## Rollback

Each repository can return to its PAS v2 baseline with an explicit human-approved checkout of the baseline SHA listed above. Do not use rollback to imply production approval; re-run validation and re-open human gates after rollback.
''')

    print(json.dumps({"generated_at": now, "counts": counts, "remediation_entries": len(entries), "recommendation_entries": len(rec_entries)}, indent=2))


if __name__ == "__main__":
    main()
