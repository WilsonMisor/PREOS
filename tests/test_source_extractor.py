import hashlib, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class SourceExtractorTests(unittest.TestCase):
    def test_extracts_exact_source_member(self):
        data=subprocess.check_output([sys.executable,str(ROOT/'scripts/extract-source.py'),'baseline_75_controls.json'],cwd=ROOT)
        self.assertEqual(hashlib.sha256(data).hexdigest(),'db4c900348ed824a26c7ff043759daba913d286ccb08fd7c3e2e98192a0f0edb')

if __name__=='__main__': unittest.main()
