#!/usr/bin/env python3
from preos_common import load_json,PROTECTED_AUTHORITY_WORDS
import argparse,sys,re
ap=argparse.ArgumentParser(); ap.add_argument('project_contract')
a=ap.parse_args(); c=load_json(a.project_contract); errs=[]
for key,val in c.get('authority',{}).items():
    text=str(val).upper()
    if any(re.search(rf'\\b{re.escape(w)}\\b',text) for w in PROTECTED_AUTHORITY_WORDS): errs.append(f'{key}: AI/tool cannot be consequential authority ({val})')
    if not val or str(val).strip().upper() in {'ROLE GAP','UNKNOWN'}: errs.append(f'{key}: unresolved authority {val!r}')
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print('PASS authority: protected decision authorities are named humans/roles, not AI/tool personas')
