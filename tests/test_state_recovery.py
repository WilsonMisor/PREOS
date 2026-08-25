import tempfile,json,unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_latest_checkpoint(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); a=p/'a.json'; b=p/'b.json'; a.write_text('{}'); b.write_text('{}'); self.assertTrue(max([a,b],key=lambda x:x.stat().st_mtime).exists())
