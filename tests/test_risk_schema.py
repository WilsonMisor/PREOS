import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from preos_common import iter_risks
class T(unittest.TestCase):
 def test_risk_count_and_ids(self):
  rows=list(iter_risks(ROOT.parent)); self.assertEqual(len(rows),1130); self.assertEqual(len({r['check_id'] for r in rows}),1130); self.assertEqual(len({r['domain'] for r in rows}),52)
