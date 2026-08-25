#!/usr/bin/env python3
from preos_common import preos_root
import argparse, zipfile, re
ap=argparse.ArgumentParser(); ap.add_argument('--keyword',action='append',default=[]); ap.add_argument('--domain',action='append',default=[]); ap.add_argument('--limit',type=int,default=100); a=ap.parse_args()
with zipfile.ZipFile(preos_root()/'source-package/original-package.zip') as zp:
 text=zp.read('master_production_readiness_questions.md').decode('utf-8')
terms=[x.lower() for x in a.keyword+a.domain]
blocks=re.split(r'(?=^###? )',text,flags=re.M)
selected=[]
for b in blocks:
 if not terms or any(t in b.lower() for t in terms):
  for line in b.splitlines():
   if re.match(r'^\s*(?:[-*]|\d+[.)])\s+',line):
    selected.append(line.strip())
    if len(selected)>=a.limit: break
 if len(selected)>=a.limit: break
for q in selected: print(q)
