#!/usr/bin/env python3
from preos_common import open_source_zip
import re,sys
with open_source_zip() as zf:
    text=zf.read('master_production_readiness_questions.md').decode('utf-8')
count=len(re.findall(r'^\d+\.\s+',text,re.M))
if count!=1300:
    print(f'FAIL readiness: expected 1300 numbered questions, found {count}'); sys.exit(1)
print('PASS readiness: 1300 production-readiness questions present in checksum-verified authoritative source package')
