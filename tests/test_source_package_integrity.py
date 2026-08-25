import json,hashlib,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from preos_common import source_package_bytes,open_source_zip
class T(unittest.TestCase):
 def test_reconstructed_zip_hashes(self):
  m=json.loads((ROOT/'source-package/SOURCE-MANIFEST.json').read_text()); raw=source_package_bytes(ROOT); self.assertEqual(len(raw),m['original_zip']['bytes']); self.assertEqual(hashlib.sha256(raw).hexdigest(),m['original_zip']['sha256'])
  with open_source_zip(ROOT) as zp:
   for f in m['files']: self.assertEqual(hashlib.sha256(zp.read(f['name'])).hexdigest(),f['sha256'])
