"""Bounded, source-addressable doctrine requirements over preserved source bytes.

This is a view of the canonical source ledger, not a second editable corpus.
Routing identifies the existing runtime owner; it does not claim that an
application implements a requirement merely because its source was selected.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re

from canonical_sources import source_bytes, SOURCES
from four_source_audit import meaningful_lines, rows, sha, verify_semantic_units

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/'references/source-units/PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl'

def destination(section):
    text=section.casefold()
    if any(word in text for word in ('feedback','learn from production')):
        return 'scripts/production_feedback.py','validate_learning'
    if any(word in text for word in ('evidence','nondeferrable','gate','readiness')):
        return 'scripts/control_assurance.py','evidence_gate_engine'
    if any(word in text for word in ('economic','cost','complexity budget','build versus buy','vendor lock')):
        return 'scripts/assurance_engines.py','economics_complexity_engine'
    if any(word in text for word in ('maturity','stage','evolution','defer','activation','architecture decision','expensive technology')):
        return 'scripts/assurance_engines.py','evolution_engine'
    if 'context' in text:
        return 'scripts/assurance_engines.py','context_engine'
    return 'scripts/assurance_engines.py','risk_generation_engine'

def requirements(source_id):
    if source_id not in {'source-3','source-4'}: raise ValueError('doctrine selection supports source-3 and source-4')
    label={'source-3':'source-3-operating-system','source-4':'source-4-original-master-prompt'}[source_id]
    units=[r for r in rows(LEDGER) if r['source_id']==label]
    lines=meaningful_lines(source_bytes(source_id))
    if len(lines)!=len(units): raise ValueError('source semantic unit count drift')
    section='General production assurance doctrine'
    result=[]
    for unit,(number,text) in zip(units,lines,strict=True):
        if unit['source_line_or_paragraph']!=number or unit['text_sha256']!=sha(text.encode()):
            raise ValueError('semantic unit source binding changed')
        is_heading=(source_id=='source-3' and bool(re.match(r'^\*\*\d+[. ]',text))) or (source_id=='source-4' and text.startswith('#'))
        if is_heading: section=text.strip('*# ')
        path,symbol=destination(section)
        result.append({'source_unit_id':unit['semantic_unit_id'],'source_id':source_id,
            'source_sha256':SOURCES[source_id][1],'line':number,'text_sha256':sha(text.encode()),
            'text':text,'section':section,'kind':'source_heading' if is_heading else 'addressable_requirement',
            'runtime_owner':{'path':path,'symbol':symbol},
            'implementation_unit':'Blueprint AI Task Packet',
            'project_disposition':'REQUIRES_CONTEXTUAL_ASSESSMENT',
            'authority':'PREOS G0-G11; humans retain consequential approval'})
    return result

def select(source_id, *, keyword=None, section=None, ids=None, limit=25):
    if not 1<=limit<=100: raise ValueError('source requirement limit must be 1..100')
    selected=[]
    for row in requirements(source_id):
        if ids and row['source_unit_id'] not in ids: continue
        if keyword and keyword.casefold() not in row['text'].casefold(): continue
        if section and section.casefold() not in row['section'].casefold(): continue
        selected.append(row)
        if len(selected)==limit: break
    return selected

def validate():
    verify_semantic_units()
    output={}; checked=set()
    for sid in ('source-3','source-4'):
        data=requirements(sid)
        for row in data:
            dest=row['runtime_owner']; key=(dest['path'],dest['symbol'])
            if key not in checked:
                tree=ast.parse((ROOT/dest['path']).read_text(encoding='utf-8'))
                if not any(isinstance(n,ast.FunctionDef) and n.name==dest['symbol'] for n in tree.body):
                    raise ValueError('runtime destination does not resolve: '+str(key))
                checked.add(key)
        output[sid]={'units':len(data),'sections':len({r['section'] for r in data}),
                     'runtime_destinations':dict(Counter(r['runtime_owner']['symbol'] for r in data)),
                     'missing_source_units':0}
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',choices=['source-3','source-4'])
    parser.add_argument('--keyword'); parser.add_argument('--section'); parser.add_argument('--limit',type=int,default=25)
    args=parser.parse_args()
    print(json.dumps(select(args.source,keyword=args.keyword,section=args.section,limit=args.limit) if args.source else validate(),indent=2))
