#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,json,hashlib
from preos_common import source_package_bytes
ROOT=Path(__file__).resolve().parents[1]
checks=['validate-source-package.py','validate-baseline.py','validate-risk-catalogue.py','validate-readiness.py','validate-integration.py']
for script in checks:
    r=subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT)
    if r.returncode: raise SystemExit(r.returncode)
manifest=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))
required=manifest['required_paths']
miss=[p for p in required if not (ROOT/p).exists()]
if miss: raise SystemExit('Missing PREOS files from MANIFEST.json:\n'+'\n'.join(miss))
if len(required)!=len(set(required)): raise SystemExit('MANIFEST.json contains duplicate required paths')
canonical=source_package_bytes(ROOT)
if len(canonical)!=manifest['canonical_source']['bytes']: raise SystemExit('canonical reconstructed source ZIP byte count mismatch')
if hashlib.sha256(canonical).hexdigest()!=manifest['canonical_source']['sha256']: raise SystemExit('canonical reconstructed source ZIP hash mismatch')
text=(ROOT/'SKILL.md').read_text(encoding='utf-8')
anchors=['UNKNOWN never silently becomes GREEN','75','1,130','1,300','PREOS_STATE_ROOT','.ai-product-delivery/preos','gstack-plan-eng-review','AI Task Packet','G0','G11']
for a in anchors:
    if a not in text: raise SystemExit(f'SKILL.md missing semantic anchor: {a}')
rec=(ROOT/'RECOMMENDATION-COVERAGE.md').read_text(encoding='utf-8')
for n in range(1,39):
    if f'| I{n:02d} |' not in rec: raise SystemExit(f'missing integration recommendation I{n:02d}')
source=(ROOT/'SOURCE-CONCEPT-COVERAGE.md').read_text(encoding='utf-8')
for n in range(1,53):
    if f'| D{n:02d} |' not in source: raise SystemExit(f'missing source domain D{n:02d}')
metadata=['VERSION','CHANGELOG.md','LICENSE-NOTES.md','SECURITY.md','CONTRIBUTING.md','INTEGRATION-CONTRACT.md','.gitignore','.github/workflows/validate-preos.yml','.github/CODEOWNERS']
for p in metadata:
    if not (ROOT/p).exists(): raise SystemExit(f'missing repository metadata: {p}')
print(f'PASS PREOS manifest: {len(required)} required paths exist; canonical source hash matches')
print('PASS PREOS semantic completeness: 38 integration recommendations and 52 source domains covered')
print('PASS PREOS repository metadata and integration contracts present')
print('PASS PREOS validation complete')
