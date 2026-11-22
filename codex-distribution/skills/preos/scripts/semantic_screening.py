"""Reproducible corpus screening; heuristics report evidence, never approval."""
from collections import defaultdict
import hashlib
import re

FIELDS=('Root cause','Failure mechanism','Prevention strategy','Automated test')

def normalized(text): return re.sub(r'\s+',' ',str(text).strip().casefold())

def screen_corpus(records):
    groups={field:defaultdict(list) for field in FIELDS}
    for record in records:
        for field in FIELDS: groups[field][normalized(record['fields'].get(field,''))].append(record)
    results={}
    for record in records:
        checks=[]; fields=record['fields']; name=normalized(record['canonical_name']); category=normalized(record['category'])
        for field in FIELDS:
            value=normalized(fields.get(field,'')); peers=groups[field][value]
            categories={r['category'] for r in peers}; names={r['canonical_name'] for r in peers}
            repeated=len(categories)>1 and len(names)>1
            checks.append({'rule_id':'SEM-TEMPLATE-'+field.upper().replace(' ','-'),'state':'REVIEW' if repeated or not value else 'NO_PATTERN_DETECTED','field':field,'text_sha256':hashlib.sha256(value.encode()).hexdigest(),'shared_records':len(peers),'distinct_categories':len(categories),'distinct_names':len(names),'reason':'Identical text across distinct names/categories requires context-specific interpretation.' if repeated else 'No cross-category exact-text reuse detected; this is not semantic approval.'})
        mechanism=normalized(' '.join(fields.get(f,'') for f in ('Root cause','Failure mechanism','Conditions required to trigger the problem')))
        patterns=[
            ('SEM-SERIALIZATION-CONCURRENCY','serialization' in name and any(t in mechanism for t in ('shared state','lost update','competing writes','concurrent')),'Serialization name with shared-state concurrency mechanism'),
            ('SEM-DRUG-SAFETY-CONTROL','drug serialization' in name and any(t in mechanism for t in ('sensor','interlock','control loop','control command')),'Drug serialization name with physical control mechanism'),
            ('SEM-PERFORMANCE-AUTHORIZATION',any(t in name for t in ('latency','throughput','performance')) and 'authorization' in mechanism,'Performance title with authorization mechanism; review causal relationship'),
            ('SEM-DATABASE-CACHE','database' in name and 'cache' in mechanism,'Database title with cache mechanism; review causal relationship'),
        ]
        for rule,flag,reason in patterns:
            checks.append({'rule_id':rule,'state':'REVIEW' if flag else 'NO_PATTERN_DETECTED','field':'name/mechanism','reason':reason,'matched':flag})
        checks.append({'rule_id':'SEM-OWNER-TEST-SUITABILITY','state':'HUMAN_REVIEW','reason':'Presence is checkable; professional ownership and test sufficiency need domain interpretation.','owner_present':bool(fields.get('Owner')),'test_present':bool(fields.get('Automated test'))})
        results[record['risk_id']]=checks
    return results
