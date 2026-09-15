#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from risk_concern_runtime import RiskConcernError, validate_concern_runtime

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "references" / "risks" / "model2" / "concern-runtime-evidence.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate operational PREOS risk concern linkage.")
    parser.add_argument("path", nargs="?", default=str(DEFAULT))
    args = parser.parse_args()
    path = Path(args.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate_concern_runtime(data)
    except (OSError, json.JSONDecodeError, RiskConcernError) as exc:
        raise SystemExit(f"FAIL risk concern linkage: {exc}")
    print(
        "PASS risk concern linkage: "
        f"{result['definitions']} RiskDefinition version(s), "
        f"{result['assessments']} assessment(s), "
        f"{result['independent_definitions']} independent definition(s), "
        f"{result['current_acceptances']} current acceptance(s)"
    )


if __name__ == "__main__":
    main()
