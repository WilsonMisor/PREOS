#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "references" / "traceability" / "pasv2-traceability-chain.json"
CHAIN = [
    "source_document",
    "source_item",
    "normalized_runtime_record",
    "risk_definition",
    "risk_assessment",
    "control",
    "requirement",
    "task_packet",
    "implementation",
    "test",
    "evidence",
    "gate",
    "release",
    "incident",
    "learning",
]


def validate_chain(path: Path = DEFAULT) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("chains", [])
    if not isinstance(records, list) or not records:
        raise ValueError("traceability chains must be a non-empty array")
    for idx, chain in enumerate(records, 1):
        if not isinstance(chain, dict):
            raise ValueError(f"chain {idx} is not an object")
        applicability = chain.get("applicability", {})
        if not isinstance(applicability, dict):
            raise ValueError(f"chain {idx} applicability must be an object")
        for node in CHAIN:
            value = chain.get(node)
            if value in (None, "", []):
                if applicability.get(node) == "NOT_APPLICABLE":
                    continue
                raise ValueError(f"chain {idx} missing required node {node}")
        links = chain.get("links", [])
        expected_links = list(zip(CHAIN, CHAIN[1:]))
        observed = {(item.get("from"), item.get("to")) for item in links if isinstance(item, dict)}
        for edge in expected_links:
            if edge not in observed:
                missing_terminal = edge[1]
                if applicability.get(missing_terminal) == "NOT_APPLICABLE":
                    continue
                raise ValueError(f"chain {idx} missing link {edge[0]} -> {edge[1]}")
    return {"chains": len(records), "nodes": len(CHAIN)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PAS v2 source-to-learning traceability chain.")
    parser.add_argument("path", nargs="?", default=str(DEFAULT))
    args = parser.parse_args()
    try:
        result = validate_chain(Path(args.path))
    except Exception as exc:
        raise SystemExit(f"FAIL traceability chain: {exc}")
    print(f"PASS traceability chain: {result['chains']} chain(s), {result['nodes']} node types")


if __name__ == "__main__":
    main()
