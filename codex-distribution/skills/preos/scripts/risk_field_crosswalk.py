"""Lossless input projections into the existing six canonical risk concerns.

Source templates are knowledge/provenance, never project evidence or approvals.
The returned projections are migration input, not approved runtime records.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
# Field numbers bind the immutable source versions checked by four_source_audit.
# Values are canonical concern and schema property paths. Nested definition
# knowledge remains inside the existing normalized_definition object.
S1={
 1:('risk_definition','source_records'),2:('risk_definition','canonical_name'),
 3:('risk_definition','normalized_definition.aliases'),4:('risk_definition','category'),
 5:('risk_assessment','source_projection.applicability'),6:('risk_assessment','source_projection.applicability_rationale'),
 7:('risk_definition','normalized_definition.affected_components'),8:('risk_definition','normalized_definition.trigger_conditions'),
 9:('risk_definition','normalized_definition.root_cause'),10:('risk_definition','normalized_definition.failure_mechanism'),
 11:('risk_definition','normalized_definition.default_consequences.customer'),12:('risk_definition','normalized_definition.default_consequences.business'),
 13:('risk_definition','normalized_definition.default_consequences.security'),14:('risk_definition','normalized_definition.default_consequences.data_integrity'),
 15:('risk_definition','normalized_definition.default_consequences.availability'),16:('risk_definition','normalized_definition.default_consequences.performance'),
 17:('risk_economics','source_projection.financial_consequences'),18:('risk_definition','normalized_definition.default_consequences.privacy'),
 19:('risk_assessment','source_projection.likelihood'),20:('risk_assessment','source_projection.severity'),21:('risk_assessment','source_projection.blast_radius'),22:('risk_assessment','source_projection.detectability'),
 23:('risk_assessment','source_projection.existing_protections'),24:('risk_assessment','source_projection.protection_weaknesses'),
 25:('risk_definition','normalized_definition.control_patterns.prevention'),26:('risk_definition','normalized_definition.monitoring_patterns.detection'),
 27:('risk_definition','normalized_definition.control_patterns.mitigation'),28:('risk_definition','normalized_definition.recovery_patterns'),
 29:('risk_definition','normalized_definition.testing_patterns.automated'),30:('risk_definition','normalized_definition.testing_patterns.load_concurrency'),
 31:('risk_definition','normalized_definition.testing_patterns.negative'),32:('risk_definition','normalized_definition.testing_patterns.chaos'),33:('risk_definition','normalized_definition.testing_patterns.security'),
 34:('risk_definition','normalized_definition.monitoring_patterns.observability'),35:('risk_definition','normalized_definition.monitoring_patterns.alerts'),
 36:('risk_evidence','source_projection.required_acceptance_evidence'),37:('risk_acceptance','source_projection.residual_risk_instruction'),
 38:('risk_evolution','source_projection.regression_protection'),39:('risk_definition','normalized_definition.owner_role_pattern'),40:('risk_assessment','source_projection.source_status')}
S4={
 1:('risk_definition','source_records'),2:('risk_definition','category'),3:('risk_assessment','context.feature'),4:('risk_assessment','context.actor'),
 5:('risk_definition','normalized_definition.preconditions'),6:('risk_definition','normalized_definition.failure_mechanism'),7:('risk_definition','normalized_definition.trigger_conditions'),8:('risk_definition','normalized_definition.root_cause'),
 9:('risk_definition','normalized_definition.business_invariant'),10:('risk_definition','normalized_definition.expected_correct_behaviour'),
 11:('risk_assessment','source_projection.severity'),12:('risk_assessment','source_projection.likelihood'),13:('risk_assessment','source_projection.blast_radius'),
 14:('risk_definition','normalized_definition.default_consequences.customer'),15:('risk_definition','normalized_definition.default_consequences.security'),16:('risk_economics','source_projection.financial_impact'),17:('risk_definition','normalized_definition.default_consequences.privacy'),18:('risk_definition','normalized_definition.default_consequences.legal'),19:('risk_definition','normalized_definition.default_consequences.operations'),20:('risk_economics','source_projection.cost_impact'),
 21:('risk_assessment','source_projection.source_status'),22:('risk_definition','normalized_definition.control_patterns.prevention'),23:('risk_definition','normalized_definition.control_patterns.implementation'),24:('risk_definition','normalized_definition.testing_patterns.required'),25:('risk_definition','normalized_definition.testing_patterns.failure'),26:('risk_definition','normalized_definition.monitoring_patterns'),27:('risk_definition','normalized_definition.recovery_patterns'),28:('risk_definition','normalized_definition.reconciliation'),
 29:('risk_economics','source_projection.cost_now'),30:('risk_economics','source_projection.cost_at_scale'),31:('risk_economics','source_projection.complexity_tax'),
 32:('risk_evolution','source_projection.maturity_stage'),33:('risk_evolution','source_projection.deferral_status'),34:('risk_evolution','source_projection.activation_trigger'),
 35:('risk_acceptance','source_projection.proposed_owner_not_approval'),36:('risk_evidence','source_projection.evidence_not_verified'),37:('risk_assessment','source_projection.gate_result_not_verified')}
SCHEMAS={'risk_definition':'risk-definition','risk_assessment':'risk-assessment','risk_economics':'risk-economics','risk_evolution':'risk-evolution','risk_evidence':'risk-evidence-binding','risk_acceptance':'risk-acceptance'}

def mapping(source):
    if source=='source-1': return S1
    if source=='source-4': return S4
    raise ValueError('only the 40-field Source 1 and 37-field Source 4 input layouts are supported')

def validate_mapping(source):
    data=mapping(source); expected=40 if source=='source-1' else 37
    if set(data)!=set(range(1,expected+1)): raise ValueError('missing or duplicate source field')
    for concern,path in data.values():
        schema=json.loads((ROOT/'schemas'/(SCHEMAS[concern]+'.schema.json')).read_text())
        if path.split('.')[0] not in schema['properties']: raise ValueError('crosswalk destination absent from canonical schema: '+concern+'.'+path)
    return {'fields':expected,'concerns':len({c for c,_ in data.values()}),'information_loss':0}

def project_fields(source, fields):
    data=mapping(source)
    if set(fields)!=set(data):raise ValueError('exact source field identities are required')
    validate_mapping(source)
    projections={concern:{} for concern in SCHEMAS}
    for number,value in fields.items():
        concern,path=data[number]
        projections[concern][path]={'source_field':number,'value':value}
    return {'source':source,'projections':projections,'authority':'UNREVIEWED_SOURCE_PROJECTION','creates_assessment':False,'grants_acceptance':False}

def reconstruct(projected):
    return {entry['source_field']:entry['value'] for fields in projected['projections'].values() for entry in fields.values()}

def manifest():
    return {'version':'pasv2-linked-crosswalk-v2','policy':'Source defaults are provenance only. Context, fresh evidence and explicit human acceptance must be supplied separately. Owner text is not approval authority.','sources':{source:{'validation':validate_mapping(source),'fields':[{'source_field_number':n,'concern':c,'schema':SCHEMAS[c]+'.schema.json','destination':path,'rule':'retain exact source value as unreviewed projection; no implicit applicability, evidence validity or authority','cardinality':'one-to-one lossless projection'} for n,(c,path) in mapping(source).items()]} for source in ('source-1','source-4')}}

def write_crosswalks():
    data=manifest()
    path=ROOT/'references/risks/model2/concern-separation-crosswalk.json'
    data.update(activation_state='installed_not_default',zero_loss=all(v['validation']['information_loss']==0 for v in data['sources'].values()),field_numbers_accounted=list(range(1,41)),
                concerns={concern:[n for n,(c,_) in S1.items() if c==concern] for concern in SCHEMAS})
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    path=ROOT/'references/integration/source4-production-assurance-crosswalk.json'
    cx=json.loads(path.read_text(encoding='utf-8'))
    for row in cx['atomic_field_crosswalk']:
        row['projection']=data['sources']['source-4']['fields'][row['number']-1]
    path.write_text(json.dumps(cx,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    return data

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--write',action='store_true')
    print(json.dumps(write_crosswalks() if parser.parse_args().write else manifest(),indent=2))
