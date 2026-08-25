import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from preos_common import load_source_json
class T(unittest.TestCase):
 def test_75(self):
  d=load_source_json('baseline_75_controls.json',ROOT.parent); self.assertEqual(d['count'],75); self.assertEqual([x['no'] for x in d['controls']],list(range(1,76)))
