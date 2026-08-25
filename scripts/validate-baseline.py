#!/usr/bin/env python3
from preos_common import preos_root,load_json,load_source_json
import sys
root=preos_root(); pointer=load_json(root/'references/baseline/baseline-75-controls.json'); d=load_source_json('baseline_75_controls.json'); controls=d.get('controls',[]); errs=[]
if pointer.get('canonical_source')!='source-package/original-package.zip::baseline_75_controls.json': errs.append('baseline pointer must bind to the preserved source-package JSON')
if pointer.get('count')!=75: errs.append('baseline pointer count must be 75')
if d.get('count')!=75 or len(controls)!=75: errs.append('expected exactly 75 controls')
nums=[c.get('no') for c in controls]
if nums!=list(range(1,76)): errs.append('control numbers must be exactly 1..75 in order')
for c in controls:
    for k in ['gate_and_acceptance_condition','applicability_rule','required_test','evidence_before_acceptance','source']:
        if not c.get(k): errs.append(f"control {c.get('no')} missing {k}")
if errs:
    print('\n'.join('FAIL '+e for e in errs)); sys.exit(1)
print('PASS baseline: 75 canonical controls, numbered 1..75, loaded from authoritative source package')
