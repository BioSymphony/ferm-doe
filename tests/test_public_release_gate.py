from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.public_release import scan_paths  # noqa: E402
from biosymphony_ferm_doe.validators import audit_public_tree  # noqa: E402


class PublicReleaseGateTests(unittest.TestCase):
    def test_strict_public_release_scan_passes_repo(self) -> None:
        findings = scan_paths([ROOT], root=ROOT)
        self.assertEqual([], findings)

    def test_scanner_does_not_flag_its_own_rules(self) -> None:
        findings = scan_paths([SRC / "biosymphony_ferm_doe" / "public_release.py"], root=ROOT)
        self.assertEqual([], findings)

    def test_audit_cli_uses_strict_scanner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_path = "/" + "Users/example/private-campaign.json"
            (root / "notes.md").write_text(f"input path: {private_path}\n", encoding="utf-8")
            payload = audit_public_tree(root)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("local_path", payload["issues"][0]["kind"])

    def test_audit_skips_ignored_runtime_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / ".runtime" / "validation" / "report.json"
            report.parent.mkdir(parents=True)
            report.write_text('{"repo_root": "' + "/" + 'Users/example/private-checkout"}\n', encoding="utf-8")
            payload = audit_public_tree(root)
        self.assertEqual("PASS", payload["status"])

    def test_public_cli_audit_passes_repo(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-m", "biosymphony_ferm_doe.cli", "audit", "."],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(0, payload["issue_count"])


if __name__ == "__main__":
    unittest.main()
