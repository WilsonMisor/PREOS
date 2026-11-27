import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from canonical_sources import source_bytes
from control_assurance import capture_control_evidence
from lifecycle_traceability import Resolver, canonical_hash, sha, validate_operational_graph
from preos_common import load_source_json
from risk_graph import RiskGraph, rows
from production_feedback import record_learning


def build_fixture(repo):
    """Actual disposable application, executable regression and incident record."""
    (repo/'app.py').write_text('def accept_port(value):\n    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535\n')
    (repo/'test_app.py').write_text('import unittest\nfrom app import accept_port\nclass PortTests(unittest.TestCase):\n    def test_invalid_port(self):\n        self.assertFalse(accept_port(70000))\n        self.assertFalse(accept_port(True))\n        self.assertTrue(accept_port(443))\n')
    for args in [('init',),('config','user.email','fixture@example.invalid'),('config','user.name','Test Fixture'),('add','app.py','test_app.py'),('commit','-m','Disposable traceability regression')]:
        subprocess.run(['git',*args],cwd=repo,capture_output=True,check=True)
    evidence=capture_control_evidence(repo,'test_app.PortTests.test_invalid_port','test_app.py',['app.py'],['FS-004'],repo/'evidence.json',project_id='trace-test',release_id='REL-test')
    corpus=ROOT/'references/risks/model2'
    raw=rows(corpus/'risk-corpus.jsonl')[0]
    variant=next(r for r in rows(corpus/'risk-context-variants.jsonl') if r['source_risk_id']==raw['risk_id'])
    definition=next(r for r in rows(corpus/'normalized-risk-definitions.jsonl') if r['risk_definition_id']==variant['risk_definition_id'])
    control=next(r for r in load_source_json('baseline_75_controls.json',ROOT)['controls'] if r['no']==4)
    master=json.loads((ROOT.parent/'wed_dev_skill/references/pasv2/requirements.unassessed.json').read_text())
    requirement=next(r for r in master['requirements'] if r['parent_section']=='77')
    code_id='app.py::accept_port'; test_id='test_app.py::PortTests.test_invalid_port'
    records={
        'assessment':{'assessment_id':'RA-test','project_id':'trace-test','risk_context_variant_id':variant['risk_context_variant_id'],'risk_definition_id':variant['risk_definition_id'],'control_ids':['FS-004'],'scope':'Disposable fixture only; not evidence of any production product.'},
        'packet':{'task_packet_id':'TP-test','project_id':'trace-test','assessment_ids':['RA-test'],'requirement_ids':[requirement['requirement_id']],'implementation_refs':[code_id]},
        'gate':{'gate_id':'G4','project_id':'trace-test','release_id':'REL-test','control_ids':['FS-004'],'evidence_ids':[evidence['evidence_id']],'state':'GREEN'},
        'release':{'release_id':'REL-test','project_id':'trace-test','gate_ids':['G4'],'production_authorized':False,'purpose':'Disposable test fixture'},
        'incident':{'incident_id':'INC-test','project_id':'trace-test','release_id':'REL-test','observed_failure':'accept_port accepted out-of-range input before the regression fix'},
    }
    for name,value in records.items():
        (repo/(name+'.json')).write_text(json.dumps(value))
    (repo/'monitoring.json').write_text(json.dumps({'metric':'invalid_port_config_total','alert':'increase > 0 during release validation'}))
    (repo/'runbook.md').write_text('Reject invalid port configuration; restore the previous valid port and rerun the configuration check.\n')
    def ref(path): return {'path':path,'sha256':sha((repo/path).read_bytes())}
    updates={'root_cause':'missing upper bound','trigger':'port 70000','contributing_factors':['boundary omitted'],'missed_detection_reason':'happy-path test only',
             'regression_test':{**ref('test_app.py'),'selector':'test_app.PortTests.test_invalid_port','execution':ref('evidence.execution.json')},
             'monitoring_change':ref('monitoring.json'),'runbook_change':ref('runbook.md')}
    for action in ('architecture_decision','cost_model','security_model'):
        updates[action]={'disposition':'NOT_APPLICABLE','rationale':'Local input boundary fix in a disposable fixture; no architecture, pricing or trust boundary change.','review_trigger':'Extension to an externally configurable production path.'}
    candidate={'definition':{'canonical_name':'Out of Range Port Configuration','category':'Input validation','dimension':'universal','root_cause':'Port validation omits upper bound','failure_mechanism':'Invalid port prevents socket initialization','trigger_conditions':'Port exceeds 65535','prevention_strategy':'Validate inclusive 1..65535 bounds and reject booleans','automated_test':'Force 70000 and verify rejection; accept 443','owner':'Application engineering'}}
    records['learning']=record_learning(repo/'incident.json',updates,candidate,repo/'candidate-queue',repo/'learning.json',repo=repo)
    learning_id=records['learning']['learning_id']
    nodes=[]
    def record(kind,ident,name,value):
        nodes.append({'id':ident,'type':kind,'ref':{'root':'project','path':name+'.json','format':'json','sha256':sha((repo/(name+'.json')).read_bytes())}})
    def catalogue(kind,ident,name,key,value):
        nodes.append({'id':ident,'type':kind,'ref':{'root':'PREOS','path':'references/risks/model2/'+name+'.jsonl','format':'jsonl','key':key,'value':value[key],'record_sha256':canonical_hash(value)}})
    start=raw['source_line_start']; source=source_bytes('source-1')
    source_id=f'source-1:L{start}-{start}'
    nodes.append({'id':source_id,'type':'source_item','ref':{'source_id':'source-1','start_line':start,'end_line':start,'source_sha256':sha(source),'excerpt_sha256':sha(source.decode('utf-8').splitlines()[start-1].encode())}})
    catalogue('normalized_runtime_record',raw['risk_id'],'risk-corpus','risk_id',raw)
    rid=definition['risk_definition_id']+'@'+definition['definition_version']
    catalogue('risk_definition',rid,'normalized-risk-definitions','risk_definition_id',definition)
    catalogue('risk_context_variant',variant['risk_context_variant_id'],'risk-context-variants','risk_context_variant_id',variant)
    nodes.append({'id':'FS-004','type':'control','ref':{'record_sha256':canonical_hash(control)}})
    nodes.append({'id':requirement['requirement_id'],'type':'master_requirement','ref':{'root':'wed_dev_skill','path':'references/pasv2/requirements.unassessed.json','format':'master_requirement','master_path':'references/pasv2/master-prompt.md'}})
    for kind,ident,name in [('risk_assessment','RA-test','assessment'),('task_packet','TP-test','packet'),('evidence',evidence['evidence_id'],'evidence'),('preos_gate','G4','gate'),('release','REL-test','release'),('incident','INC-test','incident'),('learning',learning_id,'learning')]:
        record(kind,ident,name,records.get(name,evidence))
    for kind,ident,path,symbol in [('implementation_artifact',code_id,'app.py','accept_port'),('test',test_id,'test_app.py','PortTests.test_invalid_port')]:
        nodes.append({'id':ident,'type':kind,'ref':{'root':'project','path':path,'format':'python','symbol':symbol,'sha256':sha((repo/path).read_bytes())}})
    edges=[('PRESERVES',source_id,raw['risk_id']),('NORMALIZES',raw['risk_id'],rid),('VARIANT_OF',variant['risk_context_variant_id'],rid),('ASSESSES',variant['risk_context_variant_id'],'RA-test'),('MITIGATED_BY','RA-test','FS-004'),('ADDRESSES','RA-test','TP-test'),('IMPLEMENTS',requirement['requirement_id'],'TP-test'),('DELIVERS','TP-test',code_id),('TESTED_BY',code_id,test_id),('PRODUCES',test_id,evidence['evidence_id']),('SATISFIES',evidence['evidence_id'],'G4'),('DECIDES','G4','REL-test'),('OBSERVED_IN','REL-test','INC-test'),('LEARNS','INC-test',learning_id)]
    graph={'project_id':'trace-test','unit_type':'operational','phase':'incident-learning','nodes':nodes,'edges':[{'type':k,'from':a,'to':b} for k,a,b in edges]}
    (repo/'graph.json').write_text(json.dumps(graph))
    return graph


class LifecycleResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.graph=build_fixture(self.repo)
        self.roots={'PREOS':ROOT,'wed_dev_skill':ROOT.parent/'wed_dev_skill','project':self.repo}

    def test_real_source_to_incident_chain_resolves_and_queries(self):
        result=validate_operational_graph(self.graph,self.roots)
        self.assertEqual(result['nodes'],15)
        graph=RiskGraph()
        for query in ('mitigated-by','affected-gates','evidence','incidents'):
            result=graph.query(query,project_graph=self.repo/'graph.json')
            self.assertEqual(result['total_matches'],1,query)

    def test_disconnected_edge_and_forged_resolves_flag_fail(self):
        for mutation in ('missing','type','flag','join'):
            graph=copy.deepcopy(self.graph)
            if mutation=='missing': graph['edges'].pop()
            if mutation=='type': graph['edges'][0]['type']='TRACE_TO'
            if mutation=='flag': graph['nodes'][0]['resolves']=True
            if mutation=='join': graph['edges'][0]['to']='FS-004'
            with self.assertRaises(ValueError,msg=mutation):
                validate_operational_graph(graph,self.roots)

    def test_artifact_identity_hash_and_scope_are_checked(self):
        for field,value in [('assessment_id','WRONG'),('project_id','different-project'),('risk_context_variant_id','MISSING')]:
            path=self.repo/'assessment.json'
            original=path.read_bytes()
            record=json.loads(original);record[field]=value;path.write_text(json.dumps(record))
            graph=copy.deepcopy(self.graph)
            next(n for n in graph['nodes'] if n['type']=='risk_assessment')['ref']['sha256']=sha(path.read_bytes())
            with self.assertRaises(ValueError,msg=field): validate_operational_graph(graph,self.roots)
            path.write_bytes(original)

    def test_rebinding_changed_implementation_does_not_refresh_old_evidence(self):
        path=self.repo/'app.py';path.write_text(path.read_text()+'\n# changed implementation\n')
        next(n for n in self.graph['nodes'] if n['type']=='implementation_artifact')['ref']['sha256']=sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'evidence is invalid'):
            validate_operational_graph(self.graph,self.roots)

    def test_test_node_cannot_claim_to_exercise_unreferenced_implementation(self):
        path=self.repo/'test_app.py';path.write_text(path.read_text().replace('accept_port(', 'bool('))
        next(n for n in self.graph['nodes'] if n['type']=='test')['ref']['sha256']=sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'TESTED_BY'):
            validate_operational_graph(self.graph,self.roots)


if __name__=='__main__':
    unittest.main()
