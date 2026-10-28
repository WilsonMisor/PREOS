import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from canonical_sources import DIRECTORY, SOURCES, source_bytes


class CanonicalSourceTests(unittest.TestCase):
    def test_all_four_sources_are_preserved_with_governing_hashes(self):
        for sid,(_,expected) in SOURCES.items():
            raw=source_bytes(sid)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),expected)

    def test_archive_corruption_and_manifest_tampering_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            shutil.copyfile(DIRECTORY/'manifest.json',root/'manifest.json')
            shutil.copyfile(DIRECTORY/'source-4.gz',root/'source-4.gz')
            (root/'source-4.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'archive changed'): source_bytes('source-4',root)
            manifest=json.loads((root/'manifest.json').read_text())
            manifest['sources'][-1]['sha256']='0'*64
            (root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'authority mismatch'): source_bytes('source-4',root)


if __name__=='__main__': unittest.main()
