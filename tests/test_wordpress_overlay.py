import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OVERLAY = ROOT / "references" / "wordpress" / "wordpress-75-control-overlay.md"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


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

    def test_disposable_classic_theme_custom_plugin_interruption_recovery(self):
        """Exercise the WordPress E2E boundary in fresh PREOS processes."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "wordpress-app"
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "wp-preos@example.invalid")
            git(repo, "config", "user.name", "WP PREOS Test")

            theme = repo / "wp-content" / "themes" / "project-classic-theme"
            plugin = repo / "wp-content" / "plugins" / "project-site-core"
            theme.mkdir(parents=True)
            plugin.mkdir(parents=True)
            (theme / "style.css").write_text("/* Theme Name: Project Classic Theme */\n", encoding="utf-8")
            (theme / "functions.php").write_text("<?php // presentation bootstrap\n", encoding="utf-8")
            (theme / "front-page.php").write_text("<?php get_header(); ?><main>Home</main><?php get_footer(); ?>\n", encoding="utf-8")
            (plugin / "project-site-core.php").write_text("<?php // business/application logic\n", encoding="utf-8")
            (plugin / "permissions.php").write_text("<?php // current_user_can + WHERE-scoped authorization\n", encoding="utf-8")

            # The disposable architecture deliberately contains none of the forbidden
            # page-builder/block-theme proof paths from the governed WordPress profile.
            forbidden = ["theme.json", "templates/index.html", "patterns", "elementor", "divi", "bricks"]
            tree_names = [p.relative_to(repo).as_posix().lower() for p in repo.rglob("*")]
            for token in forbidden:
                self.assertFalse(any(token in name for name in tree_names), token)

            source = repo / "prd.md"
            source.write_text("Classic theme presentation; custom plugin business logic.\n", encoding="utf-8")
            import hashlib
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            contract = repo / "project-contract.json"
            contract.write_text(json.dumps({
                "project_id": "wp-e2e",
                "classification": {"profiles": ["web", "wordpress"], "production_assurance": "standard"},
                "source_hashes": [{"artifact": "prd.md", "sha256": source_hash}],
            }), encoding="utf-8")
            packet = repo / "task-packet.md"
            packet.write_text("WP-TP-001: bounded classic-theme/custom-plugin change; PREOS FS-001..FS-075 applicable decisions required.\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "disposable governed WordPress baseline")

            env = os.environ.copy()
            env["PREOS_STATE_ROOT"] = str(base / "state")
            def run(name, *args, check=True):
                return subprocess.run(
                    [os.sys.executable, str(SCRIPTS / name), *map(str, args)],
                    cwd=ROOT, env=env, check=check,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )

            run("init-project-state.py", "wp-e2e", "--repo", repo)
            # Capture a coherent interrupted implementation state.
            plugin_file = plugin / "project-site-core.php"
            plugin_file.write_text("<?php // business logic partial but durably checkpointed\n", encoding="utf-8")
            run(
                "checkpoint-state.py", "wp-e2e", "--repo", repo, "--kind", "soft",
                "--event", "SESSION_INTERRUPTED", "--project-contract", contract,
                "--project-contract-version", "WP-PC-1", "--task-packet", packet,
                "--task-packet-id", "WP-TP-001", "--last-verified-action", "plugin edit captured",
                "--next-unverified-action", "WordPress negative permission tests",
                "--pending-test", "wordpress:permission-and-row-scope",
            )
            recovered = run("recover-state.py", "wp-e2e", "--repo", repo)
            result = json.loads(recovered.stdout)
            self.assertEqual(result["status"], "SAFE_TO_RESUME")
            self.assertEqual(result["next_unverified_action"], "re-run uncertain test: wordpress:permission-and-row-scope")

            # An unexplained second edit after the durable checkpoint is not safe.
            (plugin / "permissions.php").write_text("<?php // unexplained external change\n", encoding="utf-8")
            conflict = run("recover-state.py", "wp-e2e", "--repo", repo, check=False)
            self.assertEqual(conflict.returncode, 2)
            conflict_result = json.loads(conflict.stdout)
            self.assertEqual(conflict_result["status"], "RECOVERY_CONFLICT")
            self.assertIn("WORKING_TREE_MISMATCH", {c["type"] for c in conflict_result["conflicts"]})


if __name__ == "__main__":
    unittest.main()
