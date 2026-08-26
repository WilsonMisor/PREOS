#!/usr/bin/env python3
"""Deterministic PREOS runtime continuity and recovery primitives."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from preos_common import runtime_root
from schema_validation import SchemaValidationError, validate_file, validate_instance, load_schema
from state_machine import CANONICAL_EVENTS, STATE_SET, require_transition, validate_event, validate_state

PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
AI_AUTHORITY_WORDS = {"AI", "CODEX", "GSTACK", "LLM", "AGENT", "PREOS"}
NON_AUTHORITY_VALUES = {"", "ROLE GAP", "ROLE_GAP", "MISSING", "UNKNOWN", "UNASSIGNED", "NONE", "N/A"}
APPROVAL_STATUSES = {"PENDING", "GRANTED", "DENIED"}
SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing ISO-8601 timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value}") from exc
    if dt.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return dt.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, data); os.fsync(fd)
    finally:
        os.close(fd)


def validate_project_id(project_id: str) -> str:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("project_id may contain only letters, numbers, dot, underscore and hyphen")
    return project_id


def production_root(project_id: str) -> Path:
    return runtime_root() / "projects" / validate_project_id(project_id) / "production"


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def _changed_paths(repo: Path) -> list[dict]:
    proc = run_git(repo, "status", "--porcelain=v1", "-z")
    parts = proc.stdout.split("\0"); entries: list[dict] = []; i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1; continue
        status = item[:2]; path_text = item[3:]
        if status[0] in {"R", "C"} and i + 1 < len(parts) and parts[i + 1]:
            old_path = path_text; i += 1; path_text = parts[i]
        else:
            old_path = None
        file_path = repo / path_text
        digest = sha256_file(file_path) if file_path.is_file() and not file_path.is_symlink() else None
        entries.append({"status": status, "path": path_text, "old_path": old_path, "sha256": digest})
        i += 1
    return sorted(entries, key=lambda x: (x["path"], x["status"]))


def git_snapshot(repo: Path) -> dict:
    repo = repo.resolve()
    top = Path(run_git(repo, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    head = run_git(top, "rev-parse", "HEAD").stdout.strip()
    branch_proc = run_git(top, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "DETACHED"
    files = _changed_paths(top)
    fingerprint = sha256_json(files)
    return {"repo_root": str(top), "branch": branch, "head": head, "working_tree": files,
            "working_tree_fingerprint": fingerprint, "clean": len(files) == 0}


def file_binding(path: Path, repo: Path) -> dict:
    p = path.expanduser()
    if not p.is_absolute(): p = repo / p
    p = p.resolve()
    if not p.is_file(): raise FileNotFoundError(str(p))
    try: display = p.relative_to(repo.resolve()).as_posix()
    except ValueError: display = str(p)
    return {"path": display, "sha256": sha256_file(p)}


def file_bindings(paths: list[Path], repo: Path) -> list[dict]:
    return [file_binding(p, repo) for p in paths]


def environment_binding(names: list[str]) -> dict:
    names = sorted({str(n) for n in names if str(n)})
    material = {name: os.environ.get(name) for name in names}
    return {"variables": names, "sha256": sha256_json(material)}


def resolve_bound_path(path_text: str, repo: Path) -> Path:
    p = Path(path_text).expanduser()
    if not p.is_absolute(): p = repo / p
    return p.resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_current_state(path: Path) -> dict:
    data = validate_file(path, SCHEMAS / "current-state.schema.json")
    parse_time(data["updated_at"])
    if data.get("pipeline_state"):
        validate_state(str(data["pipeline_state"]))
    return data


def load_latest_state(root: Path) -> tuple[dict, Path, list[str]]:
    """Load newest schema-valid current/checkpoint state by persisted timestamp."""
    candidates: list[tuple[datetime, int, str, Path, dict]] = []
    corrupt: list[str] = []
    checkpoints = root / "checkpoints"
    if checkpoints.exists():
        for path in sorted(checkpoints.glob("*.json")):
            try:
                data = _validate_current_state(path)
                if not data.get("checkpoint_id") or not data.get("checkpoint_kind"):
                    raise ValueError("checkpoint file lacks checkpoint identity/kind")
                if path.stem != str(data["checkpoint_id"]):
                    raise ValueError(f"checkpoint filename/id mismatch: {path.name} != {data['checkpoint_id']}")
                candidates.append((parse_time(data["updated_at"]), 0, str(data["checkpoint_id"]), path, data))
            except Exception as exc:
                corrupt.append(f"{path}: {exc}")
    current = root / "CURRENT-STATE.json"
    if current.exists():
        try:
            data = _validate_current_state(current)
            candidates.append((parse_time(data["updated_at"]), 1, str(data.get("checkpoint_id") or current.name), current, data))
        except Exception as exc:
            corrupt.append(f"{current}: {exc}")
    if corrupt:
        raise ValueError("corrupt PREOS state/checkpoint: " + "; ".join(corrupt))
    if not candidates:
        raise FileNotFoundError("No recoverable PREOS state found; do not invent state from conversation memory.")
    _, _, _, path, data = max(candidates, key=lambda x: (x[0], x[1], x[2]))
    return data, path, []


def load_pipeline_state(root: Path, *, required: bool) -> dict | None:
    path = root / "PIPELINE-STATE.json"
    if not path.exists():
        if required: raise FileNotFoundError("PIPELINE-STATE.json is missing")
        return None
    data = load_json(path)
    if str(data.get("schema_version")) == "1.2":
        data = validate_file(path, SCHEMAS / "pipeline-state.schema.json")
        parse_time(data["updated_at"]); parse_time(data["last_transition"])
        validate_state(str(data["state"]))
    else:
        # Legacy 1.1 state remains readable for migration but is never treated as
        # proof of the new state-machine contract.
        if not isinstance(data, dict) or not data.get("project_id") or not data.get("updated_at"):
            raise ValueError("legacy PIPELINE-STATE.json is invalid")
        parse_time(str(data["updated_at"]))
    return data


def _ledger_checkpoint(root: Path, checkpoint_id: str) -> dict:
    path = root / "checkpoints" / f"{checkpoint_id}.json"
    if not path.is_file():
        raise ValueError(f"ledger references missing checkpoint: {checkpoint_id}")
    return _validate_current_state(path)


def load_ledger(root: Path, project_id: str) -> list[dict]:
    """Validate JSONL parse, IDs, references and canonical state/event sequence."""
    path = root / "implementation-ledger.jsonl"
    if not path.exists(): return []
    events: list[dict] = []; seen: set[str] = set(); previous_time: datetime | None = None
    previous_state: str | None = None
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip(): continue
        try: event = json.loads(raw)
        except json.JSONDecodeError as exc: raise ValueError(f"ledger line {line_no} is corrupt JSON") from exc
        if not isinstance(event, dict): raise ValueError(f"ledger line {line_no} is not an object")
        for field in ("event_id", "timestamp", "event_type", "project_id"):
            if not event.get(field): raise ValueError(f"ledger line {line_no} missing {field}")
        if event["project_id"] != project_id: raise ValueError(f"ledger line {line_no} project_id mismatch")
        event_id = str(event["event_id"])
        if event_id in seen: raise ValueError(f"duplicate ledger event_id: {event_id}")
        seen.add(event_id)
        when = parse_time(str(event["timestamp"]))
        if previous_time and when < previous_time: raise ValueError(f"ledger timestamp moved backwards at line {line_no}")
        previous_time = when
        et = str(event["event_type"])
        if et not in CANONICAL_EVENTS:
            raise ValueError(f"ledger line {line_no} has unknown event_type {et}")
        checkpoint_id = event.get("checkpoint_id")
        if checkpoint_id and ("CHECKPOINT" in et or et in {"SESSION_INTERRUPTED", "IMPLEMENTATION_COMPLETE"}):
            cp = _ledger_checkpoint(root, str(checkpoint_id))
            if event.get("task_packet_id") and cp.get("task_packet_id") and event["task_packet_id"] != cp["task_packet_id"]:
                raise ValueError(f"ledger/checkpoint task packet mismatch at line {line_no}")
            if et == "HARD_CHECKPOINT" and cp.get("checkpoint_kind") != "HARD":
                raise ValueError(f"ledger HARD_CHECKPOINT references non-hard checkpoint at line {line_no}")
        state_value = event.get("pipeline_state")
        if state_value:
            validate_state(str(state_value))
            if previous_state:
                require_transition(previous_state, str(state_value))
            prior_declared = event.get("previous_pipeline_state")
            if prior_declared and previous_state and prior_declared != previous_state:
                raise ValueError(f"ledger previous_pipeline_state mismatch at line {line_no}")
            previous_state = str(state_value)
        events.append(event)
    return events


def source_binding_conflicts(contract: dict, repo: Path) -> list[dict]:
    conflicts: list[dict] = []
    source_hashes = contract.get("source_hashes", [])
    if not isinstance(source_hashes, list): return [{"type": "SOURCE_BINDINGS_INVALID", "detail": "source_hashes is not an array"}]
    for item in source_hashes:
        if not isinstance(item, dict): conflicts.append({"type": "SOURCE_BINDING_INVALID", "artifact": None}); continue
        artifact = item.get("artifact") or item.get("path"); expected = item.get("sha256")
        if not artifact or not expected: conflicts.append({"type": "SOURCE_BINDING_INVALID", "artifact": artifact}); continue
        path = resolve_bound_path(str(artifact), repo)
        if not path.is_file(): conflicts.append({"type": "SOURCE_MISSING", "artifact": artifact}); continue
        actual = sha256_file(path)
        if actual != expected: conflicts.append({"type": "SOURCE_HASH_MISMATCH", "artifact": artifact, "expected": expected, "actual": actual})
    return conflicts


def binding_conflict(label: str, binding: dict | None, repo: Path) -> dict | None:
    if not binding: return None
    if not isinstance(binding, dict): return {"type": f"{label}_BINDING_INVALID"}
    path_text = binding.get("path"); expected = binding.get("sha256")
    if not path_text or not expected: return {"type": f"{label}_BINDING_INVALID"}
    path = resolve_bound_path(str(path_text), repo)
    if not path.is_file(): return {"type": f"{label}_MISSING", "path": path_text}
    actual = sha256_file(path)
    if actual != expected: return {"type": f"{label}_HASH_MISMATCH", "path": path_text, "expected": expected, "actual": actual}
    return None


def _file_list_changed(bindings: Any, repo: Path) -> bool:
    if bindings in (None, []): return False
    if not isinstance(bindings, list): raise ValueError("file bindings must be an array")
    for binding in bindings:
        if binding_conflict("EVIDENCE_FILE", binding, repo): return True
    return False


def authority_is_ai(authority: str) -> bool:
    words = {w for w in re.split(r"[^A-Za-z0-9]+", str(authority).upper()) if w}
    return bool(words & AI_AUTHORITY_WORDS)


def authority_is_human(authority: str) -> bool:
    normalized = str(authority or "").strip().upper()
    if normalized in NON_AUTHORITY_VALUES: return False
    return not authority_is_ai(normalized)


def load_approvals(root: Path, project_id: str) -> dict:
    path = root / "approval-state.json"
    if not path.exists(): return {"project_id": project_id, "approvals": []}
    data = validate_file(path, SCHEMAS / "approval-state.schema.json")
    seen: set[str] = set()
    for idx, item in enumerate(data.get("approvals", []), 1):
        approval_id = str(item["approval_id"])
        if approval_id in seen: raise ValueError(f"duplicate approval_id: {approval_id}")
        seen.add(approval_id)
        status = str(item.get("status") or "")
        if status in {"GRANTED", "DENIED"} and not authority_is_human(str(item.get("authority") or "")):
            raise ValueError(f"approval {approval_id} has non-human consequential authority")
    return data


def _evidence_expired(item: dict) -> bool:
    until = item.get("valid_until")
    if not until: return False
    return parse_time(str(until)) < datetime.now(timezone.utc)


def evidence_binding_reasons(item: dict, actual_git: dict, repo: Path) -> list[str]:
    reasons: list[str] = []
    bindings = item.get("bindings", {})
    if not isinstance(bindings, dict): raise ValueError("evidence bindings are invalid")
    expected_head = bindings.get("git_head") or item.get("commit_sha")
    if expected_head and expected_head != actual_git["head"]: reasons.append("commit changed")
    for label in ("project_contract", "task_packet"):
        b = bindings.get(label)
        if b and binding_conflict(label.upper(), b, repo): reasons.append(f"{label} changed")
    source_hashes = bindings.get("source_hashes", [])
    if source_hashes:
        if not isinstance(source_hashes, list): raise ValueError("source_hashes binding is invalid")
        for source in source_hashes:
            path_text = source.get("path") or source.get("artifact") if isinstance(source, dict) else None
            expected = source.get("sha256") if isinstance(source, dict) else None
            if not path_text or not expected: raise ValueError("source binding is invalid")
            p = resolve_bound_path(str(path_text), repo)
            if not p.is_file() or sha256_file(p) != expected:
                reasons.append("source changed"); break
    for key, label in (
        ("configuration_files", "configuration changed"),
        ("schema_files", "schema changed"),
        ("dependency_files", "dependency versions changed"),
        ("test_definition_files", "test definition changed"),
    ):
        if _file_list_changed(bindings.get(key, []), repo): reasons.append(label)
    env = bindings.get("environment")
    if env:
        if not isinstance(env, dict) or not isinstance(env.get("variables", []), list) or not env.get("sha256"):
            raise ValueError("environment binding is invalid")
        current = environment_binding([str(x) for x in env["variables"]])
        if current["sha256"] != env["sha256"]: reasons.append("environment changed")
    if _evidence_expired(item): reasons.append("validity period expired")
    return reasons


def stale_evidence(root: Path, actual_git: dict, state: dict, repo: Path) -> list[str]:
    path = root / "evidence-index.json"
    if not path.exists(): return []
    data = validate_file(path, SCHEMAS / "evidence-index.schema.json")
    stale: list[str] = []; seen: set[str] = set()
    for item in data.get("evidence", []):
        eid = str(item.get("evidence_id") or "")
        if eid in seen: raise ValueError(f"duplicate evidence_id: {eid}")
        seen.add(eid)
        explicit = str(item.get("validity") or item.get("status") or "").upper()
        if explicit in {"STALE", "EXPIRED"}:
            stale.append(eid); continue
        if evidence_binding_reasons(item, actual_git, repo): stale.append(eid)
    return sorted(set(stale))


def _approval_outcome(state: dict, approvals: dict) -> tuple[list[str], list[str], list[str]]:
    records = {str(a["approval_id"]): a for a in approvals.get("approvals", [])}
    required = state.get("required_approval_ids", []) or []
    if not isinstance(required, list): raise ValueError("required_approval_ids must be an array")
    missing: list[str] = []; pending: list[str] = []; denied: list[str] = []
    if required:
        for aid in sorted({str(x) for x in required}):
            item = records.get(aid)
            if item is None: missing.append(aid)
            elif item.get("status") == "PENDING": pending.append(aid)
            elif item.get("status") == "DENIED": denied.append(aid)
    else:
        pending = sorted(str(a["approval_id"]) for a in approvals.get("approvals", []) if a.get("status") == "PENDING")
    return missing, pending, denied


def _pipeline_conflicts(pipeline: dict | None, state: dict, actual_git: dict) -> list[dict]:
    conflicts: list[dict] = []
    strict = str(state.get("schema_version")) == "1.2"
    if pipeline is None:
        if strict: conflicts.append({"type": "PIPELINE_STATE_MISSING"})
        return conflicts
    if str(pipeline.get("schema_version")) != "1.2":
        if strict: conflicts.append({"type": "PIPELINE_STATE_LEGACY", "actual": pipeline.get("schema_version")})
        return conflicts
    pairs = [
        ("project_id", "project_id", "PIPELINE_PROJECT_ID_MISMATCH"),
        ("project_contract_version", "project_contract_version", "PIPELINE_CONTRACT_VERSION_MISMATCH"),
        ("current_task_packet", "task_packet_id", "PIPELINE_TASK_PACKET_MISMATCH"),
        ("last_checkpoint_id", "checkpoint_id", "PIPELINE_CHECKPOINT_MISMATCH"),
        ("last_verified_action", "last_verified_action", "PIPELINE_LAST_VERIFIED_MISMATCH"),
        ("next_unverified_action", "next_unverified_action", "PIPELINE_NEXT_ACTION_MISMATCH"),
        ("pending_test", "pending_test", "PIPELINE_PENDING_TEST_MISMATCH"),
        ("pending_build", "pending_build", "PIPELINE_PENDING_BUILD_MISMATCH"),
        ("pending_migration", "pending_migration", "PIPELINE_PENDING_MIGRATION_MISMATCH"),
        ("pending_evidence", "pending_evidence", "PIPELINE_PENDING_EVIDENCE_MISMATCH"),
    ]
    for pkey, skey, ctype in pairs:
        pv, sv = pipeline.get(pkey), state.get(skey)
        if pv != sv and not (pv is None and sv is None): conflicts.append({"type": ctype, "pipeline": pv, "state": sv})
    expected_state = state.get("pipeline_state")
    if expected_state and pipeline.get("state") != expected_state:
        conflicts.append({"type": "PIPELINE_STATE_MISMATCH", "pipeline": pipeline.get("state"), "state": expected_state})
    for pkey, actual_key, ctype in (
        ("git_branch", "branch", "PIPELINE_BRANCH_MISMATCH"),
        ("git_head", "head", "PIPELINE_HEAD_MISMATCH"),
        ("working_tree_fingerprint", "working_tree_fingerprint", "PIPELINE_WORKTREE_MISMATCH"),
    ):
        if pipeline.get(pkey) and pipeline[pkey] != actual_git[actual_key]:
            conflicts.append({"type": ctype, "pipeline": pipeline[pkey], "actual": actual_git[actual_key]})
    return conflicts


def reconcile_project(project_id: str, repo: Path) -> dict:
    root = production_root(project_id)
    state, state_source, _ = load_latest_state(root)
    repo = repo.resolve(); actual_git = git_snapshot(repo); conflicts: list[dict] = []
    strict = str(state.get("schema_version")) == "1.2"
    try: pipeline = load_pipeline_state(root, required=strict)
    except Exception as exc:
        conflicts.append({"type": "PIPELINE_STATE_INVALID", "detail": str(exc)}); pipeline = None
    conflicts.extend(_pipeline_conflicts(pipeline, state, actual_git))

    ledger_valid = True
    try: ledger = load_ledger(root, project_id)
    except Exception as exc:
        conflicts.append({"type": "LEDGER_INVALID", "detail": str(exc)}); ledger = []; ledger_valid = False

    if state.get("project_id") != project_id:
        conflicts.append({"type": "STATE_PROJECT_ID_MISMATCH", "expected": project_id, "actual": state.get("project_id")})
    expected_git = state.get("git") or {}
    if expected_git:
        if expected_git.get("repo_root") and Path(expected_git["repo_root"]).resolve() != Path(actual_git["repo_root"]):
            conflicts.append({"type": "REPOSITORY_MISMATCH", "expected": expected_git.get("repo_root"), "actual": actual_git["repo_root"]})
        if expected_git.get("branch") and expected_git.get("branch") != actual_git["branch"]:
            conflicts.append({"type": "BRANCH_MISMATCH", "expected": expected_git.get("branch"), "actual": actual_git["branch"]})
        if expected_git.get("head") and expected_git.get("head") != actual_git["head"]:
            conflicts.append({"type": "HEAD_MISMATCH", "expected": expected_git.get("head"), "actual": actual_git["head"]})
        if expected_git.get("working_tree_fingerprint") and expected_git.get("working_tree_fingerprint") != actual_git["working_tree_fingerprint"]:
            conflicts.append({"type": "WORKING_TREE_MISMATCH", "expected": expected_git.get("working_tree"), "actual": actual_git["working_tree"]})

    bindings = state.get("bindings", {})
    if not isinstance(bindings, dict): conflicts.append({"type": "STATE_BINDINGS_INVALID"}); bindings = {}
    for label in ("project_contract", "task_packet"):
        conflict = binding_conflict(label.upper(), bindings.get(label), repo)
        if conflict: conflicts.append(conflict)
    contract_binding = bindings.get("project_contract")
    if contract_binding and not any(c["type"].startswith("PROJECT_CONTRACT") for c in conflicts):
        contract_path = resolve_bound_path(str(contract_binding["path"]), repo)
        try:
            contract = load_json(contract_path)
            if not isinstance(contract, dict): raise ValueError("Project Contract is not an object")
            conflicts.extend(source_binding_conflicts(contract, repo))
        except Exception as exc:
            conflicts.append({"type": "PROJECT_CONTRACT_INVALID", "detail": str(exc)})

    try:
        approvals = load_approvals(root, project_id)
        missing_approvals, pending_approvals, denied_approvals = _approval_outcome(state, approvals)
    except Exception as exc:
        conflicts.append({"type": "APPROVAL_STATE_INVALID", "detail": str(exc)})
        missing_approvals, pending_approvals, denied_approvals = [], [], []
    try: stale = stale_evidence(root, actual_git, state, repo)
    except Exception as exc:
        conflicts.append({"type": "EVIDENCE_INDEX_INVALID", "detail": str(exc)}); stale = []

    if state.get("pending_migration"):
        conflicts.append({"type": "MIGRATION_STATE_UNCERTAIN", "migration": state["pending_migration"],
                          "detail": "external database state must be reconciled before migration execution can resume"})

    last_verified = state.get("last_verified_action")
    next_unverified = state.get("next_unverified_action") or "reconcile next approved task action"
    if state.get("pending_test"): next_unverified = f"re-run uncertain test: {state['pending_test']}"
    elif state.get("pending_build"): next_unverified = f"re-run uncertain build: {state['pending_build']}"
    elif stale: next_unverified = f"revalidate stale evidence: {', '.join(stale)}"
    elif state.get("pending_evidence"): next_unverified = f"capture pending evidence: {state['pending_evidence']}"

    if conflicts: status = "RECOVERY_CONFLICT"
    elif missing_approvals or pending_approvals or denied_approvals: status = "BLOCKED"
    else: status = "SAFE_TO_RESUME"

    recovered_at = utc_now()
    result = {
        "status": status, "project_id": project_id, "state_source": str(state_source),
        "pipeline_state": pipeline.get("state") if pipeline else state.get("pipeline_state"),
        "project_contract_version": state.get("project_contract_version"), "task_packet_id": state.get("task_packet_id"),
        "git": actual_git, "last_verified_action": last_verified, "next_unverified_action": next_unverified,
        "missing_approvals": missing_approvals, "pending_approvals": pending_approvals, "denied_approvals": denied_approvals,
        "stale_evidence": stale, "ledger_events_validated": len(ledger), "conflicts": conflicts, "recovered_at": recovered_at,
    }
    append_jsonl(root / "recovery-events.jsonl", result)
    if ledger_valid:
        token = re.sub(r"[^0-9]", "", recovered_at)
        current_pipeline = pipeline.get("state") if pipeline and pipeline.get("state") in STATE_SET else state.get("pipeline_state")
        append_jsonl(root / "implementation-ledger.jsonl", {
            "event_id": f"RECOVERY-{token}-START", "timestamp": recovered_at, "event_type": "RECOVERY_STARTED",
            "project_id": project_id, "task_packet_id": state.get("task_packet_id"), "checkpoint_id": state.get("checkpoint_id"),
            "pipeline_state": current_pipeline,
        })
        completed_at = utc_now()
        append_jsonl(root / "implementation-ledger.jsonl", {
            "event_id": f"RECOVERY-{re.sub(r'[^0-9]', '', completed_at)}-{status}", "timestamp": completed_at,
            "event_type": "RECOVERY_COMPLETED" if status == "SAFE_TO_RESUME" else ("RECOVERY_CONFLICT" if status == "RECOVERY_CONFLICT" else "RECOVERY_BLOCKED"),
            "project_id": project_id, "task_packet_id": state.get("task_packet_id"), "checkpoint_id": state.get("checkpoint_id"),
            "recovery_status": status, "next_unverified_action": next_unverified, "pipeline_state": current_pipeline,
        })
    return result
