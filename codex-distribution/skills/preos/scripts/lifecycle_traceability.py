"""Resolve lifecycle nodes and validate semantic joins, not caller status flags."""
from collections import Counter
import ast
import hashlib
import json
from pathlib import Path

from canonical_sources import source_bytes
from control_assurance import evaluate_evidence
from preos_common import load_source_json
from production_feedback import validate_learning

ROOT=Path(__file__).resolve().parents[1]
REQUIRED_OPERATIONAL={'source_item','normalized_runtime_record','risk_definition','risk_context_variant',
    'risk_assessment','control','master_requirement','task_packet','implementation_artifact','test','evidence','preos_gate','release'}
PROJECT_KEYS={'risk_assessment':'assessment_id','task_packet':'task_packet_id','evidence':'evidence_id',
              'preos_gate':'gate_id','release':'release_id','incident':'incident_id','learning':'learning_id',
              'master_requirement':'requirement_id'}
EDGE_TYPES={
    'PRESERVES':('source_item','normalized_runtime_record'),
    'NORMALIZES':('normalized_runtime_record','risk_definition'),
    'VARIANT_OF':('risk_context_variant','risk_definition'),
    'ASSESSES':('risk_context_variant','risk_assessment'),
    'MITIGATED_BY':('risk_assessment','control'),
    'ADDRESSES':('risk_assessment','task_packet'),
    'IMPLEMENTS':('master_requirement','task_packet'),
    'DELIVERS':('task_packet','implementation_artifact'),
    'TESTED_BY':('implementation_artifact','test'),
    'PRODUCES':('test','evidence'),
    'SATISFIES':('evidence','preos_gate'),
    'DECIDES':('preos_gate','release'),
    'OBSERVED_IN':('release','incident'),
    'LEARNS':('incident','learning'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value):
    return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())


class Resolver:
    def __init__(self,roots):
        self.roots={k:Path(v).resolve() for k,v in roots.items()}
        self.cache={}
        self.sources={}

    def path(self,ref):
        root=self.roots[ref['root']]
        path=(root/ref['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('unresolved or out-of-scope artifact: '+str(path))
        return path

    def read(self,path):
        if path not in self.cache:
            self.cache[path]=path.read_bytes()
        return self.cache[path]

    def resolve(self,node):
        kind=node['type']; ref=node['ref']
        if 'resolves' in node:
            raise ValueError('self-authored resolves flag is not a reference')
        if kind=='source_item':
            sid=ref['source_id']
            if sid not in self.sources:
                self.sources[sid]=source_bytes(sid)
                self.cache[(sid,'source_sha256')]=sha(self.sources[sid])
            raw=self.sources[sid]
            if ref.get('source_sha256')!=self.cache[(sid,'source_sha256')]:
                raise ValueError('source hash binding mismatch')
            if sid=='source-2':
                from four_source_audit import docx_paragraphs
                if (sid,'paragraphs') not in self.cache: self.cache[(sid,'paragraphs')]=docx_paragraphs(raw)
                paragraphs=self.cache[(sid,'paragraphs')]; number=ref['paragraph']
                if not 1<=number<=len(paragraphs): raise ValueError('source paragraph does not resolve')
                text=paragraphs[number-1]
                if sha(text.encode())!=ref['excerpt_sha256'] or node['id']!=f'{sid}:P{number}':
                    raise ValueError('source paragraph identity/content mismatch')
                return {'text':text,**ref}
            if (sid,'lines') not in self.cache: self.cache[(sid,'lines')]=raw.decode('utf-8').splitlines()
            lines=self.cache[(sid,'lines')]
            start,end=ref['start_line'],ref['end_line']
            if not 1<=start<=end<=len(lines):
                raise ValueError('source range does not resolve')
            text='\n'.join(lines[start-1:end])
            if sha(text.encode())!=ref['excerpt_sha256'] or node['id']!=f'{sid}:L{start}-{end}':
                raise ValueError('source item identity/content mismatch')
            return {'text':text,**ref}
        if kind=='control':
            controls={f"FS-{c['no']:03d}":c for c in load_source_json('baseline_75_controls.json',ROOT)['controls']}
            value=controls.get(node['id'])
            if value is None or canonical_hash(value)!=ref['record_sha256']:
                raise ValueError('control does not resolve in the original baseline')
            return value
        path=self.path(ref)
        raw=self.read(path)
        if ref.get('format')=='master_requirement':
            document=json.loads(raw)
            master=self.read(self.path({'root':ref['root'],'path':ref['master_path']}))
            if sha(master)!='74e547225f0af2e0f64d0930f7f4317e86823bf6b103c96f648936b1dfa823c3':
                raise ValueError('governing master bytes changed')
            matches=[r for r in document['requirements'] if r['requirement_id']==node['id']]
            if len(matches)!=1:
                raise ValueError('master requirement ID does not resolve')
            value=matches[0]
            master_text=master.decode('utf-8').replace('\r\n','\n')
            if master_text[value['source_start']:value['source_end']]!=value['exact_text']:
                raise ValueError('requirement text does not match its master range')
        elif ref.get('format')=='jsonl':
            cache_key=(path,'rows',ref['key'])
            if cache_key not in self.cache:
                records=[json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
                index={r[ref['key']]:r for r in records}
                if len(index)!=len(records):
                    raise ValueError('duplicate record identities in '+str(path))
                self.cache[cache_key]=index
            value=self.cache[cache_key].get(ref['value'])
            if value is None or canonical_hash(value)!=ref['record_sha256']:
                raise ValueError('JSONL record does not resolve or changed')
        elif ref.get('format')=='python':
            if sha(raw)!=ref['sha256']:
                raise ValueError('implementation/test bytes changed')
            tree=ast.parse(raw.decode('utf-8'))
            current=tree
            for part in ref['symbol'].split('.'):
                matches=[n for n in current.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==part]
                if len(matches)!=1:
                    raise ValueError('Python symbol does not resolve')
                current=matches[0]
            if node['id']!=ref['path']+'::'+ref['symbol']:
                raise ValueError('code node identity is not its exact reference')
            if kind=='test' and (not isinstance(current,ast.FunctionDef) or not current.name.startswith('test_')):
                raise ValueError('test reference is not an executable test method')
            imports={}
            for item in tree.body:
                if isinstance(item,ast.ImportFrom):
                    for alias in item.names:
                        imports[alias.asname or alias.name]=(item.module or '')+'.'+alias.name
                elif isinstance(item,ast.Import):
                    for alias in item.names:
                        imports[alias.asname or alias.name]=alias.name
            calls=[]
            for item in ast.walk(current):
                if isinstance(item,ast.Call):
                    called=ast.unparse(item.func)
                    prefix=called.split('.')[0]
                    calls.append(imports.get(prefix,prefix)+called[len(prefix):])
            return {'path':ref['path'],'symbol':ref['symbol'],'sha256':ref['sha256'],
                    'calls':calls,'selector':ref['path'][:-3].replace('/','.')+'.'+ref['symbol']}
        else:
            if ref.get('format')!='json' or sha(raw)!=ref['sha256']:
                raise ValueError('unsupported or changed JSON artifact')
            value=json.loads(raw)
        if kind in PROJECT_KEYS and value.get(PROJECT_KEYS[kind])!=node['id']:
            raise ValueError('project node ID does not resolve inside its artifact')
        if kind=='risk_definition' and node['id']!=value['risk_definition_id']+'@'+value['definition_version']:
            raise ValueError('definition identity/version mismatch')
        if kind=='risk_context_variant' and node['id']!=value['risk_context_variant_id']:
            raise ValueError('variant identity mismatch')
        if kind=='normalized_runtime_record' and node['id']!=value.get('risk_id',value.get('source_unit_id',value.get('semantic_unit_id'))):
            raise ValueError('normalized runtime identity mismatch')
        return value


def validate_edge(edge,nodes,values,resolver):
    kind=edge['type']
    if kind not in EDGE_TYPES:
        raise ValueError('unsupported lifecycle edge: '+kind)
    left,right=nodes[edge['from']],nodes[edge['to']]
    if (left['type'],right['type'])!=EDGE_TYPES[kind]:
        raise ValueError('lifecycle edge endpoint types do not match '+kind)
    a,b=values[left['id']],values[right['id']]
    lid,rid=left['id'],right['id']
    valid=False
    if kind=='PRESERVES':
        valid=b.get('source_line_start')==a['start_line'] and b.get('source_heading_name','') in a['text']
    elif kind=='NORMALIZES':
        valid=lid in b.get('source_records',[])
    elif kind=='VARIANT_OF':
        valid=rid==a['risk_definition_id']+'@'+a['definition_version']
    elif kind=='ASSESSES':
        valid=lid==b.get('risk_context_variant_id') and a['risk_definition_id']==b.get('risk_definition_id')
    elif kind=='MITIGATED_BY':
        valid=rid in a.get('control_ids',[])
    elif kind=='ADDRESSES':
        valid=lid in b.get('assessment_ids',[]) and a.get('project_id')==b.get('project_id')
    elif kind=='IMPLEMENTS':
        valid=lid in b.get('requirement_ids',[])
    elif kind=='DELIVERS':
        valid=rid in a.get('implementation_refs',[])
    elif kind=='TESTED_BY':
        valid=a['path'][:-3].replace('/','.')+'.'+a['symbol'] in b.get('calls',[])
    elif kind=='PRODUCES':
        execution_path=Path(b.get('artifact_location',''))
        if execution_path.is_file():
            execution=json.loads(execution_path.read_text(encoding='utf-8'))
            bound=b.get('bindings',{}).get('test_definition_files',[])
            valid=execution.get('selector')==a.get('selector') and any(t['path']==a['path'] and t['sha256']==a['sha256'] for t in bound)
    elif kind=='SATISFIES':
        controls=b.get('control_ids',[])
        valid=bool(controls) and lid in b.get('evidence_ids',[])
        repo=resolver.roots['project']
        reasons=[reason for control in controls for reason in evaluate_evidence(a,repo,control,project_id=b.get('project_id'),release_id=b.get('release_id'))]
        if reasons:
            raise ValueError('gate evidence is invalid: '+'; '.join(reasons))
        valid=valid and b.get('state')=='GREEN'
    elif kind=='DECIDES':
        valid=lid in b.get('gate_ids',[]) and a.get('release_id')==rid and a.get('project_id')==b.get('project_id')
        if b.get('production_authorized') is not False:
            raise ValueError('traceability cannot substitute for production release authority')
    elif kind=='OBSERVED_IN':
        valid=lid==b.get('release_id') and a.get('project_id')==b.get('project_id')
    elif kind=='LEARNS':
        valid=lid==b.get('incident_id') and a.get('project_id')==b.get('project_id')
        validate_learning(b,resolver.roots['project'])
    if not valid:
        raise ValueError(f'edge {kind} does not join actual artifact fields: {lid} -> {rid}')


def validate_operational_graph(graph,roots):
    if graph.get('unit_type')!='operational':
        raise ValueError('project lifecycle requires operational coverage policy')
    resolver=Resolver(roots)
    nodes={n['id']:n for n in graph['nodes']}
    if len(nodes)!=len(graph['nodes']):
        raise ValueError('duplicate lifecycle node IDs')
    types={n['type'] for n in nodes.values()}
    required=REQUIRED_OPERATIONAL|({'incident','learning'} if graph.get('phase')=='incident-learning' else set())
    if not required<=types:
        raise ValueError('operational chain omits required types: '+str(sorted(required-types)))
    values={ident:resolver.resolve(node) for ident,node in nodes.items()}
    connected={k:set() for k in nodes}
    used=set()
    for edge in graph['edges']:
        pair=(edge['type'],edge['from'],edge['to'])
        if pair in used:
            raise ValueError('duplicate lifecycle edge')
        used.add(pair)
        if edge['from'] not in nodes or edge['to'] not in nodes:
            raise ValueError('lifecycle edge endpoint is absent')
        validate_edge(edge,nodes,values,resolver)
        connected[edge['from']].add(edge['to'])
        connected[edge['to']].add(edge['from'])
    required_edges=set(EDGE_TYPES)-({'OBSERVED_IN','LEARNS'} if graph.get('phase')!='incident-learning' else set())
    if not required_edges<={edge['type'] for edge in graph['edges']}:
        raise ValueError('operational chain omits required lifecycle joins')
    visited=set(); pending=[next(iter(nodes))]
    while pending:
        ident=pending.pop()
        if ident not in visited:
            visited.add(ident); pending.extend(connected[ident]-visited)
    if visited!=set(nodes):
        raise ValueError('disconnected lifecycle nodes do not establish traceability')
    for ident,node in nodes.items():
        if node['type'] in PROJECT_KEYS and node['type']!='master_requirement' and values[ident].get('project_id')!=graph.get('project_id'):
            raise ValueError('lifecycle contains a different project scope')
    return {'nodes':len(nodes),'edges':len(used),'node_types':dict(Counter(n['type'] for n in nodes.values())),'project_id':graph['project_id']}


def validated_query_edges(path):
    graph=json.loads(Path(path).read_text(encoding='utf-8'))
    roots={'PREOS':ROOT,'wed_dev_skill':ROOT.parent/'wed_dev_skill','project':Path(path).resolve().parent}
    validate_operational_graph(graph,roots)
    nodes={n['id']:n for n in graph['nodes']}
    result=[]
    for edge in graph['edges']:
        kind={'MITIGATED_BY':'MITIGATED_BY','SATISFIES':'AFFECTS_GATE','PRODUCES':'EVIDENCED_BY','OBSERVED_IN':'OBSERVED_IN'}.get(edge['type'])
        if kind:
            result.append({'relationship_id':'PROJECT-'+canonical_hash(edge)[:16],
                'relationship_type':kind,'source':{'type':nodes[edge['from']]['type'],'id':edge['from']},
                'target':{'type':nodes[edge['to']]['type'],'id':edge['to']},'provenance':str(path)})
    return result
