#!/usr/bin/env python3
"""Classify canonical PREOS controls using the master-plan applicability semantics.

The 75-control baseline is immutable. This command produces project-specific
assessments. Unresolved applicability never silently becomes APPLIES or GREEN;
it escalates. CONDITIONAL must resolve to APPLIES, NOT_APPLICABLE, or ESCALATE.
FORBIDDEN remains blocking unless an accountable human override is explicitly
recorded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from preos_common import load_source_json

STATES = {"APPLIES", "CONDITIONAL", "NOT_APPLICABLE", "ESCALATE", "FORBIDDEN"}
AI_WORDS = {"AI", "CODEX", "GSTACK", "LLM", "AGENT", "PREOS"}


def authority_is_human(value: str) -> bool:
    words = {w for w in re.split(r"[^A-Za-z0-9]+", str(value or "").upper()) if w}
    return bool(words) and not bool(words & AI_WORDS) and words not in ({"UNKNOWN"}, {"UNASSIGNED"})


def load_assessments(path: str | None) -> dict[int, dict]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("controls", data) if isinstance(data, dict) else data
    out: dict[int, dict] = {}
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = []
        for key, value in raw.items():
            if not isinstance(value, dict):
                raise ValueError(f"control assessment {key} must be an object")
            item = dict(value); item.setdefault("control_no", int(key)); items.append(item)
    else:
        raise ValueError("assessments must be a list or controls object")
    for item in items:
        if not isinstance(item, dict) or "control_no" not in item:
            raise ValueError("each assessment requires control_no")
        no = int(item["control_no"])
        if no in out:
            raise ValueError(f"duplicate assessment for control {no}")
        out[no] = item
    return out


def normalize_assessment(control: dict, supplied: dict | None) -> dict:
    no = int(control["no"])
    rule = control.get("applicability_rule")
    if supplied is None:
        return {
            "control_no": no,
            "requested_applicability": "UNRESOLVED",
            "applicability": "ESCALATE",
            "condition": None,
            "condition_result": "NOT_EVALUATED",
            "not_applicable_reason": None,
            "escalation_reason": "project-specific applicability has not been resolved",
            "human_decision_id": None,
            "forbidden_reason": None,
            "authorized_override": None,
            "obligation_required": False,
            "already_satisfied": False,
            "result": "HUMAN REVIEW",
            "evidence_ids": [],
            "dependencies": [],
            "owner": None,
            "rule": rule,
        }

    requested = str(supplied.get("applicability") or "").upper()
    if requested not in STATES:
        raise ValueError(f"control {no}: invalid applicability {requested!r}")
    condition = supplied.get("condition")
    condition_result = str(supplied.get("condition_result") or "NOT_EVALUATED").upper()
    if condition_result not in {"TRUE", "FALSE", "UNKNOWN", "NOT_EVALUATED"}:
        raise ValueError(f"control {no}: invalid condition_result")

    applicability = requested
    escalation_reason = supplied.get("escalation_reason")
    not_applicable_reason = supplied.get("not_applicable_reason")
    if requested == "CONDITIONAL":
        if not condition:
            raise ValueError(f"control {no}: CONDITIONAL requires condition")
        if condition_result == "TRUE":
            applicability = "APPLIES"
        elif condition_result == "FALSE":
            applicability = "NOT_APPLICABLE"
            if not not_applicable_reason:
                not_applicable_reason = f"condition evaluated FALSE: {condition}"
        else:
            applicability = "ESCALATE"
            escalation_reason = escalation_reason or f"condition unresolved: {condition}"

    evidence_ids = sorted({str(x) for x in supplied.get("evidence_ids", []) if str(x)})
    already_satisfied = bool(supplied.get("already_satisfied", False))
    owner = supplied.get("owner")
    dependencies = list(supplied.get("dependencies", []))
    human_decision_id = supplied.get("human_decision_id")
    forbidden_reason = supplied.get("forbidden_reason")
    override = supplied.get("authorized_override")

    obligation_required = False
    result = str(supplied.get("result") or "UNKNOWN").upper()

    if applicability == "APPLIES":
        obligation_required = not already_satisfied
        if already_satisfied:
            if not evidence_ids:
                raise ValueError(f"control {no}: already_satisfied requires existing evidence_ids")
            result = "GREEN"
        elif result in {"NOT_APPLICABLE", "BLOCKED"}:
            raise ValueError(f"control {no}: APPLIES cannot have result {result}")

    elif applicability == "NOT_APPLICABLE":
        if not str(not_applicable_reason or "").strip():
            raise ValueError(f"control {no}: NOT_APPLICABLE requires evidence-based reason")
        obligation_required = False
        result = "NOT_APPLICABLE"

    elif applicability == "ESCALATE":
        if not str(escalation_reason or "").strip():
            raise ValueError(f"control {no}: ESCALATE requires escalation_reason")
        obligation_required = False
        result = "HUMAN REVIEW"

    elif applicability == "FORBIDDEN":
        if not str(forbidden_reason or "").strip():
            raise ValueError(f"control {no}: FORBIDDEN requires forbidden_reason")
        obligation_required = False
        if override is None:
            result = "BLOCKED"
        else:
            if not isinstance(override, dict):
                raise ValueError(f"control {no}: authorized_override must be an object")
            for field in ("approval_id", "authority", "rationale"):
                if not str(override.get(field) or "").strip():
                    raise ValueError(f"control {no}: authorized_override requires {field}")
            if not authority_is_human(str(override["authority"])):
                raise ValueError(f"control {no}: FORBIDDEN override requires accountable human authority")
            result = str(supplied.get("result") or "HUMAN REVIEW").upper()
            if result == "GREEN" and not evidence_ids:
                raise ValueError(f"control {no}: overridden FORBIDDEN control cannot be GREEN without evidence")

    return {
        "control_no": no,
        "requested_applicability": requested,
        "applicability": applicability,
        "condition": condition,
        "condition_result": condition_result,
        "not_applicable_reason": not_applicable_reason,
        "escalation_reason": escalation_reason,
        "human_decision_id": human_decision_id,
        "forbidden_reason": forbidden_reason,
        "authorized_override": override,
        "obligation_required": obligation_required,
        "already_satisfied": already_satisfied,
        "result": result,
        "evidence_ids": evidence_ids,
        "dependencies": dependencies,
        "owner": owner,
        "rule": rule,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Produce project-specific PREOS control applicability assessments.")
    ap.add_argument("--assessments", help="Governed JSON assessment input keyed by control number or as a list")
    ap.add_argument("--output")
    args = ap.parse_args()
    controls = load_source_json("baseline_75_controls.json")["controls"]
    supplied = load_assessments(args.assessments)
    known = {int(c["no"]) for c in controls}
    extra = sorted(set(supplied) - known)
    if extra:
        raise SystemExit(f"unknown control numbers: {extra}")
    out = [normalize_assessment(c, supplied.get(int(c["no"]))) for c in controls]
    payload = {"schema_version": "1.2", "controls": out}
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if any(c["applicability"] == "FORBIDDEN" and c["result"] == "BLOCKED" for c in out):
        raise SystemExit(4)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"APPLICABILITY_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
