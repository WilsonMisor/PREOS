#!/usr/bin/env python3
"""Nondeferrable controls and evidence-backed gate decisions. No release authority."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from assurance_engines import normalize_project_context, source4
from preos_common import load_source_json
from runtime_state import atomic_write_json, evidence_binding_reasons, environment_binding, git_snapshot
from risk_concern_runtime import verify_acceptance_authority
from schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
# Semantic links to immutable controls, not ordinal equality. NDC IDs identify
# the additional Source-4 acceptance condition where a baseline control is broad.
CONTROL_LINKS = [([21,24],'G4'),([21,27,28],'G5'),([75],'G3'),([74,75],'G3'),([39,47,74],'G3'),([3],'G3'),([75],'G3'),([21,23,24,27],'G4'),([72],'G7'),([66,72],'G7'),([4],'G3'),([12,18,55],'G5'),([61,75],'G9'),([61,63],'G9'),([75],'G3'),([70],'G8'),([54],'G7'),([27,28],'G5'),([4,75],'G3'),([52],'G8')]


def nondeferrable_control_map():
    baseline={f"FS-{c['no']:03d}":c for c in load_source_json('baseline_75_controls.json',ROOT)['controls']}
    result=[]
    for source,(numbers,gate) in zip(source4()['nondeferrable_controls'],CONTROL_LINKS,strict=True):
        ids=[f'FS-{n:03d}' for n in numbers]
        if not all(i in baseline for i in ids):
            raise ValueError('nondeferrable mapping references absent baseline control')
        result.append({'nondeferrable_control_id':f"NDC-{source['number']:02d}",'source4_text':source['text'],'source_line':source['line'],'preos_control_ids':ids,'baseline_acceptance':[baseline[i]['gate_and_acceptance_condition'] for i in ids],'gate':gate,'evidence_requirement':f"Executable evidence specific to {source['text'].lower()}, in addition to linked baseline controls."})
    return result


def applicability(control_id, contract):
    if contract.get('documentation_only') is True:
        return 'NOT_APPLICABLE','Documentation-only change does not introduce a production execution path.'
    if contract.get('production_intent') is False and contract.get('first_production_release') is not True:
        return 'NOT_APPLICABLE','Explicit non-production scope; reevaluate before first real production release.'
    context=normalize_project_context(contract)
    if control_id in {'NDC-02','NDC-18'}:
        if context['money_movement'] is False:
            return 'NOT_APPLICABLE','Project Contract explicitly excludes monetary representation and money movement.'
        if context['money_movement'] is None:
            return 'UNKNOWN','Money movement classification is unknown.'
    if control_id=='NDC-05':
        if context['tenant_model'] in {'single-tenant','no-tenancy'}:
            return 'NOT_APPLICABLE','Project Contract explicitly declares no shared tenant boundary.'
        if context['tenant_model']=='UNKNOWN':
            return 'UNKNOWN','Tenant model is unknown.'
    if control_id=='NDC-17' and contract.get('external_dependencies')==[] and contract.get('external_providers')==[]:
        return 'NOT_APPLICABLE','Both external dependencies and providers are explicitly absent.'
    return 'APPLICABLE','Production control applies independently of product size or maturity.'


def file_binding(repo, relative):
    path=(repo/relative).resolve()
    if not path.is_relative_to(repo.resolve()) or not path.is_file():
        raise ValueError('evidence input must be an existing repository file')
    return {'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def capture_control_evidence(repo, selector, test_file, source_files, control_ids, output, *, environment='test', project_id=None, release_id=None):
    repo=Path(repo).resolve()
    artifact=Path(output).with_suffix('.execution.json')
    if Path(output).exists() or artifact.exists():
        raise ValueError('evidence history is immutable; use a new output for replacement evidence')
    if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,}',selector):
        raise ValueError('exact unittest method selector required')
    if not source_files or not control_ids:
        raise ValueError('evidence requires implementation bindings and control identities')
    before={'git_head':git_snapshot(repo)['head'],'source_hashes':[file_binding(repo,p) for p in source_files],'configuration_files':[],'schema_files':[],'dependency_files':[],'test_definition_files':[file_binding(repo,test_file)],'environment':environment_binding([])}
    if not before['git_head']:
        raise ValueError('evidence requires a Git commit binding')
    proc=subprocess.run([sys.executable,'-m','unittest',selector],cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    execution={'selector':selector,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'tests_executed':not bool(re.search(r'Ran 0 tests|OK \(skipped=',proc.stderr))}
    atomic_write_json(artifact,execution)
    record={'evidence_id':'E-'+hashlib.sha256((selector+str(artifact)).encode()).hexdigest()[:20],'project_id':project_id,'release_id':release_id,'produced_at':datetime.now(timezone.utc).isoformat(),'producer':'PREOS/scripts/control_assurance.py::capture_control_evidence','environment':environment,'artifact_location':str(artifact.resolve()),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'validity':'CURRENT','commit_sha':before['git_head'],'control_ids':control_ids,'bindings':before}
    reasons=evidence_binding_reasons(record,git_snapshot(repo),repo)
    if reasons:
        record['validity']='STALE'
    atomic_write_json(Path(output),record)
    return record


def evaluate_evidence(record, repo, control_id, *, project_id=None, release_id=None):
    if not isinstance(record,dict):
        return ['structured execution evidence missing']
    try:
        validate_instance(record,json.loads((ROOT/'schemas/evidence-record.schema.json').read_text()))
        if record.get('validity')!='CURRENT':
            return ['evidence is not current']
        if control_id not in record.get('control_ids',[]):
            return ['evidence does not prove this specific control']
        for name,expected in [('project_id',project_id),('release_id',release_id)]:
            if expected is not None and record.get(name)!=expected:
                return [f'evidence {name} scope mismatch']
        bindings=record['bindings']
        required={'git_head','source_hashes','configuration_files','schema_files','dependency_files','test_definition_files','environment'}
        if not required<=bindings.keys() or not bindings['source_hashes'] or not bindings['test_definition_files']:
            return ['complete code/test/environment freshness bindings required']
        if record.get('commit_sha')!=bindings['git_head']:
            return ['commit binding mismatch']
        reasons=evidence_binding_reasons(record,git_snapshot(Path(repo)),Path(repo))
        artifact=Path(record['artifact_location'])
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=record.get('artifact_sha256'):
            return reasons+['execution artifact missing or changed']
        execution=json.loads(artifact.read_text(encoding='utf-8'))
        if execution.get('returncode')!=0 or execution.get('tests_executed') is not True:
            reasons.append('required executable test failed or was skipped')
        produced=datetime.fromisoformat(record['produced_at'].replace('Z','+00:00'))
        if produced.tzinfo is None or produced>datetime.now(timezone.utc):
            reasons.append('invalid evidence production time')
        return reasons
    except (ValueError,KeyError,OSError,TypeError) as exc:
        return [str(exc)]


def evaluate_nondeferrable_controls(contract, evidence=None, *, repo=None):
    evidence=evidence or {}
    results=[]
    for control in nondeferrable_control_map():
        cid=control['nondeferrable_control_id']
        applies,rationale=applicability(cid,contract)
        requested=contract.get('control_dispositions',{}).get(cid)
        if requested=='NOT_APPLICABLE' and applies!='NOT_APPLICABLE':
            reasons=['requested NOT_APPLICABLE contradicts deterministic applicability']
        elif applies=='NOT_APPLICABLE':
            reasons=[]
        elif applies=='UNKNOWN':
            reasons=[rationale]
        elif repo is None:
            reasons=['live repository required to verify evidence freshness']
        else:
            reasons=evaluate_evidence(evidence.get(cid),repo,cid,project_id=contract.get('project_id'),release_id=contract.get('release_id'))
        state='NOT_APPLICABLE' if applies=='NOT_APPLICABLE' else ('SATISFIED' if not reasons else 'BLOCKING_MISSING_EVIDENCE')
        results.append({**control,'applicability':applies,'applicable':applies=='APPLICABLE','rationale':rationale,'state':state,'blockers':reasons})
    return {'blocked':any(r['blockers'] for r in results),'results':results}


def evidence_gate_engine(contract, evidence=None, *, repo=None, approval_root=None):
    from readiness_assurance import evaluate as evaluate_readiness
    controls=evaluate_nondeferrable_controls(contract,evidence,repo=repo)
    readiness=evaluate_readiness(contract,evidence,repo=repo,approval_root=approval_root)
    blockers=[{'control':r['nondeferrable_control_id'],'gate':r['gate'],'reasons':r['blockers']} for r in controls['results'] if r['blockers']]
    blockers.extend({'requirement':r['source_unit_id'],'gate':gate,'reasons':r['reasons']} for r in readiness['results'] if r['blocking'] and r['state'] in {'RED','UNKNOWN','HUMAN REVIEW'} for gate in r['gates'])
    for acceptance in contract.get('risk_acceptances',[]):
        try:
            if not verify_acceptance_authority(acceptance, approval_root):
                blockers.append({'gate':'G11','reasons':['risk acceptance expired, revoked or stale']})
        except ValueError as exc:
            blockers.append({'gate':'G11','reasons':[str(exc)]})
    states=contract.get('required_assurance_states',[])
    if any(state not in {'GREEN','AMBER'} for state in states):
        blockers.append({'gate':'G11','reasons':['required RED, UNKNOWN or HUMAN REVIEW remains unresolved']})
    state='RED' if blockers else ('AMBER' if 'AMBER' in states or readiness['conditional'] else 'GREEN')
    if not evidence and not all(r['applicability']=='NOT_APPLICABLE' for r in controls['results']):
        state='RED'
    return {'engine':'Evidence and Gate Engine','nondeferrable':controls,'readiness':readiness,'gate_state':state,'blockers':blockers,'production_authorized':False,'acceptance_authority':'qualified human only','release_boundary':'Technical evidence never grants PRODUCTION_RELEASE_AUTHORITY.'}
