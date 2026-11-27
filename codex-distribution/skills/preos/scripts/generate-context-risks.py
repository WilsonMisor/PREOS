#!/usr/bin/env python3
"""Deterministically select risk domains from Project Contract triggers.
This script does not pretend to replace contextual engineering judgement; it creates a bounded candidate set for AI/human review.
"""
from preos_common import load_json, iter_risks
from pathlib import Path
import argparse,json
MAP={
 'multi_tenant':['Authorization and Tenant Isolation','Authentication','Economic Abuse Surface'],
 'payments':['Money and Financial Correctness','Billing and Subscription','Trade Assurance and Protected Transactions','Economic Abuse Surface'],
 'mobile':['Mobile Engineering','Compatibility and Version Evolution','Time and Temporal Correctness'],
 'personal_data':['Privacy and Data Lifecycle','Security','Legal, Contractual, and Evidence Exposure'],
 'ai':['AI Specific Risks','Decision Automation Risk','AI Coding Agent Authority Boundary'],
 'vendors':['Vendor Viability and Concentration Risk','Software Supply Chain and Build Provenance','Cloud and Compute'],
 'production':['Observability','Reliability and Availability','Backup, Recovery, and Disaster Recovery','CI, CD, and Version Control','Support and Operations','Evidence Freshness and Validity','Risk Aggregation and Release Risk']}
ap=argparse.ArgumentParser(); ap.add_argument('project_contract'); ap.add_argument('--output')
a=ap.parse_args(); c=load_json(a.project_contract); flags=c.get('classification',{}); active=set()
for flag,ds in MAP.items():
    v=flags.get(flag)
    if v is True or (isinstance(v,str) and v.lower() not in ('','false','none','not_applicable')): active.update(ds)
for p in flags.get('profiles',[]):
    if p=='mobile': active.update(MAP['mobile'])
active.update(MAP['production'])
selected=[r for r in iter_risks() if r.get('domain') in active]
out={'project_id':c.get('project_id'),'selected_domains':sorted(active),'selected_risk_count':len(selected),'risk_ids':[r['check_id'] for r in selected], 'rule':'candidate set only; unresolved material context remains UNKNOWN until reviewed'}
text=json.dumps(out,indent=2)
if a.output: Path(a.output).write_text(text+'\n',encoding='utf-8')
else: print(text)
