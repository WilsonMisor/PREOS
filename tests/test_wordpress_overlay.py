import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "references" / "wordpress" / "wordpress-75-control-overlay.md"


class WordPressOverlayTests(unittest.TestCase):
    def test_exactly_one_mapping_per_control(self):
        text = OVERLAY.read_text(encoding="utf-8")
        ids = re.findall(r"\| (FS-\d{3}) \|", text)
        expected = [f"FS-{n:03d}" for n in range(1, 76)]
        self.assertEqual(ids, expected)
        self.assertEqual(len(set(ids)), 75)

    def test_wordpress_security_boundaries_present(self):
        text = OVERLAY.read_text(encoding="utf-8")
        for token in [
            "classic theme owns presentation",
            "custom plugin owns application/business logic",
            "permission_callback",
            "WHERE`-scoped access",
            "current_user_can",
            "map_meta_cap",
            "FS-074",
            "FS-075",
        ]:
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
