import json,hashlib,zipfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_zip_hashes(self):
  m=json.loads((ROOT/'source-package/SOURCE-MANIFEST.json').read_text()); z=ROOT/'source-package/original-package.zip'; self.assertEqual(hashlib.sha256(z.read_bytes()).hexdigest(),m['original_zip']['sha256'])
  with zipfile.ZipFile(z) as zp:
   for f in m['files']: self.assertEqual(hashlib.sha256(zp.read(f['name'])).hexdigest(),f['sha256'])
