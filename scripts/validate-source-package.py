#!/usr/bin/env python3
from preos_common import preos_root,load_json,sha256_file,source_package_bytes,open_source_zip
import sys,hashlib
root=preos_root(); man=load_json(root/'source-package/SOURCE-MANIFEST.json'); errs=[]
try:
    raw=source_package_bytes(root)
except Exception as e:
    print('FAIL '+str(e)); sys.exit(1)
if len(raw)!=man['original_zip']['bytes']: errs.append('reconstructed source package byte count mismatch')
if hashlib.sha256(raw).hexdigest()!=man['original_zip']['sha256']: errs.append('reconstructed source package hash mismatch')
source_by_name={f['name']:f for f in man['files']}
with open_source_zip(root) as zp:
    names=set(zp.namelist())
    for f in man['files']:
        name=f['name']
        if name not in names: errs.append(f'ZIP missing {name}'); continue
        data=zp.read(name)
        if hashlib.sha256(data).hexdigest()!=f['sha256']: errs.append(f'ZIP file hash mismatch {name}')
    for source_name, rel in man.get('active_canonical_mapping',{}).items():
        p=root/rel
        if source_name not in source_by_name: errs.append(f'canonical mapping uses unknown source {source_name}'); continue
        if not p.is_file(): errs.append(f'canonical source missing {rel}'); continue
        if sha256_file(p)!=source_by_name[source_name]['sha256']: errs.append(f'canonical source hash mismatch {rel}')
    for source_name, rel in man.get('source_package_access_mapping',{}).items():
        p=root/rel
        if source_name not in source_by_name: errs.append(f'source access mapping uses unknown source {source_name}'); continue
        if not p.is_file(): errs.append(f'source access pointer missing {rel}'); continue
        text=p.read_text(encoding='utf-8')
        if source_name not in text or 'package-chunks' not in text: errs.append(f'source access pointer does not bind {source_name} to reconstructed source package: {rel}')
for k,v in man['expected_counts'].items():
    if man['observed_counts'].get(k)!=v: errs.append(f'count mismatch {k}')
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print('PASS source package: chunks reconstruct exact ZIP; members, canonical mappings, hashes and source counts match provenance manifest')
