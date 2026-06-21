from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.public_release import scan_paths  # noqa: E402


SCRIPT = ROOT / "skills/biosymphony-ferm-doe/scripts/public_release_check.py"


class PublicReleaseCheckTests(unittest.TestCase):
    def test_clean_public_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            safe = tmp_path / "README.md"
            safe.write_text(
                "\n".join(
                    [
                        "# Public fixture",
                        "Use portable placeholders such as <repo_path> and <orchestrator_home>.",
                        "Use capability tiers such as low-cost extraction and frontier reasoning.",
                    ]
                )
                + "\n"
            )

            self.assertEqual(scan_paths([tmp_path], root=tmp_path), [])

    def test_blocks_requested_private_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "release.md"
            issue_id = "VOG" + "-1271"
            bad.write_text(
                "\n".join(
                    [
                        "repo=" + "/" + "Users" + "/" + "example" + "/private-checkout",
                        "lane=" + "/" + "Users" + "/" + "example" + "/" + "auto" + "nomy" + "/" + "." + "claude" + "/" + "symphony" + "-claude",
                        "issue=https://" + "linear" + ".app/acme/issue/" + issue_id,
                        "runpod=" + "pod-" + "abc123def456",
                        "runtime=" + ".runtime/" + "runpod" + "/demo/artifacts.tar.gz",
                        "model=" + "claude-" + "sonnet" + "-4-6",
                        "marker=" + "unpublished " + "sequence",
                        "aws=" + "AKIA" + "A" * 16,
                        "gh=" + "ghp_" + "A" * 24,
                        "secret=" + "sk-" + "A" * 24,
                        "assigned=" + "api_key=" + "A" * 24,
                        "auth=Authorization: Bearer " + "eyJ" + "A" * 24 + ".payload.signature",
                        "placeholder=" + "[" + "validation-ticket" + "]",
                    ]
                )
                + "\n"
            )

            rule_ids = {finding.rule_id for finding in scan_paths([tmp_path], root=tmp_path, allow_private=[])}

            self.assertIn("local_path", rule_ids)
            self.assertIn("private_orchestration_marker", rule_ids)
            self.assertIn("linear_url", rule_ids)
            self.assertIn("linear_issue_id", rule_ids)
            self.assertIn("runpod_identifier", rule_ids)
            self.assertIn("runpod_provider_path", rule_ids)
            self.assertIn("private_model_name", rule_ids)
            self.assertIn("private_campaign_marker", rule_ids)
            self.assertIn("aws_access_key", rule_ids)
            self.assertIn("github_token", rule_ids)
            self.assertIn("api_token_like_value", rule_ids)
            self.assertIn("authorization_bearer_token", rule_ids)
            self.assertIn("assigned_secret_like_value", rule_ids)
            self.assertIn("tracker_placeholder", rule_ids)

    def test_guardrail_language_and_synthetic_ids_are_not_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            safe = tmp_path / "release.md"
            safe.write_text(
                "\n".join(
                    [
                        "Do not include private process data, unpublished sequences, or confidential formulations.",
                        "Use synthetic IDs such as EV-001, SYN-001, SW-W1-01, TASK-001, and BIO-142 in public examples.",
                        "A scale bridge can mention vvm and volume-limited regimes without implying a provider volume ID.",
                        "Use $RUNPOD_BRIDGE_BIN as a public-safe executable reference.",
                        "Send placeholders such as Authorization: Bearer <runtime token> or Authorization: Bearer $FERM_DOE_API_TOKEN.",
                    ]
                )
                + "\n"
            )

            self.assertEqual(scan_paths([tmp_path], root=tmp_path, allow_private=[]), [])

    def test_blocks_private_orchestration_lane_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "registry.md"
            bad.write_text("lane=" + "auto" + "nomy" + "/" + "." + "claude" + "/" + "symphony" + "-claude" + "\n")

            findings = scan_paths([tmp_path], root=tmp_path, allow_private=[])

            self.assertTrue(findings)
            self.assertEqual(findings[0].rule_id, "private_orchestration_marker")

    def test_private_docs_and_artifacts_require_explicit_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            private_doc = tmp_path / "docs/operator-only-defaults.md"
            private_doc.parent.mkdir(parents=True)
            private_doc.write_text("path=" + "/" + "Users" + "/" + "example" + "/" + "auto" + "nomy" + "\n")
            private_artifact = tmp_path / "artifacts/private/report.md"
            private_artifact.parent.mkdir(parents=True)
            private_artifact.write_text("model=" + "claude-" + "opus" + "-4-7" + "\n")

            self.assertTrue(scan_paths([tmp_path], root=tmp_path))
            self.assertEqual(
                scan_paths(
                    [tmp_path],
                    root=tmp_path,
                    allow_private=["docs/operator-only-*.md", "artifacts/private/**"],
                ),
                [],
            )

    def test_ignored_runtime_dirs_are_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runtime_report = tmp_path / ".runtime" / "validation" / "report.json"
            runtime_report.parent.mkdir(parents=True)
            runtime_report.write_text('{"repo_root": "' + "/" + 'Users/example/private-checkout"}\n')

            self.assertEqual(scan_paths([tmp_path], root=tmp_path), [])

    def test_custom_private_allowlist_can_be_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            private = tmp_path / "private-artifacts/report.md"
            private.parent.mkdir(parents=True)
            private.write_text("issue=" + "VOG" + "-2048" + "\n")

            blocked = scan_paths([tmp_path], root=tmp_path, allow_private=[])
            allowed = scan_paths([tmp_path], root=tmp_path, allow_private=["private-artifacts/**"])

            self.assertTrue(blocked)
            self.assertEqual(allowed, [])

    def test_audit_skip_marker_is_line_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            release = tmp_path / "release.md"
            release.write_text(
                "\n".join(
                    [
                        "fixture=" + "VOG" + "-2048 # audit-skip: linear_issue_id synthetic scanner fixture",
                        "real=" + "VOG" + "-2049",
                    ]
                )
                + "\n"
            )

            findings = scan_paths([tmp_path], root=tmp_path, allow_private=[])

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 2)
        self.assertEqual(findings[0].rule_id, "linear_issue_id")

    def test_script_json_output_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "bad.md"
            bad.write_text("linear=" + "VOG" + "-3001" + "\n")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--json", str(tmp_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["finding_count"], 1)
            self.assertEqual(payload["findings"][0]["rule_id"], "linear_issue_id")


if __name__ == "__main__":
    unittest.main()
