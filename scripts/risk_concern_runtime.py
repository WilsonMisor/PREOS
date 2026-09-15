#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
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
    now = now or datetime.now(timezone.utc)
    for field in ("acceptance_id", "risk_definition_id", "definition_version", "authority", "reason", "scope", "approved_at", "expires_at", "review_trigger", "status"):
        if not record.get(field):
            raise RiskConcernError(f"acceptance missing {field}")
    status = str(record["status"]).upper()
    if status not in ACCEPTANCE_STATUSES:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} has invalid status {status}")
    if authority_is_protected(str(record.get("authority"))):
        raise RiskConcernError(f"acceptance {record['acceptance_id']} uses AI/tool protected authority")
    parse_time(str(record["approved_at"]))
    expires_at = parse_time(str(record["expires_at"]))

    if status == "ACTIVE" and expires_at <= now:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} is expired but marked ACTIVE")
    if status == "REVOKED":
        for field in ("revoked_at", "revoked_by", "revocation_reason"):
            if not record.get(field):
                raise RiskConcernError(f"revoked acceptance {record['acceptance_id']} missing {field}")
        parse_time(str(record["revoked_at"]))
        if authority_is_protected(str(record.get("revoked_by"))):
            raise RiskConcernError(f"revoked acceptance {record['acceptance_id']} uses AI/tool revoking authority")

    current_requested = bool(record.get("current_authority"))
    current = status == "ACTIVE" and expires_at > now and not acceptance_stale_reasons(record)
    if current_requested and not current:
        raise RiskConcernError(f"acceptance {record['acceptance_id']} cannot be current authority in status {status}")
    return current


def validate_concern_runtime(data: dict[str, Any]) -> dict[str, int]:
    definitions_raw = data.get("definitions", [])
    if not isinstance(definitions_raw, list):
        raise RiskConcernError("definitions must be an array")
    definitions: set[tuple[str, str]] = set()
    for item in definitions_raw:
        if not isinstance(item, dict):
            raise RiskConcernError("definition is not an object")
        key = definition_key(item)
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
        for item in data.get(collection_name, []):
            if not isinstance(item, dict):
                raise RiskConcernError(f"{collection_name} item is not an object")
            key = _require_definition_ref(item, definitions, collection_name)
            if not item.get(id_field):
                raise RiskConcernError(f"{collection_name} item missing {id_field}")
            aid = item.get("risk_assessment_id")
            if aid:
                if str(aid) not in assessments:
                    raise RiskConcernError(f"{collection_name} item references missing RiskAssessment: {aid}")
                if assessments[str(aid)] != key:
                    raise RiskConcernError(f"{collection_name} item assessment/definition version mismatch: {aid}")

    current_acceptances = 0
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
        if validate_acceptance_record(item):
            current_acceptances += 1

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
    }
