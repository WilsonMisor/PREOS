"""Resolve catalogue lineage; explicitly leave project lifecycle links unbound.

Project execution uses lifecycle_traceability.validate_operational_graph. A
catalogue cannot supply an application's assessment, evidence or release.
"""
from collections import Counter
import json
from pathlib import Path

from canonical_sources import source_bytes, SOURCES
from four_source_audit import rows, unique, docx_paragraphs
from lifecycle_traceability import Resolver, canonical_hash, sha
from source_semantics import requirements

ROOT=Path(__file__).resolve().parents[1]
TRACE=ROOT/'references/traceability'
MODEL=ROOT/'references/risks/model2'
PROJECT_LINKS=['risk_assessment','risk_economics','risk_evolution','risk_evidence','risk_acceptance','control','requirement','task_packet','implementation','test_execution','gate','release','incident','learning']

def record_node(kind,path,key,record,identity=None):
    return {'id':identity or record[key],'type':kind,'ref':{'root':'PREOS','path':path.relative_to(ROOT).as_posix(),'format':'jsonl','key':key,'value':record[key],'record_sha256':canonical_hash(record)}}

def source_node(sid,number,lines=None,paragraphs=None):
    text=paragraphs[number-1] if paragraphs is not None else lines[number-1]
    ref={'source_id':sid,'source_sha256':SOURCES[sid][1],'excerpt_sha256':sha(text.encode())}
    if paragraphs is not None: ref['paragraph']=number; identity=f'{sid}:P{number}'
    else: ref.update(start_line=number,end_line=number); identity=f'{sid}:L{number}-{number}'
    return {'id':identity,'type':'source_item','ref':ref}

def expected_rows():
    output=[]
    definitions=unique(rows(MODEL/'normalized-risk-definitions.jsonl'),'risk_definition_id')
    variants=unique(rows(MODEL/'risk-context-variants.jsonl'),'source_risk_id')
    reviews=unique(rows(MODEL/'semantic-review-ledger.jsonl'),'source_record')
    lines=source_bytes('source-1').decode().splitlines()
    for raw in rows(MODEL/'risk-corpus.jsonl'):
        rid=raw['risk_id']; variant=variants[rid]; definition=definitions[variant['risk_definition_id']]; review=reviews[rid]
        if rid not in definition['source_records'] or variant['definition_version']!=definition['definition_version'] or review['risk_definition_id']!=definition['risk_definition_id']:
            raise ValueError('source/variant/review/definition join mismatch: '+rid)
        nodes=[source_node('source-1',raw['source_line_start'],lines=lines),
            record_node('normalized_runtime_record',MODEL/'risk-corpus.jsonl','risk_id',raw),
            record_node('risk_context_variant',MODEL/'risk-context-variants.jsonl','risk_context_variant_id',variant),
            record_node('risk_definition',MODEL/'normalized-risk-definitions.jsonl','risk_definition_id',definition,definition['risk_definition_id']+'@'+definition['definition_version']),
            record_node('semantic_review',MODEL/'semantic-review-ledger.jsonl','semantic_review_id',review)]
        output.append({'trace_id':'TRACE-S1-'+rid,'source_document':'source-1','source_item':rid,'nodes':nodes,
                       'terminal_disposition':review['semantic_review_status'],'unbound_project_links':{k:'REQUIRES_PROJECT_CONTEXT' for k in PROJECT_LINKS}})
    paragraphs=docx_paragraphs(source_bytes('source-2'))
    path=ROOT/'references/readiness/source2-readiness-units.jsonl'
    for number,unit in enumerate(rows(path),1):
        if unit['excerpt']!=paragraphs[number-1]: raise ValueError('readiness source text mismatch')
        output.append({'trace_id':'TRACE-S2-'+unit['source_unit_id'],'source_document':'source-2','source_item':unit['source_unit_id'],
            'nodes':[source_node('source-2',number,paragraphs=paragraphs),record_node('normalized_runtime_record',path,'source_unit_id',unit)],
            'terminal_disposition':unit['mapping_status'],'unbound_project_links':{k:'REQUIRES_PROJECT_CONTEXT' for k in PROJECT_LINKS}})
    path=ROOT/'references/source-units/PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl'; units=unique(rows(path),'semantic_unit_id')
    for sid in ('source-3','source-4'):
        lines=source_bytes(sid).decode().splitlines()
        for requirement in requirements(sid):
            unit=units[requirement['source_unit_id']]
            output.append({'trace_id':'TRACE-'+unit['semantic_unit_id'],'source_document':sid,'source_item':unit['semantic_unit_id'],
                'nodes':[source_node(sid,requirement['line'],lines=lines),record_node('normalized_runtime_record',path,'semantic_unit_id',unit)],
                'runtime_owner':requirement['runtime_owner'],'terminal_disposition':'ADDRESSABLE_REQUIREMENT',
                'unbound_project_links':{k:'REQUIRES_PROJECT_CONTEXT' for k in PROJECT_LINKS}})
    return output

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in data),encoding='utf-8',newline='\n')

def generate(path=TRACE/'pasv2-traceability-graph.jsonl'):
    data=expected_rows(); write(path,data)
    coverage={'schema_version':'pasv2-resolved-catalogue-lineage-v2','total_graph_records':len(data),
              'expected_source_counts':dict(Counter(r['source_document'] for r in data)),
              'observed_source_counts':dict(Counter(r['source_document'] for r in data)),
              'project_lifecycle_validator':'scripts/lifecycle_traceability.py::validate_operational_graph',
              'policy':'Catalogue lineage is not proof of application implementation, evidence or release approval.'}
    cp=TRACE/'pasv2-traceability-coverage.json' if path==TRACE/'pasv2-traceability-graph.jsonl' else path.with_suffix('.coverage.json')
    cp.write_text(json.dumps(coverage,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'records':len(data),**coverage['observed_source_counts']}

def validate(path=TRACE/'pasv2-traceability-graph.jsonl'):
    actual=rows(path); expected=expected_rows()
    if actual!=expected: raise ValueError('traceability differs from independently resolved source/record joins')
    resolver=Resolver({'PREOS':ROOT}); seen=set(); kinds=Counter()
    for row in actual:
        for node in row['nodes']:
            identity=canonical_hash(node)
            if identity not in seen: resolver.resolve(node); seen.add(identity)
            kinds[node['type']]+=1
    return {'records':len(actual),'node_types':len(kinds),'resolved_unique_nodes':len(seen),
            'human_review':sum(r['terminal_disposition']=='HUMAN_REVIEW_REQUIRED' for r in actual),
            'all_source_graph_records':len(actual),'all_source_count':len({r['source_document'] for r in actual}),
            'unbound_project_links_explicit':True}

def generate_sentinels(path=TRACE/'pasv2-traceability-chain.json'):
    selected=[r for r in expected_rows() if r['source_item'] in {'4.1.21','5.6.17'}]
    path.write_text(json.dumps({'schema_version':'pasv2-catalogue-sentinels-v2','chains':selected},indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--generate',action='store_true');args=parser.parse_args()
    if args.generate: generate();generate_sentinels()
    print(json.dumps(validate(),indent=2))
