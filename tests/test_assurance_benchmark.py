import math
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from assurance_benchmark import enforce_budgets, run_benchmark


class AssuranceBenchmarkTests(unittest.TestCase):
    def test_actual_workload_measures_memory_context_and_ci(self):
        result=run_benchmark()
        self.assertGreater(result['memory_peak_bytes'],1000000)
        self.assertGreater(result['ci_validation_duration_seconds'],0)
        self.assertGreater(result['ci_execution']['tests_executed'],0)
        self.assertEqual(result['ci_execution']['returncode'],0)
        self.assertGreater(result['workload']['selected_variants'],0)
        self.assertEqual(set(result['budgets']),{k for k in result if k in result['budgets']})
        enforce_budgets(result,result['budgets'])

    def test_every_metric_is_enforced_including_missing_nan_and_fake_values(self):
        fields=['catalogue_query_ms','selection_time_ms','context_generation_ms','memory_peak_bytes',
                'generated_context_size_bytes','compression_serialization_ms','compressed_context_size_bytes',
                'validation_time_ms','ci_validation_duration_seconds']
        budgets={name:10 for name in fields}
        for field in fields:
            for value in (11,-1,float('nan'),float('inf'),True,None):
                metrics={name:1 for name in fields};metrics[field]=value
                with self.assertRaises(ValueError,msg=field): enforce_budgets(metrics,budgets)
            metrics={name:1 for name in fields};metrics.pop(field)
            with self.assertRaises(ValueError): enforce_budgets(metrics,budgets)


if __name__=='__main__': unittest.main()
