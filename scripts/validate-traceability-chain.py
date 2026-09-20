#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "references" / "traceability"
DEFAULT_CHAIN = TRACE / "pasv2-traceability-chain.json"
DEFAULT_GRAPH = TRACE / "pasv2-traceability-graph.jsonl"
DEFAULT_COVERAGE = TRACE / "pasv2-traceability-coverage.json"
REQUIRED_FIELDS = [
    "chain_id",
    "source_document",
    "source_item",
    "runtime",
    "artifact",
    "test",
    "gate",
    "release",
    "links",
]

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_graph(path: Path):
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        for field in REQUIRED_FIELDS:
            if row.get(field) in (None, "", []):
                raise ValueError(f"graph line {line_no} missing {field}")
        observed = {(item.get("from"), item.get("to")) for item in row["links"]}
        if ("source_document", "source_item") not in observed:
            raise ValueError(f"graph line {line_no} missing source link")
        if ("source_item", "runtime") not in observed:
            raise ValueError(f"graph line {line_no} missing runtime link")
        rows.append(row)
    return rows

def validate_graph(graph_path: Path, coverage_path: Path) -> dict:
    rows = read_graph(graph_path)
    coverage = read_json(coverage_path)
    expected = coverage.get("expected_source_counts", {})
    observed = {}
    for row in rows:
        key = row["source_document"]
        observed[key] = observed.get(key, 0) + 1
        artifact = row["artifact"]
        if artifact.startswith("PREOS/"):
            rel = artifact.split("::", 1)[0]
            path = ROOT.parent / rel
            if not path.exists():
                raise ValueError(f"missing artifact reference: {artifact}")
    if observed != expected:
        raise ValueError(f"coverage mismatch: expected {expected}, observed {observed}")
    if coverage.get("observed_source_counts") != observed:
        raise ValueError("coverage file observed counts do not match graph")
    if coverage.get("total_graph_records") != len(rows):
        raise ValueError("coverage file total does not match graph")
    return {"records": len(rows), "sources": len(observed)}

def validate_chain(path: Path = DEFAULT_CHAIN) -> dict:
    data = read_json(path)
    chains = data.get("chains", [])
    if not chains:
        raise ValueError("sentinel chain file has no chains")
    return {"chains": len(chains)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_CHAIN))
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH))
    parser.add_argument("--coverage", default=str(DEFAULT_COVERAGE))
    args = parser.parse_args()
    try:
        chain_result = validate_chain(Path(args.path))
        graph_result = validate_graph(Path(args.graph), Path(args.coverage))
    except Exception as exc:
        raise SystemExit(f"FAIL traceability chain: {exc}")
    print(
        "PASS traceability chain: "
        + str(chain_result["chains"])
        + " sentinel chain(s), "
        + str(graph_result["records"])
        + " graph records"
    )


if __name__ == "__main__":
    main()
