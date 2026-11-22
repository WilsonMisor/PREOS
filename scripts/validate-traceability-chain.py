#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from catalogue_traceability import TRACE, expected_rows, validate

def validate_chain(path=TRACE/'pasv2-traceability-chain.json'):
    data=json.loads(path.read_text(encoding='utf-8'))
    expected=[r for r in expected_rows() if r['source_item'] in {'4.1.21','5.6.17'}]
    if data.get('chains')!=expected: raise ValueError('sentinel source/definition/variant links do not resolve')
    return {'chains':len(expected)}

def validate_graph(graph_path,coverage_path):
    result=validate(graph_path)
    coverage=json.loads(coverage_path.read_text(encoding='utf-8'))
    observed={}
    for row in expected_rows(): observed[row['source_document']]=observed.get(row['source_document'],0)+1
    if any(coverage.get(key)!=observed for key in ('expected_source_counts','observed_source_counts')) or coverage.get('total_graph_records')!=result['records']:
        raise ValueError('traceability coverage differs from resolved records')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('path',nargs='?',type=Path,default=TRACE/'pasv2-traceability-chain.json')
    parser.add_argument('--graph',type=Path,default=TRACE/'pasv2-traceability-graph.jsonl')
    parser.add_argument('--coverage',type=Path,default=TRACE/'pasv2-traceability-coverage.json');args=parser.parse_args()
    try:
        chain=validate_chain(args.path);graph=validate_graph(args.graph,args.coverage)
    except Exception as exc: raise SystemExit('FAIL traceability chain: '+str(exc))
    print('PASS traceability chain: '+json.dumps({**chain,**graph}))
