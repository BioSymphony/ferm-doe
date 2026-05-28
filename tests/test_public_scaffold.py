from __future__ import annotations

import os
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicScaffoldTests(unittest.TestCase):
    def test_readme_assets_exist(self) -> None:
        readme = (ROOT / "README.md").read_text()
        for asset in [
            "assets/images/biosymphony-ferm-doe-banner.png",
            "assets/images/biosymphony-ferm-doe-pipeline.png",
            "assets/images/biosymphony-agent-loop.svg",
        ]:
            self.assertIn(asset, readme)
            self.assertTrue((ROOT / asset).exists(), asset)

    def test_newcomer_docs_are_linked(self) -> None:
        readme = (ROOT / "README.md").read_text()
        docs_readme = (ROOT / "docs/README.md").read_text()
        for rel_path in [
            "docs/AGENT_QUICKSTART.md",
            "docs/USE_CASES.md",
            "docs/WORKFLOWS.md",
            "docs/PUBLIC_SECURITY_MODEL.md",
            "docs/superpowers.md",
            "docs/RELEASE_READINESS_CHECKLIST.md",
            "docs/diagrams/agent-loop-public.mmd",
        ]:
            self.assertTrue((ROOT / rel_path).is_file(), rel_path)
            self.assertIn(rel_path, readme)
        for rel_path in [
            "AGENT_QUICKSTART.md",
            "USE_CASES.md",
            "WORKFLOWS.md",
            "superpowers.md",
            "RELEASE_READINESS_CHECKLIST.md",
            "diagrams/agent-loop-public.mmd",
        ]:
            self.assertIn(rel_path, docs_readme)

    def test_release_scanner_covers_newcomer_public_surface(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        noxfile = (ROOT / "noxfile.py").read_text()
        for rel_path in [
            "assets/images/biosymphony-agent-loop.svg",
            "docs/AGENT_QUICKSTART.md",
            "docs/USE_CASES.md",
            "docs/WORKFLOWS.md",
            "docs/PUBLIC_ADOPTION_PATH.md",
            "docs/PUBLIC_SECURITY_MODEL.md",
            "docs/RELEASE_READINESS_CHECKLIST.md",
            "docs/ISSUE_PACK_COOKBOOK.md",
            "docs/superpowers.md",
            "docs/diagrams",
            "agents",
        ]:
            self.assertIn(rel_path, makefile)
            self.assertIn(rel_path, noxfile)
        self.assertIn("markdown-links", makefile)
        self.assertIn("secret-scan-required", makefile)
        self.assertIn("secret-scan-required", noxfile)
        self.assertIn("scripts/check_markdown_links.py", makefile)
        self.assertIn("scripts/check_markdown_links.py", noxfile)

    def test_local_markdown_links_resolve(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/check_markdown_links.py", "."],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: local Markdown links resolved", result.stdout)

    def test_demo_readme_exists(self) -> None:
        self.assertTrue((ROOT / "examples/demo-xylanase-public/README.md").exists())

    def test_demo_artifact_contract_exists(self) -> None:
        example = ROOT / "examples/demo-xylanase-public"
        for rel_path in [
            "campaign_manifest.json",
            "inputs/historical_run_ledger.csv",
            "inputs/equipment_inventory.csv",
            "inputs/reagent_inventory.csv",
            "inputs/evidence_table.csv",
            "expected/readiness_summary.json",
            "expected/selected_wave_1_design.csv",
            "expected/run_packet.md",
            "expected/AGENTS.md",
        ]:
            self.assertTrue((example / rel_path).is_file(), rel_path)

    def test_cli_validate_demo_contract(self) -> None:
        env = dict(os.environ)
        src = str(ROOT / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "biosymphony_ferm_doe.cli",
                "validate",
                "examples/demo-xylanase-public",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "YELLOW")
        self.assertEqual(payload["error_count"], 0)
        check_ids = {check["id"] for check in payload["checks"]}
        self.assertIn("assay-contract-xylanase_activity_u_ml", check_ids)
        self.assertIn("design-bounds-selected_wave_1_design.csv", check_ids)

    def test_cli_first_run_entrypoints_are_copy_paste_safe(self) -> None:
        env = dict(os.environ)
        src = str(ROOT / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        cases = [
            ([sys.executable, "-m", "biosymphony_ferm_doe.cli"], 0, "demo-xylanase-public"),
            ([sys.executable, "-m", "biosymphony_ferm_doe.cli", "--version"], 0, "0.1.0a0"),
            ([sys.executable, "-m", "biosymphony_ferm_doe.cli", "--help"], 0, "validate"),
            (
                [
                    sys.executable,
                    "-m",
                    "biosymphony_ferm_doe.cli",
                    "examples/demo-scale-bridge-public",
                    "--summary",
                ],
                0,
                "demo-scale-bridge-public",
            ),
        ]
        for command, expected_code, expected_text in cases:
            with self.subTest(command=command):
                result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, expected_code, result.stderr)
                self.assertIn(expected_text, result.stdout)

    def test_cli_public_audit_passes(self) -> None:
        env = dict(os.environ)
        src = str(ROOT / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "biosymphony_ferm_doe.cli",
                "audit",
                ".",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["issue_count"], 0)

    def test_no_private_paths_or_tokens(self) -> None:
        forbidden_patterns = [
            re.compile(r"/(?:Users|Volumes|home)/[A-Za-z0-9._-]+(?=[/\s'\"]|$)"),
            re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
            re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
            re.compile(
                r"(?i)\bAuthorization\s*:\s*Bearer\s+"
                r"(?!(?:<[^>\n]*(?:token|redacted)[^>\n]*>|redacted|REDACTED|\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*\})\b)"
                r"[A-Za-z0-9._~+/-]{16,}"
            ),
            re.compile(
                r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{16,}"
            ),
        ]
        allowed_dirs = {
            ".git",
            ".mypy_cache",
            ".nox",
            ".pytest_cache",
            ".ruff_cache",
            ".runtime",
            "__pycache__",
        }
        skip_re = re.compile(r"#\s*audit-skip:")
        for path in ROOT.rglob("*"):
            rel_parts = path.relative_to(ROOT).parts
            if any(part in allowed_dirs for part in rel_parts):
                continue
            if path.suffix == ".pyc":
                continue
            if not (path.is_file() and path.suffix.lower() not in {".png"}):
                continue
            for line_number, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
                if skip_re.search(line):
                    continue
                for pattern in forbidden_patterns:
                    self.assertIsNone(
                        pattern.search(line),
                        f"{pattern.pattern} in {path.relative_to(ROOT)}:{line_number}",
                    )


if __name__ == "__main__":
    unittest.main()
