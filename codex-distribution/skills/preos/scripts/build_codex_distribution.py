#!/usr/bin/env python3
"""Build and validate the PREOS Codex distribution tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "codex-distribution"
MANIFEST = ROOT / "CODEX-DISTRIBUTION.json"

SKILLS = [
    {"name": "preos", "source_path": "codex-distribution/skills/preos", "implicit_invocation": True},
    {"name": "preos-architecture-economics", "source_path": "codex-distribution/skills/preos-architecture-economics"},
    {"name": "preos-production-implement", "source_path": "codex-distribution/skills/preos-production-implement"},
    {"name": "preos-production-learn", "source_path": "codex-distribution/skills/preos-production-learn"},
    {"name": "preos-production-plan", "source_path": "codex-distribution/skills/preos-production-plan"},
    {"name": "preos-project-init", "source_path": "codex-distribution/skills/preos-project-init"},
    {"name": "preos-risk-model", "source_path": "codex-distribution/skills/preos-risk-model"},
]

ROOT_SKILL_ITEMS = [
    "SKILL.md",
    "agents",
    "docs",
    "references",
    "schemas",
    "scripts",
    "source-package",
    "templates",
    "ARCHITECTURE.md",
    "ETHOS.md",
    "INTEGRATION-CONTRACT.md",
    "MANIFEST.json",
    "RECOMMENDATION-COVERAGE.md",
    "SOURCE-CONCEPT-COVERAGE.md",
    "VERSION",
]

SUBSKILLS = [
    "preos-architecture-economics",
    "preos-production-implement",
    "preos-production-learn",
    "preos-production-plan",
    "preos-project-init",
    "preos-risk-model",
]

IGNORE_NAMES = {"__pycache__", ".pytest_cache", ".preos-runtime", "PREOS_STATE_ROOT"}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".log"}


def ignore_runtime(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORE_NAMES or any(name.endswith(suffix) for suffix in IGNORE_SUFFIXES):
            ignored.add(name)
    return ignored


def copy_item(rel: str, dest_root: Path, target_rel: str | None = None) -> None:
    src = ROOT / rel
    if not src.exists():
        raise SystemExit(f"missing source artifact: {rel}")
    dst = dest_root / (target_rel if target_rel is not None else Path(rel).name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore_runtime)
    else:
        shutil.copy2(src, dst)


def frontmatter_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise SystemExit(f"SKILL.md lacks frontmatter: {skill_md}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SystemExit(f"malformed frontmatter: {skill_md}")
    match = re.search(r"(?mi)^name\s*:\s*['\"]?([^'\"\r\n]+)", parts[1])
    if not match:
        raise SystemExit(f"frontmatter lacks name: {skill_md}")
    return match.group(1).strip()


def manifest() -> dict:
    return {
        "schema_version": "1.0",
        "repository": "WilsonMisor/PREOS",
        "component": "preos-production-assurance",
        "skills": SKILLS,
        "agents": [],
    }


def build_tree(target: Path) -> dict:
    skill_root = target / "skills"
    preos_root = skill_root / "preos"
    for item in ROOT_SKILL_ITEMS:
        copy_item(item, preos_root)
    for name in SUBSKILLS:
        dest = skill_root / name
        copy_item(f"{name}/SKILL.md", dest, "SKILL.md")
        agents = ROOT / name / "agents"
        if agents.exists():
            copy_item(f"{name}/agents", dest, "agents")
    data = manifest()
    validate_distribution(target, data)
    return data


def validate_distribution(target: Path, data: dict) -> None:
    seen: set[str] = set()
    for item in data["skills"]:
        name = item["name"]
        if name in seen:
            raise SystemExit(f"duplicate skill name: {name}")
        seen.add(name)
        src = ROOT / item["source_path"] if target == DIST else target / Path(item["source_path"]).relative_to("codex-distribution")
        if not src.is_dir():
            raise SystemExit(f"declared skill source missing: {item['source_path']}")
        actual = frontmatter_name(src / "SKILL.md")
        if actual != name:
            raise SystemExit(f"skill name mismatch for {item['source_path']}: manifest={name}, SKILL.md={actual}")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    files: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files[path.relative_to(root).as_posix()] = file_hash(path)
    return files


def compare_tree(expected_root: Path) -> list[str]:
    expected = snapshot(expected_root)
    current = snapshot(DIST)
    diffs: list[str] = []
    for rel in sorted(set(expected) | set(current)):
        if rel not in current:
            diffs.append(f"missing: {rel}")
        elif rel not in expected:
            diffs.append(f"extra: {rel}")
        elif current[rel] != expected[rel]:
            diffs.append(f"changed: {rel}")
    return diffs


def write_manifest(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated distribution is stale")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="preos-codex-distribution-") as td:
        expected = Path(td) / "codex-distribution"
        data = build_tree(expected)
        manifest_text = write_manifest(data)
        if args.check:
            diffs = compare_tree(expected)
            if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8-sig") != manifest_text:
                diffs.insert(0, "changed: CODEX-DISTRIBUTION.json")
            if diffs:
                print("PREOS Codex distribution is stale:")
                for diff in diffs[:50]:
                    print(f"- {diff}")
                return 1
            print("PREOS Codex distribution is fresh")
            return 0

        if DIST.exists():
            shutil.rmtree(DIST)
        shutil.copytree(expected, DIST)
        MANIFEST.write_text(manifest_text, encoding="utf-8")
        print(f"wrote {MANIFEST.relative_to(ROOT)}")
        print(f"wrote {DIST.relative_to(ROOT)}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
