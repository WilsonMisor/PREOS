import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import assurance_engines as ae
import control_assurance as ca


def high_fixture():
    return {'project_id':'SaaS-NG','release_id':'r1','product_type':'SaaS','profiles':['saas','web','api','data','infrastructure'],'tenant_model':'multi-tenant','payments':True,'personal_data':True,'architecture':['REST','relational database','queue'],'external_providers':['payment provider'],'jurisdictions':['Nigeria'],'features':['withdrawal'],'actors':['tenant user'],'first_production_release':True,'maturity_stage':1,'threat_stage':2,'business_rules':['ledger balances','one posting per event','tenant isolation']}


class ContextEngineTests(unittest.TestCase):
    def test_all_source_dimensions_have_known_assumed_or_unknown_values(self):
        context=ae.normalize_project_context(high_fixture())
        self.assertEqual(len(context['dimensions']),len(ae.source4()['context_dimensions']))
        self.assertTrue(context['money_movement'])
        self.assertEqual(context['dimensions']['budget']['state'],'UNKNOWN')
        self.assertIsNone(context['dimensions']['budget']['value'])

    def test_false_is_known_and_no_keyword_turns_it_into_true(self):
        context=ae.normalize_project_context({'money_movement':False,'personal_data':False,'notes':'payment processing is not enabled'})
        self.assertFalse(context['money_movement'])
        self.assertEqual(context['dimensions']['money_movement']['state'],'KNOWN')
        with self.assertRaises(ValueError):
            ae.normalize_project_context({'money_movement':'false'})

    def test_contract_classification_conflict_and_alias_conflict_fail_closed(self):
        for contract in ({'classification':{'payments':True},'payments':False},{'money_movement':False,'payments':True}):
            with self.assertRaises(ValueError):
                ae.normalize_project_context(contract)

    def test_assumptions_require_owner_provenance_and_validation_trigger(self):
        contract={'assumptions':[{'dimension':'expected_users','value':100}]}
        with self.assertRaises(ValueError):
            ae.normalize_project_context(contract)
        contract['assumptions'][0].update(owner='Product Owner',provenance='planning estimate',validation_trigger='first cohort measurement')
        result=ae.normalize_project_context(contract)
        self.assertEqual(result['dimensions']['expected_users']['state'],'ASSUMPTION')


class RiskGenerationEngineTests(unittest.TestCase):
    def test_selection_uses_real_variants_across_required_contexts(self):
        result=ae.risk_generation_engine(high_fixture())
        rows=result['selected_records']
        self.assertLessEqual(len(rows),25)
        self.assertEqual(set(r['dimension'] for r in rows),{'universal','industry','product','jurisdiction','architecture'})
        self.assertTrue(any(r['category']=='Nigeria' for r in rows))
        self.assertTrue(any('REST' in r['category'] for r in rows))
        self.assertTrue(any('Relational database' in r['category'] for r in rows))
        self.assertTrue(any('Queues' in r['category'] for r in rows))
        self.assertTrue(all(r['authority']=='CONTEXT_ONLY_PENDING_MODEL2_APPROVAL' for r in rows))

    def test_withdrawal_generates_all_eighteen_real_conditions_and_candidate_ids(self):
        result=ae.risk_generation_engine(high_fixture())
        expected={label for label,_ in ae.WITHDRAWAL_ADVERSITY}
        self.assertEqual(set(result['withdrawal_transfer_regression']),expected)
        candidates=result['bounded_contextual_candidates']
        self.assertTrue(all(c['candidate_id'].startswith('CAND-') for c in candidates))
        self.assertTrue(all(len(c['context'])>=3 for c in candidates))
        self.assertTrue(all(len(conditions)==2 for _,conditions in ae.WITHDRAWAL_ADVERSITY))
        self.assertTrue(any(c['context'].get('attack')=='replayed authorization' for c in candidates))

    def test_combinations_are_deterministic_pruned_and_not_finance_only(self):
        contract={'features':['document upload'],'actors':['editor'],'money_movement':False,'jurisdictions':['test jurisdiction'],'external_providers':['object store'],'adversity_axes':{axis:[str(i) for i in range(30)] for axis in ae.DEFAULT_AXES}}
        one=ae.risk_generation_engine(contract,max_candidates=8,max_combinations=20)
        two=ae.risk_generation_engine(contract,max_candidates=8,max_combinations=20)
        self.assertEqual(one,two)
        self.assertEqual(len(one['bounded_contextual_candidates']),8)
        self.assertTrue(one['pruned'])
        self.assertLessEqual(one['combinations_considered'],20)
        self.assertEqual(one['withdrawal_transfer_regression'],[])

    def test_generation_submits_candidates_without_touching_canonical_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            result=ae.risk_generation_engine(high_fixture(),max_candidates=3,queue=directory)
            self.assertEqual(len(list(Path(directory).glob('CAND-*.json'))),3)
            self.assertTrue(all(c['semantic_review_required'] for c in result['bounded_contextual_candidates']))

    def test_documentation_only_never_opens_the_catalogue(self):
        catalogue=ae.RiskCatalogue(Path('must-not-exist'))
        with patch.object(catalogue,'records',side_effect=AssertionError('documentation scanned full corpus')):
            result=ae.risk_generation_engine({'documentation_only':True},catalogue=catalogue)
        self.assertEqual(result['selected_records'],[])
        self.assertEqual(result['metrics']['records_read'],0)
        self.assertEqual(result['bounded_contextual_candidates'],[])


class EconomicsEvolutionTests(unittest.TestCase):
    def test_costs_calculate_now_and_at_scale_with_unknowns_retained(self):
        fixture={'cost_model':{'cost_per_transaction':{'unit_cost':'0.25','quantity':100,'scale_quantity':10000,'currency':'NGN','source':'fixture quote'}}}
        result=ae.economics_complexity_engine(fixture)
        measured=next(r for r in result['cost_dimensions'] if r['dimension']=='cost_per_transaction')
        self.assertEqual(measured['cost_now'],'25.00')
        self.assertEqual(measured['cost_at_scale'],'2500.00')
        self.assertEqual(result['cost_dimensions_available'],25)
        self.assertTrue(any(r['state']=='UNKNOWN' for r in result['cost_dimensions']))
        for bad in ('NaN','Infinity',-1):
            fixture['cost_model']['cost_per_transaction']['unit_cost']=bad
            with self.assertRaises(ValueError):
                ae.economics_complexity_engine(fixture)

    def test_cost_anomaly_can_be_incident_while_service_is_available(self):
        result=ae.economics_complexity_engine({'metrics':{'bill':1100},'cost_anomaly_trigger':{'metric':'bill','operator':'>','threshold':1000},'availability':'healthy'})
        self.assertTrue(result['cost_incident'])

    def test_architecture_option_requires_all_anti_overengineering_answers(self):
        option={'name':'queue cluster','engineering_hours':10,'hourly_cost':20,'monthly_operational_cost':50}
        result=ae.economics_complexity_engine({'architecture_options':[option]})
        self.assertEqual(result['architecture_options'][0]['state'],'INSUFFICIENT_RATIONALE')
        self.assertEqual(result['architecture_options'][0]['complexity_tax'],'250')
        option['decision_answers']={ae.key(q['text']):'fixture rationale' for q in ae.source4()['anti_overengineering_questions']}
        self.assertEqual(ae.economics_complexity_engine({'architecture_options':[option]})['architecture_options'][0]['state'],'REVIEWABLE')

    def deferral(self):
        return {'id':'DC-1','reason':'Current throughput is small','simpler_solution':'single worker','deferral_risk':'queue delay','activation_trigger':{'metric':'queue_depth','operator':'>=','threshold':100},'migration_path':'add consumer after partition test','cost_impact':'one worker now','review_trigger':{'metric':'queue_delay','operator':'>','threshold':20}}

    def test_deferral_activates_at_measured_trigger_and_preserves_input(self):
        fixture={'maturity_stage':1,'threat_stage':0,'metrics':{'queue_depth':5,'queue_delay':1},'deferred_complexity':[self.deferral()]}
        before=copy.deepcopy(fixture)
        self.assertEqual(ae.evolution_engine(fixture)['decisions'][0]['state'],'DEFERRED')
        self.assertEqual(fixture,before)
        fixture['metrics']['queue_depth']=100
        self.assertEqual(ae.evolution_engine(fixture)['decisions'][0]['state'],'REQUIRED_NOW')
        fixture['deferred_complexity'][0]['nondeferrable']=True
        fixture['metrics']['queue_depth']=1
        self.assertEqual(ae.evolution_engine(fixture)['decisions'][0]['state'],'REQUIRED_NOW')

    def test_missing_deferral_fields_and_trigger_metrics_do_not_authorize_deferral(self):
        with self.assertRaises(ValueError):
            ae.evolution_engine({'deferred_complexity':[{'id':'DC-missing'}]})
        result=ae.evolution_engine({'deferred_complexity':[self.deferral()]})
        self.assertEqual(result['decisions'][0]['state'],'UNKNOWN')

    def test_maturity_and_threat_changes_review_dependent_concerns_separately(self):
        result=ae.evolution_engine({'maturity_stage':2,'threat_stage':3,'previous_context':{'maturity_stage':1,'threat_stage':3}})
        self.assertEqual(len(result['review_triggers']),5)
        self.assertTrue(all(s.startswith('maturity_stage:') for s in result['review_triggers']))


class NondeferrableControlTests(unittest.TestCase):
    def test_mapping_uses_semantic_baseline_controls_not_ordinal_numbers(self):
        controls={c['nondeferrable_control_id']:c for c in ca.nondeferrable_control_map()}
        self.assertEqual(controls['NDC-06']['preos_control_ids'],['FS-003'])
        self.assertIn('FS-074',controls['NDC-05']['preos_control_ids'])
        self.assertIn('FS-012',controls['NDC-12']['preos_control_ids'])

    def test_missing_evidence_blocks_small_first_release_and_later_releases(self):
        for first in (True,False):
            fixture=high_fixture()
            fixture.update(first_production_release=first,expected_users=1,team_size=1)
            result=ca.evaluate_nondeferrable_controls(fixture)
            self.assertTrue(result['blocked'])
            self.assertTrue(all(r['blockers'] for r in result['results']))

    def test_not_applicable_is_derived_not_a_user_override(self):
        fixture=high_fixture()
        fixture.update(payments=False,tenant_model='single-tenant')
        rows={r['nondeferrable_control_id']:r for r in ca.evaluate_nondeferrable_controls(fixture)['results']}
        self.assertEqual(rows['NDC-18']['applicability'],'NOT_APPLICABLE')
        fixture['control_dispositions']={'NDC-06':'NOT_APPLICABLE'}
        result=ca.evaluate_nondeferrable_controls(fixture)
        self.assertTrue(any('contradicts' in reason for r in result['results'] for reason in r['blockers']))

    def test_current_string_cannot_make_evidence_green(self):
        result=ca.evidence_gate_engine(high_fixture(),{'NDC-06':'CURRENT'},repo=Path(__file__).resolve().parents[1])
        self.assertEqual(result['gate_state'],'RED')
        self.assertFalse(result['production_authorized'])


if __name__ == '__main__':
    unittest.main()
