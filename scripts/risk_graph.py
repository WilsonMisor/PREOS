"""Identity-based queries over canonical relationships and resolved project links."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODEL2=ROOT/'references/risks/model2'
RELATIONS={'causes':'CAUSED_BY','amplifies':'AMPLIFIES','mitigated-by':'MITIGATED_BY',
           'affected-gates':'AFFECTS_GATE','evidence':'EVIDENCED_BY','incidents':'OBSERVED_IN'}
DIMENSIONS={'industries':'industry','products':'product','architectures':'architecture','jurisdictions':'jurisdiction'}


def rows(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


class RiskGraph:
    def __init__(self,corpus=MODEL2):
        self.variants={r['risk_context_variant_id']:r for r in rows(corpus/'risk-context-variants.jsonl')}
        self.definitions={r['risk_definition_id']+'@'+r['definition_version']:r for r in rows(corpus/'normalized-risk-definitions.jsonl')}
        self.endpoints={'RISK_CONTEXT_VARIANT':self.variants,'RISK_DEFINITION':self.definitions}
        self.relationships=rows(corpus/'risk-relationships.jsonl')
        seen=set()
        for rel in self.relationships:
            if rel['relationship_id'] in seen:
                raise ValueError('duplicate graph relationship identity')
            seen.add(rel['relationship_id'])
            for side in ('source','target'):
                node=rel[side]
                if node['id'] not in self.endpoints.get(node['type'],{}):
                    raise ValueError('unresolved canonical relationship endpoint: '+node['id'])
            if rel['relationship_type']=='VARIANT_OF':
                variant=self.variants.get(rel['source']['id'],{})
                if rel['target']['id']!=variant.get('risk_definition_id','')+'@'+variant.get('definition_version',''):
                    raise ValueError('VARIANT_OF contradicts canonical variant binding')

    def query(self,query_type,value=None,*,limit=25,project_graph=None):
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500:
            raise ValueError('graph query limit must be between 1 and 500')
        if query_type in DIMENSIONS:
            dimension=DIMENSIONS[query_type]
            results=[]
            for row in self.variants.values():
                if row['dimension']!=dimension:
                    continue
                # Category is a source facet, not a fabricated causality edge.
                values={row['category'].casefold(),row['source_risk_id'].casefold(),row['risk_context_variant_id'].casefold()}
                context=row.get('context',{}).get(dimension)
                if isinstance(context,str):
                    values.add(context.casefold())
                if value is None or value.casefold() in values:
                    results.append(row)
        elif query_type=='relationship' or query_type in RELATIONS:
            wanted=RELATIONS.get(query_type)
            relations=[r for r in self.relationships if r.get('review_status') in {'VALIDATED_BY_RULE','ACCEPTED_BY_HUMAN'}]
            if project_graph is not None:
                # The project resolver checks typed nodes, hashes and edge joins;
                # arbitrary caller JSON cannot manufacture validated results.
                from lifecycle_traceability import validated_query_edges
                relations+=validated_query_edges(Path(project_graph))
            results=[r for r in relations if (wanted is None or r['relationship_type']==wanted) and
                     (value is None or value in {r['source']['id'],r['target']['id'],r['relationship_id']})]
        else:
            raise ValueError('unsupported graph query: '+query_type)
        return {'query_type':query_type,'query':value,'count':min(len(results),limit),'total_matches':len(results),
                'results':results[:limit],'empty_result_policy':'VALIDATED_RESULTS' if results else 'NO_VALIDATED_RELATION_EXISTS',
                'authority':'Canonical relationship or verified project link; contextual control hints do not establish mitigation.'}


def query_risk_graph(query_type,value=None,*,limit=25,project_graph=None):
    return RiskGraph().query(query_type,value,limit=limit,project_graph=project_graph)
