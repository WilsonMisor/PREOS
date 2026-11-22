"""Source 2 requirements feed existing PREOS gates with objective evidence."""
import argparse
import json
from pathlib import Path
from four_source_audit import rows

ROOT=Path(__file__).resolve().parents[1]
UNITS=ROOT/'references/readiness/source2-readiness-units.jsonl'

def select(*,domain=None,keyword=None,ids=None,limit=25):
    if not 1<=limit<=250: raise ValueError('readiness selection limit must be 1..250')
    result=[]
    for unit in rows(UNITS):
        if domain and unit['readiness_domain_id']!=domain:continue
        if keyword and keyword.casefold() not in unit['excerpt'].casefold():continue
        if ids and unit['source_unit_id'] not in ids:continue
        result.append(unit)
        if len(result)==limit:break
    return result

def evaluate(contract,evidence=None,*,repo=None,approval_root=None):
    from control_assurance import evaluate_evidence
    if not contract.get('readiness_requirements'):return {'results':[],'blocked':False,'conditional':False}
    evidence=evidence or {}; catalogue={r['source_unit_id']:r for r in rows(UNITS)}; result=[]; seen=set()
    for request in contract.get('readiness_requirements',[]):
        uid=request['source_unit_id']
        if uid in seen or uid not in catalogue:raise ValueError('duplicate or orphan readiness requirement: '+uid)
        seen.add(uid);unit=catalogue[uid];status=request.get('status','UNKNOWN');reasons=[]
        if status not in {'PASS','CONDITIONAL PASS','FAIL','NOT APPLICABLE','UNKNOWN'}:raise ValueError('unsupported Source 2 readiness status')
        scope=request.get('applicability','UNKNOWN')
        if status=='NOT APPLICABLE':
            valid=scope=='NOT_APPLICABLE' and bool(request.get('applicability_rationale')) and bool(request.get('applicability_basis'))
            state='NOT_APPLICABLE' if valid else 'UNKNOWN'
            if not valid:reasons=['NOT APPLICABLE requires explicit scope, rationale and an inspectable basis']
        elif scope!='APPLICABLE': state='UNKNOWN';reasons=['readiness applicability is unresolved']
        elif status=='FAIL':state='RED';reasons=['applicable readiness requirement failed']
        elif status=='UNKNOWN':state='UNKNOWN';reasons=['readiness status unknown']
        else:
            reasons=evaluate_evidence(evidence.get(uid),repo,uid,project_id=contract.get('project_id'),release_id=contract.get('release_id')) if repo else ['live repository required for objective evidence']
            state='RED' if reasons else ('AMBER' if status=='CONDITIONAL PASS' else 'GREEN')
            if status=='CONDITIONAL PASS' and not request.get('conditions'):
                reasons.append('conditional pass requires explicit conditions');state='UNKNOWN'
            if status=='CONDITIONAL PASS':
                from risk_concern_runtime import verify_acceptance_authority
                matches=[r for r in contract.get('risk_acceptances',[]) if r.get('acceptance_id')==request.get('acceptance_id') and r.get('acceptance_id')]
                try:
                    if len(matches)!=1 or uid not in matches[0].get('readiness_requirement_ids',[]) or not verify_acceptance_authority(matches[0],approval_root):
                        raise ValueError('conditional pass requires current, human-approved acceptance bound to this readiness requirement')
                except ValueError as exc:state='HUMAN REVIEW';reasons.append(str(exc))
            if unit['mapping_status']=='HUMAN_REVIEW_REQUIRED':
                state='HUMAN REVIEW';reasons.append('source requirement interpretation requires review')
        blocking=request.get('blocking',True) is not False
        result.append({'source_unit_id':uid,'readiness_domain_id':unit['readiness_domain_id'],'state':state,
            'gates':unit['preos_gates'] or ['G11'],'blocking':blocking,'reasons':reasons,
            'release_authority':'existing PREOS gates only'})
    return {'results':result,'blocked':any(r['blocking'] and r['state'] in {'RED','UNKNOWN','HUMAN REVIEW'} for r in result),
            'conditional':any(r['state']=='AMBER' for r in result)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--domain');p.add_argument('--keyword');p.add_argument('--limit',type=int,default=25);a=p.parse_args()
    print(json.dumps(select(domain=a.domain,keyword=a.keyword,limit=a.limit),indent=2))
