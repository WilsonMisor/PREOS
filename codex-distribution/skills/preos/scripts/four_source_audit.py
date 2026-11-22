"""Independently reparse preserved inputs; never accept generated totals as proof.

This validator checks preservation and joins. Semantic approval remains a separate
human/governance decision, and no successful audit activates Model 2.
"""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from canonical_sources import source_bytes, SOURCES

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {'4':'universal','5':'industry','6':'product','7':'jurisdiction','8':'architecture'}
EXPECTED_DIMENSIONS = {'universal':1406,'industry':1450,'product':753,'jurisdiction':328,'architecture':400}

def sha(raw): return hashlib.sha256(raw).hexdigest()
def rows(path): return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
def unique(records, field):
    result = {r[field]:r for r in records}
    if len(result)!=len(records): raise ValueError('duplicate '+field)
    return result

def parse_risks(raw):
    lines=raw.decode('utf-8').splitlines()
    result=[]; current=None
    for line_no,line in enumerate(lines,1):
        heading=re.fullmatch(r'#### (\d+\.\d+\.\d+) (.+)',line)
        if heading:
            if current: result.append(current)
            current={'risk_id':heading[1],'canonical_name':heading[2], 'dimension':DIMENSIONS[heading[1].split('.')[0]],'source_line_start':line_no,'fields':{},'field_numbers':[]}
        elif line.startswith('#') and current:
            result.append(current); current=None
        elif current:
            field=re.fullmatch(r'(\d+)\. ([^:]+): (.*)',line)
            if field:
                if field[2] in current['fields']: raise ValueError('duplicate source field')
                current['fields'][field[2]]=field[3]
                current['field_numbers'].append(int(field[1]))
    if current: result.append(current)
    for r in result:
        if r['field_numbers']!=list(range(1,41)) or r['fields']['Problem ID']!=r['risk_id'] or r['fields']['Canonical problem name']!=r['canonical_name']:
            raise ValueError('source record layout/identity mismatch: '+r['risk_id'])
    return result

def docx_paragraphs(raw):
    document=ET.fromstring(zipfile.ZipFile(io.BytesIO(raw)).read('word/document.xml'))
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    output=[]
    for p in document.iter(ns+'p'):
        text=''.join((node.text or '') if node.tag==ns+'t' else ('\n' if node.tag in {ns+'br',ns+'cr'} else ('\t' if node.tag==ns+'tab' else '')) for node in p.iter())
        if text.strip(): output.append(text.strip())
    return output

def meaningful_lines(raw):
    return [(i,line.strip()) for i,line in enumerate(raw.decode('utf-8').splitlines(),1) if line.strip() and line.strip()!='---']

def verify_source1(root=ROOT):
    source=unique(parse_risks(source_bytes('source-1')),'risk_id')
    corpus=unique(rows(root/'references/risks/model2/risk-corpus.jsonl'),'risk_id')
    if source.keys()!=corpus.keys(): raise ValueError('Source 1 identities lost or invented')
    distribution=Counter(r['dimension'] for r in source.values())
    if dict(distribution)!=EXPECTED_DIMENSIONS: raise ValueError('Source 1 dimension distribution changed')
    for rid,original in source.items():
        actual=corpus[rid]
        for field in ('canonical_name','dimension','fields','source_line_start'):
            if original[field]!=actual[field]: raise ValueError(f'Source 1 {rid}: {field} changed')
        if actual['category']!=original['fields']['Category']: raise ValueError('category changed: '+rid)
    variants=unique(rows(root/'references/risks/model2/risk-context-variants.jsonl'),'source_risk_id')
    definitions=rows(root/'references/risks/model2/normalized-risk-definitions.jsonl')
    by_definition={(r['risk_definition_id'],r['definition_version']):r for r in definitions}
    if len(by_definition)!=len(definitions): raise ValueError('competing definition versions')
    if variants.keys()!=source.keys(): raise ValueError('context variants do not preserve every Source 1 identity')
    reviews=unique(rows(root/'references/risks/model2/semantic-review-ledger.jsonl'),'source_record')
    if reviews.keys()!=source.keys(): raise ValueError('semantic review identities differ from source')
    bound=[]
    for definition in definitions: bound.extend(definition['source_records'])
    if Counter(bound)!=Counter({rid:1 for rid in source}): raise ValueError('definition source bindings lost or duplicated')
    for rid,variant in variants.items():
        definition=by_definition.get((variant['risk_definition_id'],variant['definition_version']))
        if definition is None or rid not in definition['source_records']: raise ValueError('orphan/mismatched context variant '+rid)
        digest=sha(json.dumps(corpus[rid],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
        if variant['source_record_sha256']!=digest: raise ValueError('variant raw-source hash mismatch '+rid)
        for field in ('dimension','category'):
            if variant[field]!=corpus[rid][field]: raise ValueError('variant context differs from source: '+rid)
        if variant.get('source_name')!=source[rid]['canonical_name'] or variant.get('source_sha256')!=SOURCES['source-1'][1]:
            raise ValueError('variant source provenance drift: '+rid)
        if variant['source_location']['source_line_start']!=source[rid]['source_line_start']:
            raise ValueError('variant source location drift: '+rid)
        review=reviews[rid]
        if variant.get('normalized_semantics_ref')!='semantic-review-ledger.jsonl#semantic_review_id='+review['semantic_review_id'] or variant.get('semantic_review_state')!=review['semantic_review_status']:
            raise ValueError('variant reviewed contextual semantics mismatch: '+rid)
        dimension=variant['dimension']
        if dimension!='universal' and variant['context'].get(dimension)!=corpus[rid]['category']:
            raise ValueError('variant contextual facet lost: '+rid)
    return {'status':'PASS','records':len(source),'dimensions':dict(distribution),'variants':len(variants),'definitions':len(definitions),'missing_identities':0,'orphan_variants':0,'all_40_fields_compared':True}

def verify_semantic_units(root=ROOT):
    ledger=rows(root/'references/source-units/PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl')
    unique(ledger,'semantic_unit_id')
    result={}
    for sid,label in [('source-3','source-3-operating-system'),('source-4','source-4-original-master-prompt')]:
        expected=meaningful_lines(source_bytes(sid))
        actual=[r for r in ledger if r['source_id']==label]
        if len(actual)!=len(expected): raise ValueError(sid+' semantic unit count mismatch')
        for row,(line,text) in zip(actual,expected,strict=True):
            if row['source_line_or_paragraph']!=line or row['text_sha256']!=sha(text.encode()) or not text.startswith(row['text_excerpt']):
                raise ValueError(sid+' semantic unit content/location mismatch: '+row['semantic_unit_id'])
        result[sid]={'status':'PASS','units':len(actual),'missing':0,'source_sha256':sha(source_bytes(sid))}
    return result

def verify_source2(root=ROOT):
    paragraphs=docx_paragraphs(source_bytes('source-2'))
    actual=rows(root/'references/readiness/source2-readiness-units.jsonl')
    unique(actual,'source_unit_id')
    if len(actual)!=len(paragraphs): raise ValueError('Source 2 paragraph count mismatch')
    for row,text in zip(actual,paragraphs,strict=True):
        # Word text extraction may normalize embedded line breaks to spaces.
        if re.sub(r'\s+',' ',row['excerpt']).strip()!=re.sub(r'\s+',' ',text).strip():
            raise ValueError('Source 2 paragraph mismatch: '+row['source_unit_id'])
    registry=json.loads((root/'references/readiness/domain-registry.json').read_text())['domains']
    headings={int(m[1]):m[2] for text in paragraphs if (m:=re.fullmatch(r'(\d+)\.\s+(.+)',text)) and 4<=int(m[1])<=39}
    if len(headings)!=36 or len(registry)!=36: raise ValueError('Source 2 domain headings incomplete')
    for domain in registry:
        if headings.get(domain['source_section'])!=domain['name']: raise ValueError('Source 2 domain mismatch '+domain['id'])
    return {'status':'PASS','domains':len(headings),'units':len(actual),'missing':0,'source_sha256':sha(source_bytes('source-2'))}

def verify_source4_crosswalk(root=ROOT):
    cx=json.loads((root/'references/integration/source4-production-assurance-crosswalk.json').read_text())
    raw=source_bytes('source-4'); lines=raw.decode().splitlines()
    if cx['source_sha256']!=sha(raw): raise ValueError('Source 4 hash binding changed')
    checked=0
    def visit(node):
        nonlocal checked
        if isinstance(node,list):
            for child in node: visit(child)
        elif isinstance(node,dict):
            if isinstance(node.get('line'),int) and 'text' in node:
                text=re.sub(r'^\d+\.\s*','',lines[node['line']-1]).strip()
                if text.rstrip('.')!=node['text'].rstrip('.'): raise ValueError('Source 4 crosswalk text/location drift at '+str(node['line']))
                checked+=1
            for child in node.values(): visit(child)
    visit(cx)
    fields={'production_questions':30,'assumption_register':40,'context_dimensions':40,'full_stack_domains':32,'threat_stages':5,'maturity_stages':6,'nondeferrable_controls':20,'test_families':28,'production_feedback_steps':12,'atomic_field_crosswalk':37,'output_structure':20,'anti_overengineering_questions':10,'engines':5}
    for name,count in fields.items():
        if len(cx[name])!=count: raise ValueError('Source 4 structure changed: '+name)
    if len(cx['economics_and_complexity']['cost_dimensions'])!=25: raise ValueError('cost dimensions incomplete')
    from risk_field_crosswalk import manifest
    projections=manifest()['sources']['source-4']['fields']
    for row in cx['atomic_field_crosswalk']:
        if row.get('projection')!=projections[row['number']-1]:raise ValueError('Source 4 concern projection drift')
    artifacts=cx.get('transformation_artifacts',[])
    if len(artifacts)!=19 or len({r['required_name'] for r in artifacts})!=19:raise ValueError('Source 4 transformation artifact coverage incomplete')
    for artifact in artifacts:
        path=root/artifact['canonical_path'];selector=artifact['selector']
        if not path.is_file():raise ValueError('missing Source 4 canonical artifact: '+str(path))
        if selector.startswith('/'):
            data=json.loads(path.read_text(encoding='utf-8'))
            for part in selector[1:].split('/'):data=data[int(part)] if isinstance(data,list) else data[part]
        elif path.suffix=='.jsonl':
            key,value=selector.split('=',1)
            if not any(str(r.get(key))==value for r in rows(path)):raise ValueError('source ledger selector unresolved')
        elif not re.search(r'^#{1,6} '+re.escape(selector)+r'$',path.read_text(encoding='utf-8'),re.M):
            raise ValueError('Source 4 report section missing')
    return {'status':'PASS','structures':fields,'cost_dimensions':25,'transformation_artifacts':len(artifacts),'source_items_checked_against_text':checked,'domain_concerns':sum(len(r['concerns']) for r in cx['full_stack_domains'])}

def audit(root=ROOT):
    return {'source1':verify_source1(root),'source2':verify_source2(root),'semantic_units':verify_semantic_units(root),'source4':verify_source4_crosswalk(root),'sources':{sid:{'sha256':sha(source_bytes(sid)),'bytes':len(source_bytes(sid))} for sid in SOURCES},'authority':'Preservation and mapping checks do not approve semantic interpretation, Model 2 activation, or production release.'}

if __name__=='__main__': print(json.dumps(audit(),indent=2))
