import hashlib,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_extract_baseline_exact_hash(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'baseline.json'
   subprocess.run([sys.executable,str(ROOT/'scripts/extract-source.py'),'baseline_75_controls.json','--output',str(out)],check=True,cwd=ROOT,stdout=subprocess.PIPE)
   self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),'db4c900348ed824a26c7ff043759daba913d286ccb08fd7c3e2e98192a0f0edb')
