#!/usr/bin/env python3
from preos_common import preos_root
import re,sys,zipfile
root=preos_root()
with zipfile.ZipFile(root/'source-package'/'original-package.zip') as zf:
    text=zf.read('master_production_readiness_questions.md').decode('utf-8')
count=len(re.findall(r'^\d+\.\s+',text,re.M))
if count!=1300:
    print(f'FAIL readiness: expected 1300 numbered questions, found {count}'); sys.exit(1)
print('PASS readiness: 1300 production-readiness questions present in authoritative source package')
