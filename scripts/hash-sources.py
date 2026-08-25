#!/usr/bin/env python3
from preos_common import sha256_file
from pathlib import Path
import argparse, json, datetime
ap=argparse.ArgumentParser(); ap.add_argument('files',nargs='+'); ap.add_argument('--output')
a=ap.parse_args(); rows=[]
for item in a.files:
    p=Path(item).resolve(); rows.append({'artifact':str(p),'sha256':sha256_file(p),'bytes':p.stat().st_size})
out={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_hashes':rows}
text=json.dumps(out,indent=2)
if a.output: Path(a.output).write_text(text+'\n',encoding='utf-8')
else: print(text)
