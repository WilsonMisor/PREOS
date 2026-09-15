#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT = WORKSPACE / ".migration-control" / "pasv2-remediation"


def count_jsonl(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PAS v2 remediation evidence artifacts.")
    parser.add_argument("--remediation-root", default=str(DEFAULT))
    args = parser.parse_args()
    root = Path(args.remediation_root)
    required = [
        "FINAL-REMEDIATION-REPORT.md",
        "REMEDIATION-REGISTER.md",
        "remediation-register.json",
        "RECOMMENDATION-COMPLIANCE-REGISTER.md",
        "recommendation-compliance-register.json",
        "artifact-registry.json",
        "source-2-semantic-unit-ledger.jsonl",
        "source-3-semantic-unit-ledger.jsonl",
        "source-4-corrected-semantic-unit-ledger.jsonl",
        "gstack-generated-doc-freshness-disposition.json",
        "HUMAN-DECISION-BRIEF.md",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise SystemExit("FAIL PAS v2 remediation artifacts: missing " + ", ".join(missing))
    expected_counts = {
        "source-2-semantic-unit-ledger.jsonl": 1148,
        "source-3-semantic-unit-ledger.jsonl": 1612,
        "source-4-corrected-semantic-unit-ledger.jsonl": 1459,
    }
    for name, expected in expected_counts.items():
        actual = count_jsonl(root / name)
        if actual != expected:
            raise SystemExit(f"FAIL {name}: expected {expected}, found {actual}")
    register = load_json(root / "remediation-register.json")
    allowed = set(register["allowed_states"])
    for entry in register["entries"]:
        state = entry.get("remediation_state")
        if state not in allowed:
            raise SystemExit(f"FAIL invalid remediation state: {state}")
        if state in {"NOT_STARTED", "IN_PROGRESS", "REMEDIATED"}:
            raise SystemExit(f"FAIL unfinished remediation state in {entry.get('finding_id')}: {state}")
    rec = load_json(root / "recommendation-compliance-register.json")
    if rec.get("missing_count") != 0:
        raise SystemExit("FAIL recommendation register reports missing requirements")
    if len(rec.get("entries", [])) != rec.get("expected_master_prompt_requirements"):
        raise SystemExit("FAIL recommendation register count mismatch")
    source4_rows = [json.loads(line) for line in (root / "source-4-corrected-semantic-unit-ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    generic = [row["source_unit_id"] for row in source4_rows if row.get("target_artifacts") == ["PREOS/references/integration/source4-production-assurance-crosswalk.json", "gstack/integration/PASV2-SOURCE4-ROUTING.json", "wed_dev_skill/orchestration/preos-routing.md"]]
    if generic:
        raise SystemExit("FAIL Source 4 ledger still contains blanket three-artifact mapping")
    artifacts = load_json(root / "artifact-registry.json")
    if artifacts.get("artifact_count") != len(artifacts.get("artifacts", [])):
        raise SystemExit("FAIL artifact registry count mismatch")
    if not (WORKSPACE / "SUITE-LOCK.json").is_file():
        raise SystemExit("FAIL SUITE-LOCK.json missing")
    print("PASS PAS v2 remediation artifacts: registers, ledgers, artifact registry, suite lock, human brief")


if __name__ == "__main__":
    main()
