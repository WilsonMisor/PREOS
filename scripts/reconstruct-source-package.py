#!/usr/bin/env python3
from preos_common import source_package_bytes, preos_root
import argparse
ap=argparse.ArgumentParser(description='Reconstruct the exact PREOS source ZIP from checksum-verified repository chunks.')
ap.add_argument('--output',default='production_risk_economics_evolution_operating_system_package.zip')
a=ap.parse_args()
out=preos_root()/a.output if not a.output.startswith('/') else __import__('pathlib').Path(a.output)
out.write_bytes(source_package_bytes())
print(out)
