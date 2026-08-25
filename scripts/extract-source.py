#!/usr/bin/env python3
from preos_common import preos_root
from pathlib import Path
import argparse, sys, zipfile

ap=argparse.ArgumentParser(description='Extract one exact member from the preserved PREOS source package.')
ap.add_argument('member', help='Exact ZIP member name, for example baseline_75_controls.json')
ap.add_argument('--output')
a=ap.parse_args()
zip_path=preos_root()/'source-package'/'original-package.zip'
with zipfile.ZipFile(zip_path) as zf:
    if a.member not in zf.namelist():
        raise SystemExit(f'unknown source member: {a.member}')
    data=zf.read(a.member)
if a.output:
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
else:
    sys.stdout.buffer.write(data)
