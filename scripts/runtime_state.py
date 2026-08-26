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

PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
AI_AUTHORITY_WORDS = {"AI", "CODEX", "GSTACK", "LLM", "AGENT", "PREOS"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
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
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_project_id(project_id: str) -> str:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("project_id may contain only letters, numbers, dot, underscore and hyphen")
    return project_id


def production_root(project_id: str) -> Path:
    return runtime_root() / "projects" / validate_project_id(project_id) / "production"


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _changed_paths(repo: Path) -> list[dict]:
    proc = run_git(repo, "status", "--porcelain=v1", "-z")
    raw = proc.stdout
    entries: list[dict] = []
    parts = raw.split("\0")
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue
        status = item[:2]
        path_text = item[3:]
        if status[0] in {"R", "C"} and i + 1 < len(parts) and parts[i + 1]:
            old_path = path_text
            i += 1
            path_text = parts[i]
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
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "repo_root": str(top),
        "branch": branch,
        "head": head,
        "working_tree": files,
        "working_tree_fingerprint": fingerprint,
        "clean": len(files) == 0,
    }


def file_binding(path: Path, repo: Path) -> dict:
    p = path.expanduser()
    if not p.is_absolute():
        p = repo / p
    p = p.resolve()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    try:
        display = p.relative_to(repo.resolve()).as_posix()
    except ValueError:
        display = str(p)
    return {"path": display, "sha256": sha256_file(p)}


def resolve_bound_path(path_text: str, repo: Path) -> Path:
    p = Path(path_text).expanduser()
    if not p.is_absolute():
        p = repo / p
    return p.resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest_state(root: Path) -> tuple[dict, Path, list[str]]:
    checkpoints = root / "checkpoints"
    parse_errors: list[tuple[float, Path, str]] = []
    valid: list[tuple[float, Path, dict]] = []
    if checkpoints.exists():
        for path in checkpoints.glob("*.json"):
            try:
                valid.append((path.stat().st_mtime, path, load_json(path)))
            except Exception as exc:
                parse_errors.append((path.stat().st_mtime, path, str(exc)))
    current = root / "CURRENT-STATE.json"
    if current.exists():
        try:
            valid.append((current.stat().st_mtime, current, load_json(current)))
        except Exception as exc:
            parse_errors.append((current.stat().st_mtime, current, str(exc)))
    if not valid and parse_errors:
        newest = max(parse_errors, key=lambda x: x[0])
        raise ValueError(f"no valid state; corrupt state file {newest[1]}: {newest[2]}")
    if not valid:
        raise FileNotFoundError("No recoverable PREOS state found; do not invent state from conversation memory.")
    newest_valid = max(valid, key=lambda x: x[0])
    errors = [f"corrupt state ignored: {p}: {err}" for _, p, err in parse_errors if _ >= newest_valid[0]]
    if errors:
        raise ValueError("; ".join(errors))
    return newest_valid[2], newest_valid[1], []


def source_binding_conflicts(contract: dict, repo: Path) -> list[dict]:
    conflicts: list[dict] = []
    for item in contract.get("source_hashes", []):
        artifact = item.get("artifact")
        expected = item.get("sha256")
        if not artifact or not expected:
            conflicts.append({"type": "SOURCE_BINDING_INVALID", "artifact": artifact})
            continue
        path = resolve_bound_path(artifact, repo)
        if not path.is_file():
            conflicts.append({"type": "SOURCE_MISSING", "artifact": artifact})
            continue
        actual = sha256_file(path)
        if actual != expected:
            conflicts.append({"type": "SOURCE_HASH_MISMATCH", "artifact": artifact, "expected": expected, "actual": actual})
    return conflicts


def binding_conflict(label: str, binding: dict | None, repo: Path) -> dict | None:
    if not binding:
        return None
    path_text = binding.get("path")
    expected = binding.get("sha256")
    if not path_text or not expected:
        return {"type": f"{label}_BINDING_INVALID"}
    path = resolve_bound_path(path_text, repo)
    if not path.is_file():
        return {"type": f"{label}_MISSING", "path": path_text}
    actual = sha256_file(path)
    if actual != expected:
        return {"type": f"{label}_HASH_MISMATCH", "path": path_text, "expected": expected, "actual": actual}
    return None


def load_approvals(root: Path, project_id: str) -> dict:
    path = root / "approval-state.json"
    if not path.exists():
        return {"project_id": project_id, "approvals": []}
    data = load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("approvals", []), list):
        raise ValueError("approval-state.json is invalid")
    return data


def stale_evidence(root: Path, actual_git: dict, state: dict, repo: Path) -> list[str]:
    path = root / "evidence-index.json"
    if not path.exists():
        return []
    data = load_json(path)
    stale: list[str] = []
    for item in data.get("evidence", []):
        eid = str(item.get("evidence_id") or item.get("id") or "UNKNOWN-EVIDENCE")
        bindings = item.get("bindings", {})
        expected_head = bindings.get("git_head")
        if expected_head and expected_head != actual_git["head"]:
            stale.append(eid)
            continue
        for label in ("project_contract", "task_packet"):
            b = bindings.get(label)
            if b and binding_conflict(label.upper(), b, repo):
                stale.append(eid)
                break
    return sorted(set(stale))


def reconcile_project(project_id: str, repo: Path) -> dict:
    root = production_root(project_id)
    state, state_source, _ = load_latest_state(root)
    repo = repo.resolve()
    actual_git = git_snapshot(repo)
    conflicts: list[dict] = []

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
    for label in ("project_contract", "task_packet"):
        conflict = binding_conflict(label.upper(), bindings.get(label), repo)
        if conflict:
            conflicts.append(conflict)

    contract_binding = bindings.get("project_contract")
    if contract_binding and not any(c["type"].startswith("PROJECT_CONTRACT") for c in conflicts):
        contract_path = resolve_bound_path(contract_binding["path"], repo)
        try:
            contract = load_json(contract_path)
            conflicts.extend(source_binding_conflicts(contract, repo))
        except Exception as exc:
            conflicts.append({"type": "PROJECT_CONTRACT_INVALID", "detail": str(exc)})

    try:
        approvals = load_approvals(root, project_id)
    except Exception as exc:
        conflicts.append({"type": "APPROVAL_STATE_INVALID", "detail": str(exc)})
        approvals = {"approvals": []}

    pending = [str(a.get("approval_id") or "UNKNOWN") for a in approvals.get("approvals", []) if a.get("status") == "PENDING"]

    try:
        stale = stale_evidence(root, actual_git, state, repo)
    except Exception as exc:
        conflicts.append({"type": "EVIDENCE_INDEX_INVALID", "detail": str(exc)})
        stale = []

    last_verified = state.get("last_verified_action")
    next_unverified = state.get("next_unverified_action") or state.get("pending_test") or "reconcile next approved task action"
    if stale:
        next_unverified = f"revalidate stale evidence: {', '.join(stale)}"

    if conflicts:
        status = "RECOVERY_CONFLICT"
    elif pending:
        status = "BLOCKED"
    else:
        status = "SAFE_TO_RESUME"

    result = {
        "status": status,
        "project_id": project_id,
        "state_source": str(state_source),
        "project_contract_version": state.get("project_contract_version"),
        "task_packet_id": state.get("task_packet_id"),
        "git": actual_git,
        "last_verified_action": last_verified,
        "next_unverified_action": next_unverified,
        "pending_approvals": pending,
        "stale_evidence": stale,
        "conflicts": conflicts,
        "recovered_at": utc_now(),
    }
    append_jsonl(root / "recovery-events.jsonl", result)
    return result


def authority_is_ai(authority: str) -> bool:
    words = {w for w in re.split(r"[^A-Za-z0-9]+", authority.upper()) if w}
    return bool(words & AI_AUTHORITY_WORDS)
