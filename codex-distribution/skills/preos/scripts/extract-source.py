#!/usr/bin/env python3
from preos_common import open_source_zip
import argparse,sys
ap=argparse.ArgumentParser(description='Extract or print an exact member of the checksum-verified PREOS source package.')
ap.add_argument('name'); ap.add_argument('--output')
a=ap.parse_args()
with open_source_zip() as zf:
    if a.name not in zf.namelist():
        print(f'unknown source member: {a.name}',file=sys.stderr); sys.exit(2)
    data=zf.read(a.name)
if a.output:
    from pathlib import Path
    p=Path(a.output); p.write_bytes(data); print(p)
else:
    try: sys.stdout.write(data.decode('utf-8'))
    except UnicodeDecodeError:
        print('binary source member requires --output',file=sys.stderr); sys.exit(2)
