#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,json,hashlib,re
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
anchors=['UNKNOWN never silently becomes GREEN','75','1,130','1,300','PREOS_STATE_ROOT','.ai-product-delivery/preos','gstack-plan-eng-review','AI Task Packet','G0','G11','Conversation memory is never authoritative execution state','RECOVERY_CONFLICT','first unverified action','wordpress-75-control-overlay.md']
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
overlay=(ROOT/'references/wordpress/wordpress-75-control-overlay.md').read_text(encoding='utf-8')
ids=re.findall(r'\| (FS-\d{3}) \|',overlay)
expected=[f'FS-{n:03d}' for n in range(1,76)]
if ids!=expected or len(set(ids))!=75: raise SystemExit('WordPress overlay must map FS-001..FS-075 exactly once and in order')
continuity=(ROOT/'docs/session-continuity.md').read_text(encoding='utf-8')
for a in ['SAFE_TO_RESUME','BLOCKED','RECOVERY_CONFLICT','first unverified','gstack context-save/context-restore']:
    if a not in continuity: raise SystemExit(f'session-continuity documentation missing anchor: {a}')
print(f'PASS PREOS manifest: {len(required)} required paths exist; canonical source hash matches')
print('PASS PREOS semantic completeness: 38 integration recommendations and 52 source domains covered')
print('PASS PREOS AI-session continuity/recovery anchors and WordPress 75/75 interpretation present')
print('PASS PREOS repository metadata and integration contracts present')
print('PASS PREOS validation complete')
