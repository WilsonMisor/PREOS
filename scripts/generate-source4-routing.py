"""Bind Source 4 roles and required artifact views to existing authorities."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CROSSWALK=ROOT/'references/integration/source4-production-assurance-crosswalk.json'
ROLE_ORDINALS=[[17,13,10],[10,18],[20],[24],[13,14],[17],[19],[23],[1,10],[30],[25],[27],[26],[33],[22],[38],[39],[4,20,23]]

def build(blueprint):
    from risk_field_crosswalk import write_crosswalks
    write_crosswalks()
    registry=json.loads((blueprint/'references/virtual-team/role-registry.json').read_text(encoding='utf-8'))
    roles={r['ordinal']:r for r in registry['roles']}
    cx=json.loads(CROSSWALK.read_text(encoding='utf-8'))
    for row,ordinals in zip(cx['role_crosswalk'],ROLE_ORDINALS,strict=True):
        selected=[roles[n] for n in ordinals]
        row.update(canonical_role_ids=[r['id'] for r in selected],virtual_team_agents=sorted({'vt_'+r['team_id'].replace('-','_') for r in selected}),
                   mapping_kind='EXACT_ROLE' if len(selected)==1 and row['role'].casefold()==selected[0]['name'].casefold() else 'RESPONSIBILITY_EQUIVALENT',
                   registry='wed_dev_skill/references/virtual-team/role-registry.json',authority='read-only specialist by default; implementation only through bounded Blueprint AI Task Packet; no release or risk acceptance authority',
                   missing_context_behavior='BLOCKED_MISSING_ROLE_CONTEXT; UNKNOWN and ROLE GAP remain explicit')
    cx['conflict_and_supersession_register']=[
        {'source_concept':'single 37-field Atomic Risk Record','decision':'Lossless input projection into existing six concern schemas; no monolithic mutable runtime authority','artifact':'references/risks/model2/concern-separation-crosswalk.json'},
        {'source_concept':'standalone production gates','decision':'Feed PREOS G0-G11; no competing release namespace','artifact':'scripts/control_assurance.py'},
        {'source_concept':'generated risks become catalogue entries','decision':'Candidates require versioned promotion and durable scoped human approval','artifact':'scripts/candidate_workflow.py'},
        {'source_concept':'large combined specialist role','decision':'Map to canonical Blueprint roles; selectively route relevant specialist context','artifact':'wed_dev_skill/references/virtual-team/role-registry.json'},
        {'source_concept':'template status and owner fields','decision':'Preserve source provenance; never infer project status or human approval','artifact':'scripts/risk_field_crosswalk.py'}]
    from source_semantics import validate as validate_semantics
    cx['semantic_coverage']=validate_semantics()['source-4']
    views=[('original-master-prompt.source-manifest.json','source-package/four-sources/manifest.json','/sources/3'),
           ('original-master-prompt.semantic-units.jsonl','references/source-units/PASV2_V5_SOURCE_SEMANTIC_UNITS.jsonl','source_id=source-4-original-master-prompt'),
           ('semantic-coverage-report.md','references/integration/source4-transformation-report.md','Semantic coverage'),
           ('semantic-coverage-summary.json',CROSSWALK.relative_to(ROOT).as_posix(),'/semantic_coverage'),
           ('role-crosswalk.json',CROSSWALK.relative_to(ROOT).as_posix(),'/role_crosswalk'),
           ('role-crosswalk.md','references/integration/source4-transformation-report.md','Canonical roles')]
    for name,key in [('primary-objective','production_questions'),('context-engine','context_dimensions'),('full-stack-domain','full_stack_domains')]:
        views.append((name+'-crosswalk.json',CROSSWALK.relative_to(ROOT).as_posix(),'/'+key))
    views.append(('full-stack-domain-crosswalk.md','references/integration/source4-transformation-report.md','Full-stack domains'))
    for name,key in [('threat-stage','threat_stages'),('maturity-stage','maturity_stages'),('nondeferrable-control','nondeferrable_controls'),('testing-framework','test_families'),('atomic-risk-record','atomic_field_crosswalk'),('output-structure','output_structure'),('skill-capability','skill_capability_crosswalk')]:
        views.append((name+'-crosswalk.json',CROSSWALK.relative_to(ROOT).as_posix(),'/'+key))
    views.extend([('conflict-and-supersession-register.json',CROSSWALK.relative_to(ROOT).as_posix(),'/conflict_and_supersession_register'),('transformation-report.md','references/integration/source4-transformation-report.md','Source 4 transformation')])
    cx['transformation_artifacts']=[{'required_name':'source-4-'+name,'canonical_path':path,'selector':selector,'decision':'Extend the existing canonical crosswalk/ledger/report; do not create competing copies.'} for name,path,selector in views]
    CROSSWALK.write_text(json.dumps(cx,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    report=['# Source 4 transformation','','## Semantic coverage','',f"All {cx['semantic_coverage']['units']} meaningful source units are hash-bound and addressable through scripts/source_semantics.py. Selection does not claim application implementation or approval.",'','## Canonical roles','']
    report+=['- '+r['role']+': '+', '.join(r['canonical_role_ids'])+' ('+r['mapping_kind']+').' for r in cx['role_crosswalk']]
    report+=['','## Full-stack domains','']
    report+=['- '+str(d.get('name',d.get('title',d.get('domain'))))+': '+str(len(d['concerns']))+' source concerns.' for d in cx['full_stack_domains']]
    report+=['','## Runtime and authority','','The five PREOS engines remain the runtime owners. Source 4 field inputs project losslessly into the six existing concerns. Readiness feeds G0-G11. Production evidence and human risk acceptance must be supplied in project context. Model 2 activation remains pending human approval.','','## Artifact consolidation','',f"The {len(views)} requested transformation artifacts resolve through transformation_artifacts in source4-production-assurance-crosswalk.json. Tests independently reparse preserved input bytes and verify exact source lines."]
    (ROOT/'references/integration/source4-transformation-report.md').write_text('\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    return {'roles':len(cx['role_crosswalk']),'canonical_roles_referenced':len({rid for row in cx['role_crosswalk'] for rid in row['canonical_role_ids']}),'field_crosswalks':[37,40]}

def validate(blueprint):
    registry=json.loads((blueprint/'references/virtual-team/role-registry.json').read_text(encoding='utf-8'))
    roles={r['ordinal']:r for r in registry['roles']};cx=json.loads(CROSSWALK.read_text(encoding='utf-8'))
    for row,ordinals in zip(cx['role_crosswalk'],ROLE_ORDINALS,strict=True):
        if row.get('canonical_role_ids')!=[roles[n]['id'] for n in ordinals]:raise ValueError('Source 4 canonical role mapping drift')
        if row.get('virtual_team_agents')!=sorted({'vt_'+roles[n]['team_id'].replace('-','_') for n in ordinals}):raise ValueError('Source 4 team routing drift')
        if 'BLOCKED_MISSING_ROLE_CONTEXT' not in row.get('missing_context_behavior',''):raise ValueError('missing role-context stop condition')
    return {'roles':len(cx['role_crosswalk']),'status':'PASS'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--blueprint',type=Path,default=ROOT.parent/'wed_dev_skill');p.add_argument('--check',action='store_true');a=p.parse_args()
    if not a.check:build(a.blueprint)
    print(json.dumps(validate(a.blueprint),indent=2))
