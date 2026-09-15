#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from preos_common import load_json
from risk_concern_runtime import RiskConcernError, validate_acceptance_record


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PREOS risk acceptance records with revocation and freshness semantics.")
    parser.add_argument("acceptance", nargs="+")
    parser.add_argument("--allow-noncurrent", action="store_true", help="Allow expired/revoked/superseded archival records after structural authority validation")
    args = parser.parse_args()
    errors: list[str] = []
    current = 0
    for path_text in args.acceptance:
        path = Path(path_text)
        try:
            record = load_json(path)
            risk_ids = record.get("risk_ids")
            if not isinstance(risk_ids, list) or not risk_ids:
                raise RiskConcernError("acceptance missing risk_ids")
            expected_ref = f"{record.get('risk_definition_id')}@{record.get('definition_version')}"
            if record.get("risk_definition_id") and record.get("definition_version") and expected_ref not in risk_ids:
                raise RiskConcernError(f"risk_ids must include stable definition reference {expected_ref}")
            is_current = validate_acceptance_record(record)
            if is_current:
                current += 1
            elif not args.allow_noncurrent:
                raise RiskConcernError("record is not current acceptance authority")
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        print("\n".join("FAIL " + error for error in errors))
        raise SystemExit(1)
    if args.allow_noncurrent:
        print(f"PASS risk acceptance: {len(args.acceptance)} record(s) have bounded human authority; {current} current")
    else:
        print(f"PASS risk acceptance: {current} current record(s) have bounded human authority")


if __name__ == "__main__":
    main()
