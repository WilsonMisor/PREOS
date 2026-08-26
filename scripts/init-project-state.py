#!/usr/bin/env python3
from preos_common import runtime_root,dump_json
from pathlib import Path
import argparse,datetime
ap=argparse.ArgumentParser(); ap.add_argument('project_id'); ap.add_argument('--repo',default='.')
a=ap.parse_args(); repo=Path(a.repo).resolve(); governed=repo/'.ai-product-delivery'; dirs=['project-contract','task-packets','approvals','preos/risk-model','preos/control-assessments','preos/architecture-economics','preos/deferred-complexity','preos/gate-state','preos/evidence','preos/risk-acceptance','preos/incidents','preos/traceability']
for d in dirs: (governed/d).mkdir(parents=True,exist_ok=True)
rt=runtime_root()/'projects'/a.project_id/'production'; (rt/'checkpoints').mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); dump_json(rt/'PIPELINE-STATE.json',{'schema_version':'1.0','project_id':a.project_id,'created_at':now,'updated_at':now,'state':'INITIALIZED','current_stage':'project-init'}); dump_json(rt/'CURRENT-STATE.json',{'schema_version':'1.0','project_id':a.project_id,'updated_at':now,'current_stage':'project-init','last_verified_action':'project runtime initialized','next_unverified_action':'bind current Project Contract'}); dump_json(rt/'approval-state.json',{'schema_version':'1.0','project_id':a.project_id,'updated_at':now,'approvals':[]}); dump_json(rt/'evidence-index.json',{'schema_version':'1.0','project_id':a.project_id,'updated_at':now,'evidence':[]})
for name in ['implementation-ledger.jsonl','recovery-events.jsonl']: (rt/name).touch(exist_ok=True)
print(f'INITIALIZED governed={governed} runtime={rt}')
