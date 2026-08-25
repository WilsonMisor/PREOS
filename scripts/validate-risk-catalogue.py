#!/usr/bin/env python3
from preos_common import preos_root, load_json, iter_risks
import sys
root=preos_root(); schema=load_json(root/'references/risks/atomic-risk-record.schema.json'); required=schema.get('required',[])
ids=set(); domains=set(); count=0; errs=[]
for r in iter_risks():
    count+=1; rid=r.get('check_id'); domain=r.get('domain'); domains.add(domain)
    if not rid: errs.append(f'record {count} missing check_id')
    elif rid in ids: errs.append(f'duplicate {rid}')
    ids.add(rid)
    miss=[k for k in required if k not in r]
    if miss: errs.append(f'{rid} missing {miss}')
if count!=1130: errs.append(f'expected 1130 risks, found {count}')
if len(ids)!=1130: errs.append(f'expected 1130 unique risk ids, found {len(ids)}')
if len(domains)!=52: errs.append(f'expected 52 domains, found {len(domains)}')
if errs:
    print('\n'.join('FAIL '+e for e in errs[:100])); sys.exit(1)
print(f'PASS risks: {count} unique records across {len(domains)} domains; required schema fields present')
