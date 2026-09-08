#!/usr/bin/env python3
from preos_common import preos_root
import sys
root=preos_root(); errs=[]
files={
 'README.md':['AI Product Delivery Blueprint','WilsonMisor/wed_dev_skill','WilsonMisor/gstack','Codex','75','1,130','1,300'],
 'INTEGRATION-CONTRACT.md':['Human authority','AI Product Delivery Blueprint','PREOS','gstack','Codex','Application repository','Do not copy'],
 'ARCHITECTURE.md':['PREOS learning','Blueprint change control','PREOS_STATE_ROOT','.ai-product-delivery'],
 'AGENTS.md':['Project Contract','AI Task Packets','.ai-product-delivery/preos','PREOS_STATE_ROOT','1,300','1,130'],
 'references/integration/blueprint-integration.md':['preos-project-init','preos-risk-model','preos-architecture-economics','preos-production-plan','preos-production-implement','preos-production-learn'],
 'references/integration/gstack-integration.md':['gstack-office-hours','gstack-plan-ceo-review','gstack-plan-eng-review','gstack-cso','gstack-review','gstack-qa','gstack-benchmark','gstack-ship','gstack-retro'],
}
for rel,tokens in files.items():
    p=root/rel
    if not p.is_file(): errs.append(f'missing {rel}'); continue
    text=p.read_text(encoding='utf-8')
    for token in tokens:
        if token not in text: errs.append(f'{rel} missing semantic anchor: {token}')
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print('PASS integration: Blueprint, PREOS, gstack, Codex, application and human authority contracts are explicit')
