#!/usr/bin/env python3
from preos_common import iter_risks
import argparse, json, re
ap=argparse.ArgumentParser(); ap.add_argument('--domain',action='append',default=[]); ap.add_argument('--keyword',action='append',default=[]); ap.add_argument('--ids',nargs='*',default=[]); ap.add_argument('--limit',type=int,default=250)
a=ap.parse_args(); domains={x.lower() for x in a.domain}; ids=set(a.ids); kws=[k.lower() for k in a.keyword]
out=[]
for r in iter_risks():
    text=' '.join(str(r.get(k,'')) for k in ['domain','feature','actor','failure_scenario','trigger','root_mechanism','business_invariant','expected_correct_behaviour']).lower()
    match=(not domains and not ids and not kws) or r.get('domain','').lower() in domains or r.get('check_id') in ids or any(k in text for k in kws)
    if match: out.append(r)
    if len(out)>=a.limit: break
for r in out: print(json.dumps(r,ensure_ascii=False))
