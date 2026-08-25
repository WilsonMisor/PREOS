#!/usr/bin/env python3
from preos_common import runtime_root,load_json
import argparse,json
ap=argparse.ArgumentParser(); ap.add_argument('project_id')
a=ap.parse_args(); root=runtime_root()/'projects'/a.project_id/'production'; cps=root/'checkpoints'; valid=[]
if cps.exists():
    for p in cps.glob('*.json'):
        try: valid.append((p.stat().st_mtime,p,load_json(p)))
        except Exception: pass
if valid:
    _,p,d=max(valid,key=lambda x:x[0]); print(json.dumps({'source':str(p),'state':d},indent=2))
elif (root/'CURRENT-STATE.json').exists(): print(json.dumps({'source':str(root/'CURRENT-STATE.json'),'state':load_json(root/'CURRENT-STATE.json')},indent=2))
else: raise SystemExit('No recoverable PREOS state found; do not invent state from conversation memory.')
