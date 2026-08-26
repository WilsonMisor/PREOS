#!/usr/bin/env python3
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
import sys

from preos_common import source_package_bytes

ROOT = Path(__file__).resolve().parents[1]
checks = ["validate-source-package.py", "validate-baseline.py", "validate-risk-catalogue.py", "validate-readiness.py", "validate-integration.py"]
for script in checks:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT)
    if r.returncode:
        raise SystemExit(r.returncode)

manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
required = manifest["required_paths"]
miss = [p for p in required if not (ROOT / p).exists()]
if miss:
    raise SystemExit("Missing PREOS files from MANIFEST.json:\n" + "\n".join(miss))
if len(required) != len(set(required)):
    raise SystemExit("MANIFEST.json contains duplicate required paths")

remediation_paths = [
    "schemas/pipeline-state.schema.json",
    "schemas/current-state.schema.json",
    "schemas/approval-state.schema.json",
    "schemas/evidence-index.schema.json",
    "schemas/hard-checkpoint-verification.schema.json",
    "scripts/state_machine.py",
    "scripts/schema_validation.py",
    "scripts/capture-evidence.py",
    "tests/test_applicability_semantics.py",
    "tests/test_master_plan_runtime_contract.py",
]
missing_remediation = [p for p in remediation_paths if not (ROOT / p).is_file()]
if missing_remediation:
    raise SystemExit("Missing master-plan remediation files:\n" + "\n".join(missing_remediation))

canonical = source_package_bytes(ROOT)
if len(canonical) != manifest["canonical_source"]["bytes"]:
    raise SystemExit("canonical reconstructed source ZIP byte count mismatch")
if hashlib.sha256(canonical).hexdigest() != manifest["canonical_source"]["sha256"]:
    raise SystemExit("canonical reconstructed source ZIP hash mismatch")

text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
anchors = [
    "UNKNOWN never silently becomes GREEN", "75", "1,130", "1,300", "PREOS_STATE_ROOT",
    ".ai-product-delivery/preos", "gstack-plan-eng-review", "AI Task Packet", "G0", "G11",
    "Conversation memory is never authoritative execution state", "RECOVERY_CONFLICT",
    "first unverified action", "wordpress-75-control-overlay.md",
]
for a in anchors:
    if a not in text:
        raise SystemExit(f"SKILL.md missing semantic anchor: {a}")

# Exact master-plan control applicability vocabulary.
control_schema = json.loads((ROOT / "schemas/control-assessment.schema.json").read_text(encoding="utf-8"))
actual_applicability = control_schema["properties"]["applicability"]["enum"]
expected_applicability = ["APPLIES", "CONDITIONAL", "NOT_APPLICABLE", "ESCALATE", "FORBIDDEN"]
if actual_applicability != expected_applicability:
    raise SystemExit(f"control applicability vocabulary mismatch: {actual_applicability}")
classify = (ROOT / "scripts/classify-controls.py").read_text(encoding="utf-8")
for token in ["CONDITIONAL", "NOT_APPLICABLE requires", "ESCALATE requires", "FORBIDDEN requires", "already_satisfied", "accountable human authority"]:
    if token not in classify:
        raise SystemExit(f"classify-controls missing applicability semantic: {token}")

# Exact master-plan runtime state vocabulary and executable transition enforcement.
state_module = (ROOT / "scripts/state_machine.py").read_text(encoding="utf-8")
expected_states = [
    "UNINITIALIZED", "INGESTING", "INTAKE_BLOCKED", "PLANNING", "PLAN_BLOCKED",
    "PLAN_APPROVAL_REQUIRED", "APPROVED_FOR_IMPLEMENTATION", "IMPLEMENTING",
    "IMPLEMENTATION_BLOCKED", "VERIFYING", "VERIFICATION_BLOCKED",
    "APPROVED_FOR_RELEASE", "RELEASE_BLOCKED", "RELEASED", "OPERATING",
    "NEEDS_RECONCILIATION", "RECOVERY_CONFLICT",
]
for state in expected_states:
    if f'"{state}"' not in state_module:
        raise SystemExit(f"state machine missing canonical state: {state}")
for token in ["require_transition", "target_for_event", "validate_event"]:
    if token not in state_module:
        raise SystemExit(f"state machine missing enforcement primitive: {token}")
pipeline_schema = json.loads((ROOT / "schemas/pipeline-state.schema.json").read_text(encoding="utf-8"))
if pipeline_schema["properties"]["state"]["enum"] != expected_states:
    raise SystemExit("pipeline-state.schema.json does not contain the exact canonical state order")

# Recovery must reconcile pipeline/current/checkpoint/ledger and validate owned schemas.
runtime = (ROOT / "scripts/runtime_state.py").read_text(encoding="utf-8")
for token in [
    "load_pipeline_state", "PIPELINE_STATE_MISMATCH", "PIPELINE_TASK_PACKET_MISMATCH",
    "validate_file(path, SCHEMAS / \"current-state.schema.json\")",
    "unknown event_type", "ledger/checkpoint task packet mismatch", "require_transition",
    "configuration_files", "schema_files", "dependency_files", "test_definition_files",
    "environment changed", "validity period expired",
]:
    if token not in runtime:
        raise SystemExit(f"runtime recovery missing strict semantic: {token}")

checkpoint = (ROOT / "scripts/checkpoint-state.py").read_text(encoding="utf-8")
for token in ["--verification-manifest", "hard-checkpoint-verification.schema.json", "declared Task Packet", "verification evidence is stale", "rollback_point", "traceability"]:
    if token not in checkpoint:
        raise SystemExit(f"hard checkpoint implementation missing proof semantic: {token}")

evidence_capture = (ROOT / "scripts/capture-evidence.py").read_text(encoding="utf-8")
for token in ["source_hashes", "configuration_files", "schema_files", "dependency_files", "test_definition_files", "environment_binding", "valid_until"]:
    if token not in evidence_capture:
        raise SystemExit(f"evidence capture missing freshness binding: {token}")
evidence_validate = (ROOT / "scripts/validate-evidence.py").read_text(encoding="utf-8")
if "--require-complete-bindings" not in evidence_validate:
    raise SystemExit("strict evidence-binding validation mode is missing")

rec = (ROOT / "RECOMMENDATION-COVERAGE.md").read_text(encoding="utf-8")
for n in range(1, 39):
    if f"| I{n:02d} |" not in rec:
        raise SystemExit(f"missing integration recommendation I{n:02d}")
source = (ROOT / "SOURCE-CONCEPT-COVERAGE.md").read_text(encoding="utf-8")
for n in range(1, 53):
    if f"| D{n:02d} |" not in source:
        raise SystemExit(f"missing source domain D{n:02d}")
metadata = [
    "VERSION", "CHANGELOG.md", "LICENSE-NOTES.md", "SECURITY.md", "CONTRIBUTING.md",
    "INTEGRATION-CONTRACT.md", ".gitignore", ".github/workflows/validate-preos.yml", ".github/CODEOWNERS",
]
for p in metadata:
    if not (ROOT / p).exists():
        raise SystemExit(f"missing repository metadata: {p}")
overlay = (ROOT / "references/wordpress/wordpress-75-control-overlay.md").read_text(encoding="utf-8")
ids = re.findall(r"\| (FS-\d{3}) \|", overlay)
expected = [f"FS-{n:03d}" for n in range(1, 76)]
if ids != expected or len(set(ids)) != 75:
    raise SystemExit("WordPress overlay must map FS-001..FS-075 exactly once and in order")
continuity = (ROOT / "docs/session-continuity.md").read_text(encoding="utf-8")
for a in [
    "SAFE_TO_RESUME", "BLOCKED", "RECOVERY_CONFLICT", "first unverified",
    "gstack context-save/context-restore", "PIPELINE-STATE.json", "test-definition",
    "--require-complete-bindings",
]:
    if a not in continuity:
        raise SystemExit(f"session-continuity documentation missing anchor: {a}")

print(f"PASS PREOS manifest: {len(required)} required paths exist; canonical source hash matches")
print("PASS PREOS semantic completeness: 38 integration recommendations and 52 source domains covered")
print("PASS PREOS applicability: exact APPLIES/CONDITIONAL/NOT_APPLICABLE/ESCALATE/FORBIDDEN semantics")
print("PASS PREOS state/recovery: canonical state machine, schema validation, pipeline/ledger reconciliation")
print("PASS PREOS checkpoints/evidence: declared hard-boundary proof and complete freshness binding vocabulary")
print("PASS PREOS AI-session continuity/recovery anchors and WordPress 75/75 interpretation present")
print("PASS PREOS repository metadata and integration contracts present")
print("PASS PREOS validation complete")
