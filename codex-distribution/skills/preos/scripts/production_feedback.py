"""Capture incident learning and submit a candidate without canonical mutation."""
import argparse
import hashlib
import json
from pathlib import Path

from candidate_workflow import submit, validate_journal
from runtime_state import atomic_write_json

CORE=('root_cause','trigger','contributing_factors','missed_detection_reason')
ARTIFACTS=('regression_test','monitoring_change','runbook_change')
CONDITIONAL=('architecture_decision','cost_model','security_model')


def artifact_reference(repo,ref):
    if not isinstance(ref,dict) or not ref.get('path') or not ref.get('sha256'):
        raise ValueError('feedback action requires an actual artifact reference and hash')
    path=(Path(repo)/ref['path']).resolve()
    if not path.is_relative_to(Path(repo).resolve()) or not path.is_file():
        raise ValueError('feedback artifact does not resolve inside project')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError('feedback artifact changed')
    return path


def validate_learning(learning,repo):
    if not all(learning.get(f) for f in ('learning_id','project_id','incident_id',*CORE)):
        raise ValueError('incident learning is missing cause/trigger/contributing factors/missed detection')
    incident_path=artifact_reference(repo,learning['incident'])
    incident=json.loads(incident_path.read_text(encoding='utf-8'))
    if incident['incident_id']!=learning['incident_id'] or incident['project_id']!=learning['project_id']:
        raise ValueError('learning incident identity/project mismatch')
    for action in ARTIFACTS:
        artifact_reference(repo,learning[action])
    regression=learning['regression_test']
    if not regression.get('selector') or not regression.get('execution'):
        raise ValueError('regression learning requires a recorded test execution')
    execution_path=artifact_reference(repo,regression['execution'])
    execution=json.loads(execution_path.read_text(encoding='utf-8'))
    if execution.get('selector')!=regression['selector'] or execution.get('returncode')!=0 or execution.get('tests_executed') is not True:
        raise ValueError('incident regression failed or was not executed')
    for action in CONDITIONAL:
        decision=learning.get(action,{})
        if decision.get('disposition')=='NOT_APPLICABLE':
            if not decision.get('rationale') or not decision.get('review_trigger'):
                raise ValueError('conditional feedback deferral requires rationale and review trigger')
        else:
            artifact_reference(repo,decision)
    candidate_path=artifact_reference(repo,learning['candidate'])
    state=json.loads(candidate_path.read_text(encoding='utf-8'))
    validate_journal(state)
    provenance=state['candidate']['source']
    if provenance.get('kind')!='incident' or provenance.get('reference')!=learning['incident_id'] or provenance.get('incident_sha256')!=learning['incident']['sha256']:
        raise ValueError('incident candidate provenance does not match captured incident')
    return {'learning_id':learning['learning_id'],'candidate_id':state['candidate_id'],'canonical_mutation':False,'actions_accounted':12}


def record_learning(incident_path,updates,candidate,queue,output,*,repo):
    repo=Path(repo).resolve(); incident_path=Path(incident_path).resolve()
    if not incident_path.is_relative_to(repo):
        raise ValueError('incident must be an artifact in the project')
    incident=json.loads(incident_path.read_text(encoding='utf-8'))
    incident_hash=hashlib.sha256(incident_path.read_bytes()).hexdigest()
    if not incident.get('incident_id') or not incident.get('project_id') or not incident.get('observed_failure'):
        raise ValueError('incident capture requires identity, project and observed failure')
    proposal=dict(candidate)
    proposal['source']={'kind':'incident','reference':incident['incident_id'],'incident_sha256':incident_hash}
    proposal['provenance_class']='ENGINEERING_EXPANSION'
    queue=Path(queue).resolve()
    if not queue.is_relative_to(repo):
        raise ValueError('incident queue must stay inside project state')
    candidate_path=Path(submit(proposal,queue))
    learning={**updates,'learning_id':'LEARN-'+incident_hash[:20].upper(),'project_id':incident['project_id'],
              'incident_id':incident['incident_id'],'incident':{'path':incident_path.relative_to(repo).as_posix(),'sha256':incident_hash},
              'candidate':{'path':candidate_path.relative_to(repo).as_posix(),'sha256':hashlib.sha256(candidate_path.read_bytes()).hexdigest()}}
    validate_learning(learning,repo)
    atomic_write_json(Path(output),learning)
    return learning


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--incident',type=Path,required=True)
    parser.add_argument('--updates',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--queue',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=record_learning(args.incident,json.loads(args.updates.read_text()),json.loads(args.candidate.read_text()),args.queue,args.output,repo=args.repo)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
