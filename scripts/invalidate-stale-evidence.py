#!/usr/bin/env python3
from preos_common import load_json,dump_json
from pathlib import Path
import argparse,datetime
ap=argparse.ArgumentParser(); ap.add_argument('evidence'); ap.add_argument('--current-bindings',required=True); ap.add_argument('--output')
a=ap.parse_args(); e=load_json(a.evidence); current=load_json(a.current_bindings); old=e.get('bindings',{}); reasons=[]
for k,v in old.items():
    if k in current and current[k]!=v: reasons.append(f'{k} changed')
until=e.get('valid_until')
if until:
    try:
        if datetime.datetime.fromisoformat(until.replace('Z','+00:00')) < datetime.datetime.now(datetime.timezone.utc): reasons.append('validity period expired')
    except ValueError: reasons.append('invalid validity period')
if reasons: e['validity']='STALE'; e['stale_reasons']=reasons
out=a.output or a.evidence; dump_json(out,e); print(('STALE: '+', '.join(reasons)) if reasons else 'UNCHANGED')
