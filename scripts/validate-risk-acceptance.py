#!/usr/bin/env python3
from preos_common import load_json,PROTECTED_AUTHORITY_WORDS
import argparse,datetime,sys,re
ap=argparse.ArgumentParser(); ap.add_argument('acceptance',nargs='+')
a=ap.parse_args(); errs=[]; now=datetime.datetime.now(datetime.timezone.utc)
for p in a.acceptance:
    r=load_json(p)
    for k in ['acceptance_id','risk_ids','authority','reason','scope','approved_at','expires_at','review_trigger']:
        if not r.get(k): errs.append(f'{p}: missing {k}')
    auth=str(r.get('authority','')).upper()
    if any(re.search(rf'\b{re.escape(w)}\b',auth) for w in PROTECTED_AUTHORITY_WORDS): errs.append(f'{p}: AI/tool cannot accept risk')
    try:
        exp=datetime.datetime.fromisoformat(str(r.get('expires_at')).replace('Z','+00:00'))
        if exp<=now: errs.append(f'{p}: risk acceptance expired')
    except Exception: errs.append(f'{p}: invalid expires_at')
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print(f'PASS risk acceptance: {len(a.acceptance)} record(s) have bounded human authority')
