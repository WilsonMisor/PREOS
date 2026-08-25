#!/usr/bin/env python3
from preos_common import load_source_json
import argparse,json
ap=argparse.ArgumentParser(); ap.add_argument('--output'); a=ap.parse_args(); controls=load_source_json('baseline_75_controls.json')['controls']
out=[]
for c in controls: out.append({'control_no':c['no'],'applicability':'UNKNOWN','not_applicable_reason':None,'result':'UNKNOWN','evidence_ids':[],'dependencies':[],'owner':None,'rule':c['applicability_rule']})
text=json.dumps({'controls':out},indent=2)
if a.output: open(a.output,'w',encoding='utf-8').write(text+'\n')
else: print(text)
