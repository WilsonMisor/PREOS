#!/usr/bin/env python3
"""Auditable candidate intake and controlled versioned catalogue promotion.

Context generation and incident learning can only submit candidates. Publication
requires a separate durable PREOS human approval scoped to the exact plan hash.
The old corpus is immutable; a completed version is published with one pointer
replacement after regression and referential-integrity checks succeed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from runtime_state import atomic_write_json, load_approvals, authority_is_human
from schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_CLASSES = {'SOURCE_DIRECT','SOURCE_IMPLIED','ENGINEERING_EXPANSION','EXTERNAL_RESEARCH_REQUIRED','QUALIFIED_HUMAN_REVIEW_REQUIRED'}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_rows(path, rows):
    Path(path).write_bytes(b''.join(canonical_bytes(row)+b'\n' for row in rows))


def semantic_findings(candidate):
    body = candidate.get('definition', {})
    required = ('canonical_name','category','dimension','root_cause','failure_mechanism','trigger_conditions','prevention_strategy','automated_test','owner')
    findings = [f'missing semantic field: {field}' for field in required if not isinstance(body.get(field), str) or not body[field].strip()]
    if body.get('dimension') not in {'universal','industry','product','jurisdiction','architecture'}:
        findings.append('invalid risk dimension')
    if body.get('canonical_name', '').casefold() == 'serialization failure' and re.search(r'concurrent.*writ|shared.state', body.get('root_cause',''), re.I):
        findings.append('serialization sentinel: concurrency contamination')
    if body.get('canonical_name', '').casefold() == 'drug serialization failure' and re.search(r'sensor|control.system', body.get('root_cause',''), re.I):
        findings.append('drug serialization sentinel: physical-control contamination')
    if any(k in body for k in ('project_id','release_id','assurance_state','risk_acceptance','evidence_freshness')):
        findings.append('reusable definition contains project/release concern')
    return findings


def validate_provenance(candidate):
    if candidate.get('provenance_class') not in PROVENANCE_CLASSES:
        raise ValueError('unsupported provenance class')
    source = candidate.get('source', {})
    if not source.get('reference') or not source.get('kind'):
        raise ValueError('candidate provenance requires source kind and reference')
    if candidate['provenance_class'] == 'EXTERNAL_RESEARCH_REQUIRED':
        research = candidate.get('research', {})
        if not research.get('url', '').startswith(('https://','http://')) or not research.get('retrieved_at'):
            raise ValueError('external research requires a source URL and research date')
        date = datetime.fromisoformat(research['retrieved_at'].replace('Z','+00:00'))
        if date.tzinfo is None or date > datetime.now(timezone.utc):
            raise ValueError('external research date must be past/present and timezone aware')


def deduplicate(candidate, definitions):
    name = ' '.join(candidate['definition']['canonical_name'].casefold().split())
    matches = []
    for definition in definitions:
        names = [definition['canonical_name'], *definition.get('aliases', [])]
        if name in {' '.join(n.casefold().split()) for n in names}:
            matches.append({'risk_definition_id':definition['risk_definition_id'], 'definition_version':definition['definition_version'], 'relationship':'SAME_AS', 'basis':'exact normalized canonical name/alias'})
    return matches


def candidate_id(candidate):
    return 'CAND-RISK-' + sha(candidate)[:24].upper()


def _event(state, stage, details):
    events = state.setdefault('events', [])
    event = {'sequence':len(events)+1, 'stage':stage, 'details':details, 'previous_sha256':events[-1]['sha256'] if events else None}
    event['sha256'] = sha(event)
    events.append(event)


def validate_journal(state):
    previous = None
    for number, event in enumerate(state['events'], 1):
        payload = {k:v for k,v in event.items() if k != 'sha256'}
        if event['sequence'] != number or event['previous_sha256'] != previous or sha(payload) != event['sha256']:
            raise ValueError('candidate audit journal integrity failure')
        previous = event['sha256']
    if state['candidate_id'] != candidate_id(state['candidate']):
        raise ValueError('candidate content no longer matches candidate ID')


def submit(candidate, queue: Path):
    validate_provenance(candidate)
    if semantic_findings(candidate):
        raise ValueError('; '.join(semantic_findings(candidate)))
    cid = candidate_id(candidate)
    queue.mkdir(parents=True, exist_ok=True)
    path = queue / (cid + '.json')
    if path.exists():
        state = read_json(path)
        validate_journal(state)
        return path
    state = {'candidate_id':cid, 'candidate':candidate, 'events':[]}
    _event(state, 'CANDIDATE_RECORDED', {'provenance_class':candidate['provenance_class'], 'source':candidate['source']})
    atomic_write_json(path, state)
    return path


def version_tuple(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('catalogue version must be semantic version')
    return tuple(map(int, version.split('.')))


def catalogue_snapshot(corpus: Path):
    files = ['normalized-risk-definitions.jsonl','risk-relationships.jsonl','catalogue-index.json']
    return {name:hashlib.sha256((corpus/name).read_bytes()).hexdigest() for name in files}


def prepare_promotion(candidate_path: Path, corpus: Path, *, version: str, regression: dict, test_repo: Path):
    state = read_json(candidate_path)
    validate_journal(state)
    validate_provenance(state['candidate'])
    findings = semantic_findings(state['candidate'])
    if findings:
        raise ValueError('; '.join(findings))
    definitions = read_rows(corpus/'normalized-risk-definitions.jsonl')
    matches = deduplicate(state['candidate'], definitions)
    if matches:
        _event(state, 'RELATIONSHIP_REVIEW', {'decision':'LINK_EXISTING', 'matches':matches})
        atomic_write_json(candidate_path, state)
        raise ValueError('duplicate candidate must link existing canonical definition; no new canonical ID')
    current = read_json(corpus/'catalogue-index.json').get('catalogue_version','1.0.0')
    if version_tuple(version) <= version_tuple(current):
        raise ValueError('promotion must increment catalogue version')
    selector = regression.get('selector','')
    if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,}', selector):
        raise ValueError('exact executable unittest regression selector required')
    test_path = (test_repo/regression['path']).resolve()
    if not test_path.is_relative_to(test_repo.resolve()) or not test_path.is_file():
        raise ValueError('regression test must resolve inside its repository')
    # Bind regression bytes before review. The human approves these exact inputs.
    plan = {'candidate_id':state['candidate_id'], 'candidate_sha256':sha(state['candidate']), 'source_snapshot':catalogue_snapshot(corpus), 'previous_version':current, 'catalogue_version':version, 'canonicalization_decision':'NEW_DEFINITION', 'regression':{**regression,'sha256':hashlib.sha256(test_path.read_bytes()).hexdigest()}}
    _event(state, 'RELATIONSHIP_REVIEW', {'decision':'NEW_CANDIDATE','matches':[]})
    _event(state, 'SEMANTIC_RULE_REVIEW', {'findings':findings,'required_human_review':True})
    state['plan'] = plan
    state['plan_sha256'] = sha(plan)
    _event(state, 'PROMOTION_PLAN', {'plan_sha256':state['plan_sha256'],'catalogue_version':version})
    atomic_write_json(candidate_path, state)
    return {'plan':plan,'approval_scope':f"candidate-promotion:{state['plan_sha256']}", 'approval_status':'REQUIRED'}


def require_approval(approval_root: Path, project_id: str, approval_id: str, plan_hash: str):
    state = load_approvals(approval_root, project_id)
    if state.get('project_id') != project_id:
        raise ValueError('approval belongs to another project')
    approval = next((a for a in state['approvals'] if a['approval_id'] == approval_id), None)
    if not approval or approval.get('status') != 'GRANTED':
        raise ValueError('required durable human promotion review is not granted')
    if not authority_is_human(approval.get('authority','')) or not approval.get('rationale'):
        raise ValueError('promotion requires named human authority and review rationale')
    if approval.get('scope') != f'candidate-promotion:{plan_hash}' or approval.get('approval_type') != 'CANONICAL_RISK_PROMOTION':
        raise ValueError('approval is not bound to this candidate plan and catalogue version')
    if approval.get('revoked_at'):
        raise ValueError('promotion approval revoked')
    if approval.get('expires_at'):
        expiry = datetime.fromisoformat(approval['expires_at'].replace('Z','+00:00'))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError('promotion approval expired')
    return approval


def promote(candidate_path: Path, corpus: Path, destination: Path, *, approval_root: Path, project_id: str, approval_id: str, test_repo: Path):
    state = read_json(candidate_path)
    validate_journal(state)
    plan = state.get('plan')
    if not plan or sha(plan) != state.get('plan_sha256'):
        raise ValueError('missing or changed promotion plan')
    if catalogue_snapshot(corpus) != plan['source_snapshot']:
        raise ValueError('catalogue changed after relationship/semantic review')
    if sha(state['candidate']) != plan['candidate_sha256']:
        raise ValueError('candidate changed after review')
    approval = require_approval(approval_root, project_id, approval_id, state['plan_sha256'])
    regression = plan['regression']
    test_path = (test_repo/regression['path']).resolve()
    if not test_path.is_relative_to(test_repo.resolve()) or hashlib.sha256(test_path.read_bytes()).hexdigest() != regression['sha256']:
        raise ValueError('regression test changed after approval')
    proc = subprocess.run([sys.executable,'-m','unittest',regression['selector']], cwd=test_repo, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    if proc.returncode or re.search(r'Ran 0 tests|OK \(skipped=', proc.stderr):
        raise ValueError('candidate regression failed or did not execute: '+proc.stderr[-1500:])
    definitions = read_rows(corpus/'normalized-risk-definitions.jsonl')
    if deduplicate(state['candidate'], definitions):
        raise ValueError('candidate now duplicates canonical record')
    candidate = state['candidate']
    body = candidate['definition']
    rid = 'RDEF-' + sha(body)[:24].upper()
    record = {'risk_definition_id':rid,'definition_version':'1.0.0','canonical_name':body['canonical_name'],'canonical_key':' '.join(body['canonical_name'].casefold().split()),'normalized_definition':body,'provenance_class':candidate['provenance_class'],'source_records':[candidate['source']['reference']],'source_locations':[candidate['source']], 'transformation_version':'candidate-workflow-v1','definition_content_sha256':sha(body),'semantic_review_status':'ACCEPTED_BY_HUMAN'}
    validate_instance(record, read_json(ROOT/'schemas/risk-definition.schema.json'))
    definitions.append(record)
    identities = [f"{d['risk_definition_id']}@{d['definition_version']}" for d in definitions]
    if len(set(identities)) != len(identities):
        raise ValueError('canonical identity collision')
    relations = read_rows(corpus/'risk-relationships.jsonl')
    # Preserve all validated canonical relations; add no invented domain edges.
    for relation in relations:
        for endpoint in ('source','target'):
            node = relation[endpoint]
            if node['type'] == 'RISK_DEFINITION' and node['id'] not in identities:
                raise ValueError('orphan canonical relationship')
    destination = destination.resolve()
    if destination == corpus.resolve() or destination.is_relative_to(corpus.resolve()):
        raise ValueError('publication must be outside the immutable source corpus')
    versions = destination/'versions'
    versions.mkdir(parents=True, exist_ok=True)
    version_path = versions/plan['catalogue_version']
    if version_path.exists():
        raise ValueError('catalogue version already exists; never overwrite published history')
    # Exclusive publication lock prevents lost updates and concurrent promotions.
    lock = destination/'.promotion-lock'
    try:
        fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError('another catalogue publication is active') from exc
    os.close(fd)
    stage = Path(tempfile.mkdtemp(prefix='.promotion-', dir=versions))
    try:
        pointer = destination/'CURRENT.json'
        if pointer.exists() and read_json(pointer)['catalogue_version'] != plan['previous_version']:
            raise ValueError('publication base changed; rebase and repeat human review')
        write_rows(stage/'normalized-risk-definitions.jsonl', definitions)
        write_rows(stage/'risk-relationships.jsonl', relations)
        _event(state,'HUMAN_REVIEW',{'approval_id':approval_id,'authority':approval['authority'],'plan_sha256':state['plan_sha256']})
        _event(state,'REGRESSION_EXECUTED',{'selector':regression['selector'],'test_sha256':regression['sha256'],'stdout':proc.stdout,'stderr':proc.stderr,'returncode':proc.returncode})
        _event(state,'CANONICAL_PROMOTION',{'canonical_id':rid,'catalogue_version':plan['catalogue_version']})
        atomic_write_json(stage/'promotion-audit.json', state)
        index = {'catalogue_version':plan['catalogue_version'],'previous_version':plan['previous_version'],'count':len(definitions),'definitions':identities,'candidate_promotions':{state['candidate_id']:rid},'source_snapshot':plan['source_snapshot'],'relationships':len(relations),'activation_state':'installed_not_default'}
        atomic_write_json(stage/'catalogue-index.json', index)
        stage.rename(version_path)
        # CURRENT is authoritative only after every file in the new version exists.
        atomic_write_json(pointer, {'catalogue_version':plan['catalogue_version'],'path':f"versions/{plan['catalogue_version']}",'index_sha256':hashlib.sha256((version_path/'catalogue-index.json').read_bytes()).hexdigest()})
        atomic_write_json(candidate_path, state)
    finally:
        if stage.exists() and stage.resolve().is_relative_to(versions.resolve()):
            shutil.rmtree(stage)
        lock.unlink()
    return {'candidate_id':state['candidate_id'],'risk_definition_id':rid,'catalogue_version':plan['catalogue_version'],'version_path':str(version_path),'canonical_source_unchanged':catalogue_snapshot(corpus)==plan['source_snapshot']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command',required=True)
    intake = sub.add_parser('submit')
    intake.add_argument('candidate',type=Path)
    intake.add_argument('--queue',type=Path,required=True)
    plan = sub.add_parser('prepare')
    plan.add_argument('candidate',type=Path)
    plan.add_argument('--corpus',type=Path,required=True)
    plan.add_argument('--version',required=True)
    plan.add_argument('--test-repo',type=Path,required=True)
    plan.add_argument('--test-file',required=True)
    plan.add_argument('--test-selector',required=True)
    publish = sub.add_parser('promote')
    publish.add_argument('candidate',type=Path)
    publish.add_argument('--corpus',type=Path,required=True)
    publish.add_argument('--destination',type=Path,required=True)
    publish.add_argument('--approval-root',type=Path,required=True)
    publish.add_argument('--project-id',required=True)
    publish.add_argument('--approval-id',required=True)
    publish.add_argument('--test-repo',type=Path,required=True)
    args = ap.parse_args()
    if args.command == 'submit':
        print(submit(read_json(args.candidate), args.queue))
    elif args.command == 'prepare':
        print(json.dumps(prepare_promotion(args.candidate,args.corpus,version=args.version,
            regression={'path':args.test_file,'selector':args.test_selector},test_repo=args.test_repo),indent=2))
    else:
        print(json.dumps(promote(args.candidate,args.corpus,args.destination,
            approval_root=args.approval_root,project_id=args.project_id,
            approval_id=args.approval_id,test_repo=args.test_repo),indent=2))


if __name__ == '__main__':
    main()
