import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from risk_graph import RiskGraph


class RiskGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.graph=RiskGraph()

    def test_relationships_resolve_without_inventing_control_evidence_or_incident_edges(self):
        total=len(self.graph.relationships)
        self.assertEqual(self.graph.query('relationship',limit=3)['total_matches'],total)
        for kind in ('causes','amplifies','mitigated-by','affected-gates','evidence','incidents'):
            result=self.graph.query(kind)
            self.assertEqual(result['total_matches'],0,kind)
            self.assertEqual(result['empty_result_policy'],'NO_VALIDATED_RELATION_EXISTS')

    def test_facets_are_exact_source_categories_and_query_is_identity_based(self):
        for query,dimension in [('industries','industry'),('products','product'),('architectures','architecture'),('jurisdictions','jurisdiction')]:
            variant=next(v for v in self.graph.variants.values() if v['dimension']==dimension)
            found=self.graph.query(query,variant['risk_context_variant_id'])
            self.assertEqual(found['total_matches'],1)
            self.assertEqual(self.graph.query(query,variant['risk_context_variant_id'][:-1])['total_matches'],0)
        edge=self.graph.relationships[0]
        self.assertEqual(self.graph.query('relationship',edge['relationship_id'])['total_matches'],1)
        self.assertEqual(self.graph.query('relationship','REL-')['total_matches'],0)

    def test_query_limit_and_unknown_types_fail(self):
        for limit in (0,-1,501,True):
            with self.assertRaises(ValueError): self.graph.query('relationship',limit=limit)
        with self.assertRaises(ValueError): self.graph.query('fabricated')

    def test_unresolved_canonical_edge_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'normalized-risk-definitions.jsonl').write_text('')
            (root/'risk-context-variants.jsonl').write_text('')
            (root/'risk-relationships.jsonl').write_text(json.dumps(self.graph.relationships[0])+'\n')
            with self.assertRaisesRegex(ValueError,'unresolved'):
                RiskGraph(root)


if __name__=='__main__': unittest.main()
