#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

PROTECTED_AUTHORITY_WORDS = {"AI", "CODEX", "GSTACK", "LLM", "AGENT", "PREOS"}
ACCEPTANCE_STATUSES = {"ACTIVE", "EXPIRED", "REVOKED", "SUPERSEDED"}


class RiskConcernError(ValueError):
    pass


def parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RiskConcernError("missing timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RiskConcernError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise RiskConcernError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def authority_is_protected(authority: str) -> bool:
    words = {w for w in re.split(r"[^A-Za-z0-9]+", str(authority).upper()) if w}
    return bool(words & PROTECTED_AUTHORITY_WORDS)


def definition_key(record: dict[str, Any]) -> tuple[str, str]:
    rid = record.get("risk_definition_id")
    version = record.get("definition_version")
    if not rid or not version:
        raise RiskConcernError("record missing risk_definition_id or definition_version")
    return str(rid), str(version)


def _require_definition_ref(record: dict[str, Any], definitions: set[tuple[str, str]], label: str) -> tuple[str, str]:
    key = definition_key(record)
    if key not in definitions:
        raise RiskConcernError(f"{label} references missing RiskDefinition/version: {key[0]}@{key[1]}")
    return key


def acceptance_stale_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    current_definition_version = record.get("current_definition_version")
    if current_definition_version and current_definition_version != record.get("definition_version"):
        reasons.append("risk definition version changed")
    current_scope_hash = record.get("current_scope_hash")
    if current_scope_hash and record.get("scope_hash") and current_scope_hash != record.get("scope_hash"):
        reasons.append("scope changed")
    current_assessment_id = record.get("current_risk_assessment_id")
    if current_assessment_id and record.get("risk_assessment_id") and current_assessment_id != record.get("risk_assessment_id"):
        reasons.append("risk assessment changed")
    return reasons


def validate_acceptance_record(record: dict[str, Any], *, now: datetime | None = None) -> bool:
    """Validate structure and temporal eligibility, NEVER human approval.

    Authority consumers must call verify_acceptance_authority with the trusted
    PREOS approval store. A caller-supplied current_authority flag is not proof.
    """
    now = now or datetime.now(timezone.utc)
    for field in ("acceptance_id", "risk_definition_id", "definition_version", "authority", "reason", "scope", "approved_at", "expires_at", "review_trigger", "status"):
        if not record.get(field):
            raise RiskConcernError(f"acceptance missing {field}")
    status = str(record["status"]).upper()
    if status not in ACCEPTANCE_STATUSES:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} has invalid status {status}")
    if authority_is_protected(str(record.get("authority"))):
        raise RiskConcernError(f"acceptance {record['acceptance_id']} uses AI/tool protected authority")
    if str(record['authority']).strip().upper() in {'UNKNOWN','ROLE GAP','ROLE_GAP','NONE','N/A','UNASSIGNED'}:
        raise RiskConcernError('acceptance requires a named accountable human')
    approved_at = parse_time(str(record["approved_at"]))
    expires_at = parse_time(str(record["expires_at"]))
    if approved_at > now or expires_at <= approved_at:
        raise RiskConcernError('acceptance approval/expiration chronology is invalid')

    if status == "ACTIVE" and expires_at <= now:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} is expired but marked ACTIVE")
    if status == "REVOKED":
        for field in ("revoked_at", "revoked_by", "revocation_reason"):
            if not record.get(field):
                raise RiskConcernError(f"revoked acceptance {record['acceptance_id']} missing {field}")
        revoked_at = parse_time(str(record["revoked_at"]))
        if revoked_at < approved_at or revoked_at > now:
            raise RiskConcernError('acceptance revocation chronology is invalid')
        if authority_is_protected(str(record.get("revoked_by"))):
            raise RiskConcernError(f"revoked acceptance {record['acceptance_id']} uses AI/tool revoking authority")

    current_requested = bool(record.get("current_authority"))
    current = status == "ACTIVE" and expires_at > now and not acceptance_stale_reasons(record)
    if current_requested and not current:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} cannot be current authority in status {status}")
    return current


def acceptance_scope(record: dict[str, Any]) -> str:
    """Bind approval to acceptance content, including residual exposure."""
    fields=('acceptance_id','risk_definition_id','definition_version','risk_assessment_id','project_id','scope','scope_hash','authority','reason','residual_risk','compensating_controls','readiness_requirement_ids','approved_at','expires_at','review_trigger')
    payload={field:record.get(field) for field in fields}
    return 'risk-acceptance:' + hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_acceptance_authority(record: dict[str, Any], approval_root: Path | None, *, now: datetime | None = None) -> bool:
    """Resolve explicit approval in the existing PREOS human approval store."""
    from runtime_state import load_approvals, authority_is_human
    now = now or datetime.now(timezone.utc)
    if not validate_acceptance_record(record, now=now): return False
    if approval_root is None: raise RiskConcernError('durable PREOS human approval store is required')
    for field in ('project_id','approval_id','residual_risk'):
        if not record.get(field): raise RiskConcernError('acceptance missing '+field)
    if not isinstance(record.get('compensating_controls'),list):
        raise RiskConcernError('compensating_controls must be explicitly recorded, including an empty list')
    state=load_approvals(Path(approval_root),record['project_id'])
    if state.get('project_id')!=record['project_id']: raise RiskConcernError('approval project mismatch')
    approval=next((a for a in state['approvals'] if a['approval_id']==record['approval_id']),None)
    if not approval or approval.get('status')!='GRANTED' or approval.get('approval_type')!='RISK_ACCEPTANCE':
        raise RiskConcernError('explicit human risk acceptance approval is missing')
    if approval.get('scope')!=acceptance_scope(record): raise RiskConcernError('acceptance changed since human approval')
    if approval.get('authority')!=record['authority'] or not authority_is_human(approval['authority']) or not approval.get('rationale'):
        raise RiskConcernError('approval authority/rationale mismatch')
    if approval.get('revoked_at'): raise RiskConcernError('human approval was revoked')
    decided=parse_time(approval.get('updated_at'))
    if decided>now: raise RiskConcernError('human approval is in the future')
    if approval.get('expires_at') and parse_time(approval['expires_at'])<=now:
        raise RiskConcernError('human approval expired')
    return True


def validate_concern_runtime(data: dict[str, Any], *, approval_root: Path | None = None) -> dict[str, int]:
    definitions_raw = data.get("definitions", [])
    if not isinstance(definitions_raw, list):
        raise RiskConcernError("definitions must be an array")
    definitions: set[tuple[str, str]] = set()
    for item in definitions_raw:
        if not isinstance(item, dict):
            raise RiskConcernError("definition is not an object")
        key = definition_key(item)
        forbidden={'assurance_state','current_status','release_id','project_id','acceptance','risk_acceptance','evidence_freshness','existing_controls'}
        if forbidden.intersection(item) or forbidden.intersection(item.get('normalized_definition',{})):
            raise RiskConcernError('RiskDefinition contains mutable assessment/authority state')
        if key in definitions:
            raise RiskConcernError(f"duplicate RiskDefinition/version: {key[0]}@{key[1]}")
        definitions.add(key)
    if not definitions:
        raise RiskConcernError("at least one RiskDefinition is required")

    assessments: dict[str, tuple[str, str]] = {}
    for item in data.get("assessments", []):
        if not isinstance(item, dict):
            raise RiskConcernError("assessment is not an object")
        key = _require_definition_ref(item, definitions, "RiskAssessment")
        if any(field in item for field in ('normalized_definition','raw_source','definition_content_sha256')):
            raise RiskConcernError('RiskAssessment cannot overwrite source or definition truth')
        aid = item.get("risk_assessment_id")
        if not aid:
            raise RiskConcernError("RiskAssessment missing risk_assessment_id")
        if str(aid) in assessments:
            raise RiskConcernError(f"duplicate RiskAssessment: {aid}")
        assessments[str(aid)] = key

    for collection_name, id_field in (
        ("economics", "risk_economics_id"),
        ("evolutions", "risk_evolution_id"),
        ("evidence_bindings", "risk_evidence_id"),
    ):
        seen = set()
        for item in data.get(collection_name, []):
            if not isinstance(item, dict):
                raise RiskConcernError(f"{collection_name} item is not an object")
            key = _require_definition_ref(item, definitions, collection_name)
            if not item.get(id_field):
                raise RiskConcernError(f"{collection_name} item missing {id_field}")
            if item[id_field] in seen:
                raise RiskConcernError(f'duplicate {collection_name} identity: {item[id_field]}')
            seen.add(item[id_field])
            aid = item.get("risk_assessment_id")
            if aid:
                if str(aid) not in assessments:
                    raise RiskConcernError(f"{collection_name} item references missing RiskAssessment: {aid}")
                if assessments[str(aid)] != key:
                    raise RiskConcernError(f"{collection_name} item assessment/definition version mismatch: {aid}")

    evidence_records = {item['risk_evidence_id']: item for item in data.get('evidence_bindings', [])}
    for eid, item in evidence_records.items():
        if item.get('validity') not in {'CURRENT','STALE','EXPIRED','UNKNOWN'}:
            raise RiskConcernError('invalid evidence validity')
        seen = {eid}
        cursor = item
        while cursor.get('replacement_evidence_id'):
            replacement = cursor['replacement_evidence_id']
            if replacement not in evidence_records:
                raise RiskConcernError('replacement evidence reference is orphaned')
            if replacement in seen:
                raise RiskConcernError('replacement evidence history contains a cycle')
            target = evidence_records[replacement]
            if definition_key(target) != definition_key(item) or target.get('risk_assessment_id') != item.get('risk_assessment_id'):
                raise RiskConcernError('replacement evidence scope mismatch')
            seen.add(replacement)
            cursor = target

    current_acceptances = 0
    eligible_acceptances = 0
    seen_acceptances = set()
    for item in data.get("acceptances", []):
        if not isinstance(item, dict):
            raise RiskConcernError("acceptance is not an object")
        key = _require_definition_ref(item, definitions, "RiskAcceptance")
        aid = item.get("risk_assessment_id")
        if aid:
            if str(aid) not in assessments:
                raise RiskConcernError(f"RiskAcceptance references missing RiskAssessment: {aid}")
            if assessments[str(aid)] != key:
                raise RiskConcernError(f"RiskAcceptance assessment/definition version mismatch: {aid}")
        if item.get('acceptance_id') in seen_acceptances: raise RiskConcernError('duplicate RiskAcceptance identity')
        seen_acceptances.add(item.get('acceptance_id'))
        if validate_acceptance_record(item):
            eligible_acceptances += 1
            if approval_root is not None and verify_acceptance_authority(item,approval_root): current_acceptances += 1

    linked_definition_keys = {
        definition_key(item)
        for collection in ("assessments", "economics", "evolutions", "evidence_bindings", "acceptances")
        for item in data.get(collection, [])
        if isinstance(item, dict)
    }
    independent_definitions = len(definitions - linked_definition_keys)
    return {
        "definitions": len(definitions),
        "independent_definitions": independent_definitions,
        "assessments": len(assessments),
        "current_acceptances": current_acceptances,
        "temporally_eligible_acceptances": eligible_acceptances,
    }
