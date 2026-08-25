#!/usr/bin/env python3
from preos_common import load_json
import argparse,json
ap=argparse.ArgumentParser(); ap.add_argument('old_contract'); ap.add_argument('new_contract'); ap.add_argument('--output')
a=ap.parse_args(); old=load_json(a.old_contract); new=load_json(a.new_contract)
def hashes(c): return {x['artifact']:x['sha256'] for x in c.get('source_hashes',[])}
a1,a2=hashes(old),hashes(new); changed=sorted({*a1,*a2}-{k for k in a1 if k in a2 and a1[k]==a2[k]})
out={'project_id':new.get('project_id'),'changed_sources':changed,'requires_risk_delta':bool(changed),'requires_evidence_freshness_review':bool(changed),'requires_control_reassessment':bool(changed),'requires_gate_reassessment':bool(changed),'rule':'do not patch downstream artifacts while upstream approved truth changed without impact analysis'}
text=json.dumps(out,indent=2)
if a.output: open(a.output,'w',encoding='utf-8').write(text+'\n')
else: print(text)
