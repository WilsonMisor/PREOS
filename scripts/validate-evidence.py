#!/usr/bin/env python3
from preos_common import load_json
import argparse,datetime,sys,re
ap=argparse.ArgumentParser(); ap.add_argument('evidence',nargs='+')
a=ap.parse_args(); errs=[]; now=datetime.datetime.now(datetime.timezone.utc)
for path in a.evidence:
    e=load_json(path)
    for k in ['evidence_id','produced_at','producer','environment','artifact_location','validity','bindings']:
        if k not in e or e[k] in ('',None): errs.append(f'{path}: missing {k}')
    if e.get('validity')=='GREEN': errs.append(f'{path}: evidence validity uses CURRENT/STALE/EXPIRED/UNKNOWN, not GREEN')
    sha=e.get('commit_sha')
    if sha and not re.fullmatch(r'[0-9a-fA-F]{7,64}',sha): errs.append(f'{path}: invalid commit_sha')
    until=e.get('valid_until')
    if until:
        try:
            dt=datetime.datetime.fromisoformat(until.replace('Z','+00:00'))
            if dt < now and e.get('validity')=='CURRENT': errs.append(f'{path}: expired evidence cannot remain CURRENT')
        except ValueError: errs.append(f'{path}: invalid valid_until')
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print(f'PASS evidence: {len(a.evidence)} record(s) structurally valid')
