#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_phase25_deterministic_lifecycle_windows as lifecycle


def main():
    root = Path(os.environ["CODEX_HOME"])
    candidates = sorted(
        (p for p in (root / "phase24-candidates").glob("ci-r3-*") if (p / "skills").is_dir()),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise AssertionError(f"no verified Phase 24 candidate home found under {root / 'phase24-candidates'}")
    candidate_home = candidates[-1]
    # candidate-only CI intentionally does not mutate the fake live skills directory.
    # Point the deterministic lifecycle at the fully verified isolated candidate so
    # gstack continuity semantics are checked against the exact generated skills.
    os.environ["CODEX_HOME"] = str(candidate_home)
    print(f"PHASE25_LIFECYCLE_CANDIDATE_HOME={candidate_home}")
    lifecycle.main()

if __name__ == "__main__":
    main()
