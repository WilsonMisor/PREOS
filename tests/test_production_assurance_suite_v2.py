import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


class ProductionAssuranceSuiteV2Tests(unittest.TestCase):
    def test_source1_model2_corpus_is_installed(self):
        corpus = ROOT / 'references' / 'risks' / 'model2' / 'risk-corpus.jsonl'
        rows = [json.loads(line) for line in corpus.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 4337)
        self.assertEqual(sum(row['field_count'] != 40 for row in rows), 0)
        dimensions = {}
        for row in rows:
            dimensions[row['dimension']] = dimensions.get(row['dimension'], 0) + 1
        self.assertEqual(dimensions['universal'], 1406)
        self.assertEqual(dimensions['industry'], 1450)
        self.assertEqual(dimensions['product'], 753)
        self.assertEqual(dimensions['jurisdiction'], 328)
        self.assertEqual(dimensions['architecture'], 400)
    def test_concern_crosswalk_accounts_for_all_source1_fields_once(self):
        path = ROOT / 'references' / 'risks' / 'model2' / 'concern-separation-crosswalk.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(data['zero_loss'])
        observed = []
        for numbers in data['concerns'].values():
            observed.extend(numbers)
        self.assertEqual(sorted(observed), list(range(1, 41)))
        self.assertEqual(len(observed), len(set(observed)))
        self.assertIn('risk_definition', data['concerns'])
        self.assertIn('risk_assessment', data['concerns'])
        self.assertIn('risk_economics', data['concerns'])
        self.assertIn('risk_evolution', data['concerns'])
        self.assertIn('risk_evidence', data['concerns'])
        self.assertIn('risk_acceptance', data['concerns'])
    def test_source4_crosswalk_counts_and_authority_policy(self):
        path = ROOT / 'references' / 'integration' / 'source4-production-assurance-crosswalk.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        counts = data['counts']
        self.assertEqual(counts['roles'], 18)
        self.assertEqual(counts['questions'], 30)
        self.assertEqual(counts['assumptions'], 40)
        self.assertEqual(counts['context_dimensions'], 40)
        self.assertEqual(counts['domains'], 32)
        self.assertEqual(counts['test_families'], 28)
        self.assertEqual(counts['atomic_fields'], 37)
        self.assertEqual(counts['output_sections'], 20)
        self.assertIn('do not create competing top-level release authority', data['routing_policy'])
    def test_validator_keeps_model2_activation_gate_disabled(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / 'validate-risk-model2.py')],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('model2 catalogue: 4337 records validated', proc.stdout)
        self.assertIn('activation gate: disabled', proc.stdout)


if __name__ == '__main__':
    unittest.main()
