#!/usr/bin/env python3
from preos_common import load_json
import argparse,json,sys,datetime
ORDER={'GREEN':0,'AMBER':1,'UNKNOWN':2,'HUMAN REVIEW':3,'RED':4}
ap=argparse.ArgumentParser(); ap.add_argument('gate_inputs'); ap.add_argument('--output')
a=ap.parse_args(); d=load_json(a.gate_inputs); result={}
for gid,items in d.get('gates',{}).items():
    states=[i.get('state','UNKNOWN') for i in items]
    state=max(states,key=lambda s:ORDER.get(s,2)) if states else 'UNKNOWN'
    if state=='GREEN' and any(not i.get('evidence_ids') for i in items): state='UNKNOWN'
    result[gid]={'state':state,'evaluated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':items}
text=json.dumps({'gate_results':result},indent=2)
if a.output: open(a.output,'w',encoding='utf-8').write(text+'\n')
else: print(text)
if any(v['state']=='RED' for v in result.values()): sys.exit(2)
