#!/usr/bin/env python3
"""Reproducible measured workload; fail on any budget or behavioral regression."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import time
import tracemalloc
import zlib

from assurance_engines import RiskCatalogue, normalize_project_context, risk_generation_engine
from canonical_sources import SOURCES, source_bytes
from risk_graph import RiskGraph

ROOT=Path(__file__).resolve().parents[1]
BUDGET_PATH=ROOT/'references/integration/performance-budgets.json'


def enforce_budgets(metrics,budgets):
    failures=[]
    for field,maximum in budgets.items():
        value=metrics.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=maximum:
            failures.append(f'{field}: observed {value!r}, maximum {maximum}')
    if failures:
        raise ValueError('performance regression: '+'; '.join(failures))


def workload_contract():
    return {'product_type':'SaaS','profiles':['saas','web','api','data','infrastructure'],
            'tenant_model':'multi-tenant','payments':True,'personal_data':True,
            'architecture':['REST','relational database','queue','external payment provider','web UI'],
            'external_providers':['payment provider'],'jurisdictions':['Nigeria'],
            'features':['withdrawal'],'actors':['tenant user','admin','payment provider'],
            'money_movement':True,'maturity_stage':'Stage 1 Early Production','threat_stage':'Stage 2'}


def run_benchmark(*,budgets_path=BUDGET_PATH):
    budget_raw=Path(budgets_path).read_bytes()
    config=json.loads(budget_raw)
    budgets=config['maximums']
    measurements={}
    contract=workload_contract()
    def measure(name,function):
        start=time.perf_counter()
        result=function()
        measurements[name]=round((time.perf_counter()-start)*1000,3)
        return result
    tracemalloc.start()
    try:
        query=measure('catalogue_query_ms',lambda:RiskGraph().query('architectures',limit=25))
        catalogue=RiskCatalogue()
        selected=measure('selection_time_ms',lambda:risk_generation_engine(contract,limit=50,catalogue=catalogue))
        context=measure('context_generation_ms',lambda:normalize_project_context(contract))
        def serialize():
            raw=json.dumps({'context':context,'selection':selected},sort_keys=True,separators=(',',':')).encode()
            compressed=zlib.compress(raw)
            if zlib.decompress(compressed)!=raw:
                raise ValueError('serialized context round trip failed')
            return raw,compressed
        raw,compressed=measure('compression_serialization_ms',serialize)
        def validate_sources():
            for sid,(_,expected) in SOURCES.items():
                if hashlib.sha256(source_bytes(sid)).hexdigest()!=expected:
                    raise ValueError('source validation failed')
        measure('validation_time_ms',validate_sources)
        measurements['memory_peak_bytes']=tracemalloc.get_traced_memory()[1]
        measurements['generated_context_size_bytes']=len(raw)
        measurements['compressed_context_size_bytes']=len(compressed)
    finally:
        tracemalloc.stop()
    if not query['results'] or not selected['selected_context_variants']:
        raise ValueError('benchmark workload did not exercise catalogue selection')
    command=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_assurance_engines.py']
    if not (ROOT/'tests/test_assurance_engines.py').is_file():
        raise ValueError('representative CI benchmark requires a source checkout containing committed tests')
    start=time.perf_counter()
    proc=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=budgets['ci_validation_duration_seconds'])
    measurements['ci_validation_duration_seconds']=round(time.perf_counter()-start,3)
    count=re.search(r'Ran (\d+) tests?',proc.stderr)
    if proc.returncode or not count or int(count[1])==0 or 'skipped=' in proc.stderr:
        raise ValueError('representative CI validation failed or did not execute: '+proc.stderr)
    enforce_budgets(measurements,budgets)
    return {'schema_version':'pasv2-measured-benchmark-v1',**measurements,'budgets':budgets,
            'budget_sha256':hashlib.sha256(budget_raw).hexdigest(),
            'environment':{'python':platform.python_version(),'platform':platform.platform(),
                'processor':platform.processor(),'instrumentation':'tracemalloc peak Python allocations; wall-clock timing','cache':'new graph and catalogue instances; operating-system filesystem cache uncontrolled'},
            'workload':{'selected_variants':len(selected['selected_context_variants']),'query_matches':query['total_matches'],'catalogue_io':catalogue.stats},
            'ci_execution':{'command':command,'returncode':proc.returncode,'tests_executed':int(count[1]),'stdout':proc.stdout,'stderr':proc.stderr}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run_benchmark()
    rendered=json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered,encoding='utf-8',newline='\n')
    print(rendered,end='')


if __name__=='__main__': main()
