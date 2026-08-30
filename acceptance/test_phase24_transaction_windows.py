#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import time

PREOS_SKILLS = [
    "preos", "preos-project-init", "preos-risk-model", "preos-architecture-economics",
    "preos-production-plan", "preos-production-implement", "preos-production-learn",
]

class AcceptanceFailure(RuntimeError):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def entry_kind(path: Path) -> str:
    try:
        if hasattr(path, "is_junction") and path.is_junction():
            return "junction"
        if path.is_symlink():
            return "symlink"
        if path.is_dir():
            return "directory"
        if lexists(path):
            return "file"
        return "missing"
    except OSError:
        return "inaccessible"


def generated_gstack_entry(path: Path) -> bool:
    skill = path / "SKILL.md"
    if not skill.is_file():
        return False
    try:
        return "<!-- AUTO-GENERATED from" in skill.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def move_entry_with_retry(src: Path, dst: Path, *, log_lines: list[str], attempts: int = 20) -> None:
    if not lexists(src):
        return
    if lexists(dst):
        raise AcceptanceFailure(f"destination collision: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(1, attempts + 1):
        try:
            os.rename(src, dst)
            log_lines.append(f"MOVE PASS attempt={attempt} src={src} dst={dst}")
            return
        except (PermissionError, OSError) as exc:
            last = exc
            log_lines.append(f"MOVE RETRY attempt={attempt} src={src} dst={dst}: {exc!r}")
            time.sleep(min(0.01 * attempt, 0.05))
    raise AcceptanceFailure(f"rename failed after retries src={src} dst={dst} kind={entry_kind(src)} last={last!r}")


def determine_transaction_names(skills_dir: Path, candidate_skills: Path, generated_gstack: list[str]):
    desired = {"ai-product-delivery-blueprint", *PREOS_SKILLS, *generated_gstack}
    managed_existing = {"ai-web-delivery-blueprint", "ai-product-delivery-blueprint", *PREOS_SKILLS}
    for entry in list(skills_dir.iterdir()):
        name = entry.name
        if name.startswith("gstack-"):
            if name in desired:
                if entry_kind(entry) == "directory" and not generated_gstack_entry(entry):
                    raise AcceptanceFailure(f"user-owned collision: {name}")
                managed_existing.add(name)
            elif generated_gstack_entry(entry):
                managed_existing.add(name)
    return desired, managed_existing


def rollback_skill_transaction(skills_dir: Path, state: dict) -> str:
    previous: Path = state["previous"]
    failed_new: Path = state["failed_new"]
    log_lines = state["log_lines"]
    errors = []
    failed_new.mkdir(parents=True, exist_ok=True)
    for name in sorted(state.get("desired", set())):
        live = skills_dir / name
        if lexists(live):
            dst = failed_new / name
            if lexists(dst):
                dst = failed_new / f"{name}-{int(time.time()*1000)}"
            try:
                move_entry_with_retry(live, dst, log_lines=log_lines)
            except Exception as exc:
                errors.append(f"quarantine {name}: {exc}")
    if previous.exists():
        for old in sorted(previous.iterdir(), key=lambda p: p.name):
            live = skills_dir / old.name
            if lexists(live):
                errors.append(f"restore collision {old.name}")
                continue
            try:
                move_entry_with_retry(old, live, log_lines=log_lines)
            except Exception as exc:
                errors.append(f"restore {old.name}: {exc}")
    return "ROLLBACK_INCOMPLETE" if errors else "ROLLBACK_PASS"


def begin_skill_transaction(home: Path, skills_dir: Path, candidate_skills: Path, generated_gstack: list[str], run_id: str):
    desired, managed_existing = determine_transaction_names(skills_dir, candidate_skills, generated_gstack)
    missing = sorted(name for name in desired if not lexists(candidate_skills / name))
    if missing:
        raise AcceptanceFailure("candidate incomplete: " + ", ".join(missing))
    txn_root = home / "phase24-skill-transactions" / run_id
    previous = txn_root / "previous"; failed_new = txn_root / "failed-new"
    previous.mkdir(parents=True, exist_ok=True); failed_new.mkdir(parents=True, exist_ok=True)
    state = {"previous": previous, "failed_new": failed_new, "desired": set(desired), "promoted": set(), "log_lines": []}
    try:
        for name in sorted(managed_existing):
            src = skills_dir / name
            if lexists(src):
                move_entry_with_retry(src, previous / name, log_lines=state["log_lines"])
        for name in sorted(desired):
            move_entry_with_retry(candidate_skills / name, skills_dir / name, log_lines=state["log_lines"])
            state["promoted"].add(name)
        return state
    except Exception as exc:
        rb = rollback_skill_transaction(skills_dir, state)
        raise AcceptanceFailure(f"promotion failed: {exc}; rollback={rb}") from exc


def make_skill(root: Path, name: str, text: str, generated=False):
    d = root / name; d.mkdir(parents=True, exist_ok=True)
    prefix = "<!-- AUTO-GENERATED from windows-ci -->\n" if generated else ""
    (d / "SKILL.md").write_text(prefix + f"name: {name}\n{text}\n", encoding="utf-8")


def build_candidate(candidate: Path):
    names = {"ai-product-delivery-blueprint", *PREOS_SKILLS, "gstack-review", "gstack-qa"}
    for n in names:
        make_skill(candidate, n, "new", generated=n.startswith("gstack-"))
    return ["gstack-review", "gstack-qa"]


def assert_normal_transaction():
    with tempfile.TemporaryDirectory(prefix="txn-normal-") as td:
        base=Path(td); home=base/"home"; skills=home/"skills"; cand=base/"candidate"/"skills"
        skills.mkdir(parents=True); cand.mkdir(parents=True)
        make_skill(skills,"preos","old"); make_skill(skills,"unrelated-skill","keep")
        generated=build_candidate(cand)
        state=begin_skill_transaction(home,skills,cand,generated,"normal")
        assert (skills/"preos"/"SKILL.md").read_text().endswith("new\n")
        assert (skills/"unrelated-skill"/"SKILL.md").is_file()
        assert rollback_skill_transaction(skills,state)=="ROLLBACK_PASS"
        assert (skills/"preos"/"SKILL.md").read_text().endswith("old\n")
        assert (skills/"unrelated-skill"/"SKILL.md").is_file()


def assert_injected_permission_failure():
    with tempfile.TemporaryDirectory(prefix="txn-perm-") as td:
        base=Path(td); home=base/"home"; skills=home/"skills"; cand=base/"candidate"/"skills"
        skills.mkdir(parents=True); cand.mkdir(parents=True)
        make_skill(skills,"preos","old"); make_skill(skills,"unrelated-skill","keep")
        generated=build_candidate(cand)
        real_rename=os.rename
        injected={"done":False}
        def fail_once(src,dst):
            srcp=Path(src)
            if srcp.parent==cand and srcp.name=="preos-risk-model" and not injected["done"]:
                injected["done"]=True
                raise PermissionError(13,"windows-ci injected access denied")
            return real_rename(src,dst)
        os.rename=fail_once
        try:
            try:
                begin_skill_transaction(home,skills,cand,generated,"injected")
                raise AssertionError("injected PermissionError did not fail transaction")
            except AcceptanceFailure as exc:
                assert "rollback=ROLLBACK_PASS" in str(exc), str(exc)
        finally:
            os.rename=real_rename
        assert (skills/"preos"/"SKILL.md").read_text().endswith("old\n")
        assert (skills/"unrelated-skill"/"SKILL.md").is_file()


def assert_user_owned_collision():
    with tempfile.TemporaryDirectory(prefix="txn-collision-") as td:
        base=Path(td); home=base/"home"; skills=home/"skills"; cand=base/"candidate"/"skills"
        skills.mkdir(parents=True); cand.mkdir(parents=True)
        make_skill(skills,"gstack-review","user-owned",generated=False)
        generated=build_candidate(cand)
        try:
            begin_skill_transaction(home,skills,cand,generated,"collision")
            raise AssertionError("user-owned gstack collision was not blocked")
        except AcceptanceFailure as exc:
            assert "user-owned collision" in str(exc)
        assert (skills/"gstack-review"/"SKILL.md").read_text().endswith("user-owned\n")


def main():
    assert os.name=="nt", "This acceptance test must run on Windows"
    assert_normal_transaction()
    assert_injected_permission_failure()
    assert_user_owned_collision()
    print("WINDOWS_TRANSACTION_TEST_PASS")

if __name__=="__main__":
    main()
