#!/usr/bin/env python3
"""Context, bounded adversity, economics and evolution over canonical PREOS data."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from itertools import combinations, product
import json
from pathlib import Path
import re

from candidate_workflow import candidate_id, submit

ROOT = Path(__file__).resolve().parents[1]
MODEL2 = ROOT/'references/risks/model2'
CROSSWALK = ROOT/'references/integration/source4-production-assurance-crosswalk.json'
RISK_GENERATION_AXES = ['feature','actor','input','state','time','concurrency','retry','network','dependency','storage','permission','attack','scale','cost','human_action','business_rule','legal_consequence','recovery']


def source4():
    return json.loads(CROSSWALK.read_text(encoding='utf-8'))


def key(text):
    return re.sub(r'[^a-z0-9]+','_',text.casefold()).strip('_')


def sequence(value):
    if value is None or value == 'UNKNOWN':
        return []
    return value if isinstance(value,list) else [value]


ALIASES = {'product_category':['product_type'],'user_types':['actors','users'],'money_movement':['payments'],'sensitive_data':['personal_data'],'external_providers':['vendors'],'current_production_stage':['maturity_stage'],'billing_requirements':['billing'],'subscription_requirements':['subscriptions'],'critical_workflows':['features'],'data_and_analytics_requirements':['analytics'],'real_time_requirements':['realtime'],'organisation_types':['organization_types']}


def normalize_project_context(contract):
    merged = dict(contract.get('classification', {}))
    for field, value in contract.items():
        if field != 'classification':
            if field in merged and merged[field] != value:
                raise ValueError(f'Project Contract/classification conflict: {field}')
            merged[field] = value
    dimensions = {}
    for item in source4()['context_dimensions']:
        name = key(item['text'])
        candidates = [field for field in [name,*ALIASES.get(name,[])] if field in merged]
        values = [merged[field] for field in candidates]
        if values and any(v != values[0] for v in values):
            raise ValueError(f'context aliases conflict: {name}')
        value = values[0] if values else None
        known = value is not None and value != 'UNKNOWN'
        assumption = next((a for a in merged.get('assumptions',[]) if a.get('dimension')==name),None)
        if not known and assumption:
            if not all(assumption.get(k) for k in ('owner','validation_trigger','provenance')):
                raise ValueError(f'assumption lacks owner/validation trigger/provenance: {name}')
            value = assumption.get('value')
        dimensions[name] = {'value':value,'state':'KNOWN' if known else ('ASSUMPTION' if assumption else 'UNKNOWN'),'source_field':candidates[0] if candidates else None,'source_line':item['line'],'owner':assumption.get('owner') if assumption else merged.get('context_owner','ROLE GAP'),'validation_trigger':assumption.get('validation_trigger') if assumption else 'Project Contract refresh','assumption_provenance':assumption.get('provenance') if assumption else None}
    output = {name:entry['value'] for name,entry in dimensions.items()}
    for flag in ('money_movement','sensitive_data'):
        value = output[flag]
        if value is not None and not isinstance(value, bool):
            raise ValueError(f'{flag} must be true, false, or unknown')
    output.update(profiles=sorted(set(sequence(merged.get('profiles')))),architecture=sequence(merged.get('architecture')),features=sequence(merged.get('features',output['critical_workflows'])),tenant_model=merged.get('tenant_model','UNKNOWN'),threat_stage=merged.get('threat_stage','UNKNOWN'),maturity_stage=merged.get('maturity_stage','UNKNOWN'),documentation_only=merged.get('documentation_only') is True,dimensions=dimensions)
    output['jurisdictions'] = sequence(output['jurisdictions'])
    output['external_providers'] = sequence(output['external_providers'])
    output['user_types'] = sequence(output['user_types'])
    output['required_source4_dimensions'] = list(dimensions)
    output['covered_source4_dimensions'] = [k for k,v in dimensions.items() if v['state']=='KNOWN']
    output['missing_source4_dimensions'] = [k for k,v in dimensions.items() if v['state']=='UNKNOWN']
    return output


def context_engine(contract):
    return {'engine':'Context Engine','output':normalize_project_context(contract)}


class RiskCatalogue:
    def __init__(self, root=MODEL2):
        self.root=Path(root)
        self.stats={'files_opened':0,'records_read':0,'queries':0}
        self._rows=None

    def records(self):
        if self._rows is None:
            self._rows=[]
            self.stats['files_opened']+=1
            for line in (self.root/'risk-context-variants.jsonl').read_text(encoding='utf-8').splitlines():
                if line.strip():
                    self._rows.append(json.loads(line))
            self.stats['records_read']+=len(self._rows)
        return self._rows

    def select(self, context, limit=25):
        if not 1 <= limit <= 500:
            raise ValueError('selection limit must be 1..500')
        self.stats['queries']+=1
        if context.get('documentation_only'):
            return []
        rows=self.records()
        facets=[('universal',lambda r:r['dimension']=='universal')]
        if context.get('money_movement') is True:
            facets.append(('money',lambda r:r['dimension']=='industry' and re.search(r'banking|payments|finance',r['category'],re.I)))
        product_type=str(context.get('product_category') or '').casefold()
        if product_type:
            facets.append(('product',lambda r:r['dimension']=='product' and product_type in r['category'].casefold()))
        for jurisdiction in context.get('jurisdictions',[]):
            facets.append(('jurisdiction:'+jurisdiction,lambda r,j=jurisdiction:r['dimension']=='jurisdiction' and j.casefold()==r['category'].casefold()))
        for architecture in context.get('architecture',[]):
            tokens=set(re.findall(r'\w+',architecture.casefold()))-{'architecture','provider','external','ui'}
            if tokens:
                facets.append(('architecture:'+architecture,lambda r,t=tokens:r['dimension'] in {'architecture','universal'} and all(any(word.startswith(token) for word in re.findall(r'\w+',r['category'].casefold())) for token in t)))
        # Round-robin prevents one broad category from starving a jurisdiction
        # or a relevant architecture. Each selected row retains its match basis.
        matches=[(facet,sorted([r for r in rows if predicate(r)],key=lambda r:r['source_risk_id'])) for facet,predicate in facets]
        selected={}
        cursor=0
        while len(selected)<limit:
            added=False
            for facet,items in matches:
                if cursor<len(items):
                    row=items[cursor]
                    rid=row['risk_context_variant_id']
                    if rid not in selected and len(selected)<limit:
                        selected[rid]={**row,'matched_facets':[],'authority':'CONTEXT_ONLY_PENDING_MODEL2_APPROVAL'}
                        added=True
                    if rid in selected and facet not in selected[rid]['matched_facets']:
                        selected[rid]['matched_facets'].append(facet)
            if not added and all(cursor>=len(items) for _,items in matches):
                break
            cursor+=1
        return list(selected.values())


WITHDRAWAL_ADVERSITY = [
    ('duplicate clicks',{'input':'duplicate submission','concurrency':'same action repeated'}),
    ('simultaneous devices',{'actor':'same user on two devices','concurrency':'parallel withdrawal'}),
    ('stale balances',{'state':'stale balance','storage':'replica lag'}),
    ('provider timeouts',{'dependency':'payment provider','network':'response lost'}),
    ('duplicate provider events',{'input':'duplicate callback','retry':'provider redelivery'}),
    ('missing provider events',{'input':'missing callback','time':'confirmation deadline exceeded'}),
    ('out of order events',{'input':'out-of-order callback','state':'later state already applied'}),
    ('worker retries',{'retry':'worker retry','state':'partially committed'}),
    ('suspension during processing',{'permission':'account suspended','time':'after debit before settlement'}),
    ('fraud review during processing',{'permission':'fraud review hold','state':'pending settlement'}),
    ('administrative freeze',{'human_action':'admin freeze','state':'in-flight withdrawal'}),
    ('provider outage',{'dependency':'provider unavailable','recovery':'reconcile pending operation'}),
    ('database failure',{'storage':'database commit unavailable','recovery':'recover uncertain outcome'}),
    ('queue redelivery/retry',{'retry':'queue redelivery','state':'already processed'}),
    ('regional failure',{'network':'regional outage','recovery':'failover without duplicate settlement'}),
    ('reconciliation mismatch',{'business_rule':'ledger/provider totals disagree','recovery':'investigate unmatched settlement'}),
    ('support-agent manual retry',{'human_action':'manual support retry','retry':'automatic retry also pending'}),
    ('attacker replay',{'attack':'replayed authorization','permission':'expired authorization'})]

DEFAULT_AXES = {'input':['malformed input','duplicate input'],'state':['partially completed'],'time':['deadline exceeded'],'concurrency':['simultaneous actions'],'retry':['retry after uncertain result'],'network':['response lost'],'dependency':['dependency unavailable'],'storage':['write rejected'],'permission':['permission revoked'],'attack':['automated replay'],'scale':['hot tenant'],'cost':['unbounded billable operations'],'human_action':['operator repeats action'],'business_rule':['invariant violated'],'legal_consequence':['qualified review required'],'recovery':['restore prior consistent state']}


def risk_generation_engine(contract, *, limit=25, max_candidates=64, max_combinations=512, catalogue=None, queue=None):
    if not 1<=max_candidates<=500 or not 1<=max_combinations<=10000:
        raise ValueError('generation budgets out of bounds')
    context=normalize_project_context(contract)
    catalogue=catalogue or RiskCatalogue()
    selected=catalogue.select(context,limit)
    if context['documentation_only']:
        return {'engine':'Risk Generation Engine','selected_records':[],'selected_context_variants':[],'bounded_contextual_candidates':[],'catalogue_first_selection_count':0,'metrics':catalogue.stats,'axes_considered':[],'combinations_considered':0}
    features=context['features'] or ['unspecified feature']
    actors=context['user_types'] or ['unknown actor']
    axes={name:sequence(contract.get('adversity_axes',{}).get(name,values)) for name,values in DEFAULT_AXES.items()}
    if not context['external_providers']:
        axes['dependency']=[]
    if not context['jurisdictions']:
        axes['legal_consequence']=[]
    candidates=[]
    identities=set()
    considered=0
    withdrawal=[]

    def emit(feature,actor,label,conditions,source):
        nonlocal considered
        considered+=1
        if considered>max_combinations or len(candidates)>=max_candidates:
            return
        signature=json.dumps([feature,actor,conditions],sort_keys=True)
        if signature in identities:
            return
        identities.add(signature)
        trigger='; '.join(f'{k}={v}' for k,v in conditions.items())
        name=f'{feature}: {label}'
        candidate={'provenance_class':'SOURCE_IMPLIED' if source=='withdrawal-example' else 'ENGINEERING_EXPANSION','source':{'kind':'contextual-generation','reference':'source-4:risk-generation-engine','scenario':source},'definition':{'canonical_name':name,'category':'Contextual adversity','dimension':'product','root_cause':f'Interaction between {trigger} can invalidate assumptions of {feature}.','failure_mechanism':f'{actor} observes an incomplete, duplicated, unauthorized or inconsistent outcome while {trigger}.','trigger_conditions':trigger,'prevention_strategy':'Preserve the declared business invariant with bounded retries, explicit state transitions and atomic enforcement appropriate to this combination.','automated_test':f'Exercise {feature} under {trigger}; assert {contract.get("business_rules",["the specified correct outcome"])} and recoverable failure.','owner':contract.get('implementation_owner','ROLE GAP')},'context':{'feature':feature,'actor':actor,**conditions},'semantic_review_required':True}
        candidate['candidate_id']=candidate_id({k:v for k,v in candidate.items() if k!='candidate_id'})
        if queue:
            submit({k:v for k,v in candidate.items() if k!='candidate_id'},Path(queue))
        candidates.append(candidate)

    for feature,actor in product(features,actors):
        if str(feature).casefold() in {'withdrawal','transfer'} and context['money_movement'] is True:
            for label,conditions in WITHDRAWAL_ADVERSITY:
                emit(feature,actor,label,conditions,'withdrawal-example')
                withdrawal.append(label)
        for first,second in combinations(axes,2):
            for a,b in product(axes[first],axes[second]):
                emit(feature,actor,f'{first} and {second}',{first:a,second:b},'bounded-pairwise-adversity')
                if considered>=max_combinations or len(candidates)>=max_candidates:
                    break
            if considered>=max_combinations or len(candidates)>=max_candidates:
                break
        if considered>=max_combinations or len(candidates)>=max_candidates:
            break
    return {'engine':'Risk Generation Engine','catalogue_first_selection_count':len(selected),'selected_records':selected,'selected_context_variants':[r['risk_context_variant_id'] for r in selected],'bounded_contextual_candidates':candidates,'axes_considered':RISK_GENERATION_AXES,'combinations_considered':min(considered,max_combinations),'pruned':len(candidates)>=max_candidates or considered>=max_combinations,'metrics':dict(catalogue.stats),'withdrawal_transfer_regression':list(dict.fromkeys(withdrawal)),'promotion_policy':'submit -> review -> versioned candidate_workflow promotion; never direct catalogue mutation'}


def number(value):
    try:
        parsed=Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('cost and workload values must be numbers') from exc
    if not parsed.is_finite() or parsed<0:
        raise ValueError('cost and workload values must be finite and nonnegative')
    return parsed


def evaluate_trigger(trigger, metrics):
    if not isinstance(trigger,dict) or trigger.get('operator') not in {'>=','>','<=','<','=='} or not trigger.get('metric'):
        raise ValueError('trigger requires metric, comparison operator and threshold')
    if trigger['metric'] not in metrics:
        return 'UNKNOWN'
    actual=number(metrics[trigger['metric']]); threshold=number(trigger['threshold'])
    return {'>=':actual>=threshold,'>':actual>threshold,'<=':actual<=threshold,'<':actual<threshold,'==':actual==threshold}[trigger['operator']]


def economics_complexity_engine(contract):
    values=contract.get('cost_model',{})
    results=[]
    for item in source4()['economics_and_complexity']['cost_dimensions']:
        dimension=key(item['text'])
        observation=values.get(dimension)
        row={'dimension':dimension,'source_line':item['line'],'state':'UNKNOWN','cost_now':None,'cost_at_scale':None}
        if observation is not None:
            if not isinstance(observation,dict) or not all(k in observation for k in ('unit_cost','quantity','scale_quantity','currency','source')):
                raise ValueError(f'cost observation lacks units, currency or provenance: {dimension}')
            row.update(state='MEASURED',cost_now=str(number(observation['unit_cost'])*number(observation['quantity'])),cost_at_scale=str(number(observation['unit_cost'])*number(observation['scale_quantity'])),currency=observation['currency'],provenance=observation['source'])
        results.append(row)
    alternatives=[]
    for option in contract.get('architecture_options',[]):
        questions=[key(q['text']) for q in source4()['anti_overengineering_questions']]
        missing=[q for q in questions if not option.get('decision_answers',{}).get(q)]
        alternatives.append({'option':option.get('name'),'state':'INSUFFICIENT_RATIONALE' if missing else 'REVIEWABLE','missing_decision_questions':missing,'complexity_tax':str(number(option.get('engineering_hours',0))*number(option.get('hourly_cost',0))+number(option.get('monthly_operational_cost',0))),'activation':evaluate_trigger(option['activation_trigger'],contract.get('metrics',{})) if option.get('activation_trigger') else 'UNKNOWN'})
    anomaly=evaluate_trigger(contract['cost_anomaly_trigger'],contract.get('metrics',{})) if contract.get('cost_anomaly_trigger') else 'UNKNOWN'
    return {'engine':'Economics and Complexity Engine','cost_dimensions_available':len(results),'cost_dimensions':results,'architecture_options':alternatives,'cost_incident':anomaly is True,'currency_policy':'Different currencies and overlapping unit costs are never blindly summed.','project_id':contract.get('project_id'),'release_id':contract.get('release_id')}


def stage(value, maximum):
    if value in (None,'UNKNOWN'):
        return None
    match=re.match(r'^(?:Stage\s+)?(\d+)',str(value),re.I)
    if not match or not 0<=int(match.group(1))<=maximum:
        raise ValueError('invalid maturity/threat stage')
    return int(match.group(1))


def evolution_engine(contract):
    maturity=stage(contract.get('maturity_stage'),5)
    threat=stage(contract.get('threat_stage'),4)
    previous=contract.get('previous_context',{})
    reviews=[]
    for field,value in [('maturity_stage',maturity),('threat_stage',threat)]:
        if field in previous and stage(previous[field],5 if field=='maturity_stage' else 4)!=value:
            reviews.extend([field+':'+concern for concern in ('architecture','economics','risk_selection','evidence','staffing')])
    decisions=[]
    for decision in contract.get('deferred_complexity',[]):
        required=('id','reason','simpler_solution','deferral_risk','activation_trigger','migration_path','cost_impact','review_trigger')
        missing=[name for name in required if decision.get(name) in (None,'')]
        if missing:
            raise ValueError('deferral missing '+','.join(missing))
        triggered=evaluate_trigger(decision['activation_trigger'],contract.get('metrics',{}))
        review=evaluate_trigger(decision['review_trigger'],contract.get('metrics',{}))
        consequence=any(contract.get(flag) is True for flag in decision.get('activate_for',[]))
        state='REQUIRED_NOW' if decision.get('nondeferrable') or triggered is True or consequence else ('UNKNOWN' if triggered=='UNKNOWN' else 'DEFERRED')
        decisions.append({**decision,'state':state,'activation_reached':triggered,'review_required':review is True or bool(reviews),'current_maturity_stage':maturity,'current_threat_stage':threat})
    transitions=[]
    for rule in contract.get('stage_transition_indicators',[]):
        if rule.get('axis') not in {'maturity_stage','threat_stage'}:
            raise ValueError('stage transition must name a maturity or threat axis')
        stage(rule['target_stage'],5 if rule['axis']=='maturity_stage' else 4)
        transitions.append({**rule,'reached':evaluate_trigger(rule['trigger'],contract.get('metrics',{})),'decision':'REVIEW_STAGE_TRANSITION'})
    return {'engine':'Evolution Engine','current_maturity_stage':maturity,'current_threat_stage':threat,'decisions':decisions,'review_triggers':reviews,'transition_reviews':transitions,'product_maturity_stages':source4()['maturity_stages'],'threat_stages':source4()['threat_stages']}
