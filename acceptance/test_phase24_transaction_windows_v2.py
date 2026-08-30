#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_phase24_transaction_windows as tx


def assert_persistent_permission_failure():
    with tempfile.TemporaryDirectory(prefix="txn-persistent-perm-") as td:
        base=Path(td); home=base/"home"; skills=home/"skills"; cand=base/"candidate"/"skills"
        skills.mkdir(parents=True); cand.mkdir(parents=True)
        tx.make_skill(skills,"preos","old"); tx.make_skill(skills,"unrelated-skill","keep")
        generated=tx.build_candidate(cand)
        real_rename=os.rename
        real_sleep=tx.time.sleep
        def always_fail_target(src,dst):
            srcp=Path(src)
            if srcp.parent==cand and srcp.name=="preos-risk-model":
                raise PermissionError(13,"windows-ci persistent access denied")
            return real_rename(src,dst)
        os.rename=always_fail_target
        tx.time.sleep=lambda _seconds: None
        try:
            try:
                tx.begin_skill_transaction(home,skills,cand,generated,"persistent-injected")
                raise AssertionError("persistent PermissionError did not fail transaction")
            except tx.AcceptanceFailure as exc:
                assert "rollback=ROLLBACK_PASS" in str(exc), str(exc)
        finally:
            os.rename=real_rename
            tx.time.sleep=real_sleep
        assert (skills/"preos"/"SKILL.md").read_text().endswith("old\n")
        assert (skills/"unrelated-skill"/"SKILL.md").is_file()
        assert not (skills/"preos-risk-model").exists()


def main():
    assert os.name=="nt", "This acceptance test must run on Windows"
    tx.assert_normal_transaction()
    assert_persistent_permission_failure()
    tx.assert_user_owned_collision()
    print("WINDOWS_TRANSACTION_V2_TEST_PASS")

if __name__=="__main__":
    main()
