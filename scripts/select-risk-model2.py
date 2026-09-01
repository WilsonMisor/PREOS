#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "references" / "risks" / "model2" / "risk-corpus.jsonl"
MAX_LIMIT = 500


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def record_owner(record: dict) -> str:
    fields = record.get("fields", {})
    if not isinstance(fields, dict):
        return ""
    return text(fields.get("39") or fields.get("Field 39") or fields.get("Owner"))

def matches(record: dict, args: argparse.Namespace) -> bool:
    if args.risk_id and record.get("risk_id") != args.risk_id:
        return False
    if args.dimension and record.get("dimension") != args.dimension:
        return False
    if args.category_contains and args.category_contains.lower() not in text(record.get("category")).lower():
        return False
    if args.owner_contains and args.owner_contains.lower() not in record_owner(record).lower():
        return False
    if args.keyword:
        fields = record.get("fields", {})
        haystack = " ".join([
            text(record.get("risk_id")),
            text(record.get("canonical_name")),
            text(record.get("category")),
            text(record_owner(record)),
            text(fields),
        ]).lower()
        if args.keyword.lower() not in haystack:
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select PREOS model2 risk records without unbounded context loading.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--id", dest="risk_id")
    parser.add_argument("--dimension", choices=["universal", "industry", "product", "jurisdiction", "architecture"])
    parser.add_argument("--category-contains")
    parser.add_argument("--owner-contains")
    parser.add_argument("--keyword")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--allow-unbounded", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.limit > MAX_LIMIT and not args.allow_unbounded:
        raise SystemExit(f"--limit above {MAX_LIMIT} requires --allow-unbounded")
    corpus = Path(args.corpus)
    if not corpus.is_file():
        raise SystemExit("model2 risk corpus is not installed; run migration gates before using this selector")

    selected = []
    with corpus.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if matches(record, args):
                selected.append(record)
                if len(selected) >= args.limit:
                    break
    print(json.dumps({"count": len(selected), "records": selected}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
