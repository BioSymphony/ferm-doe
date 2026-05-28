from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.linear_dry_run import generate_issue_pack  # noqa: E402


DOE_REFERENCE_MANIFEST = ROOT / "examples/reference-doe-custom-design/campaign_manifest.json"


class IssuePackLoaderTests(unittest.TestCase):
    def test_default_no_pack_stays_on_legacy_six_issue_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = generate_issue_pack(DOE_REFERENCE_MANIFEST, out)

        self.assertEqual(result["requested_packs"], ["fermentation-readiness-v0"])
        self.assertEqual(len(result["issues"]), 6)
        self.assertNotIn("packs", result)
        self.assertEqual(result["issues"][0]["issue_id"], "W0-01")

    def test_named_yaml_pack_loads_metadata_markdown_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = generate_issue_pack(DOE_REFERENCE_MANIFEST, out, ["campaign-arms-v1"])

            first_body = (out / "ca-w0-01-campaign-arms-contract.md").read_text()

        self.assertEqual(result["packs"][0]["pack_id"], "campaign-arms-v1")
        self.assertEqual(result["packs"][0]["name"], "Campaign Arms First-Class Contract")
        self.assertEqual(result["packs"][0]["parallelism_policy"]["W1"], 2)
        self.assertEqual(len(result["issues"]), 4)
        self.assertEqual(result["issues"][0]["source_file"], "packs/issue-packs/campaign-arms-v1/issues/01-campaign-arms-contract.md")
        issue_by_id = {issue["issue_id"]: issue for issue in result["issues"]}
        self.assertEqual(issue_by_id["CA-W1-01"]["depends_on"], ["CA-W0-01"])
        self.assertIn("# Campaign Arms Contract", first_body)
        self.assertIn("pack_id: campaign-arms-v1", first_body)
        self.assertIn("symphony-outcome", first_body)

    def test_current_named_issue_packs_use_pack_directories_not_default_fallback(self) -> None:
        expected_counts = {
            "campaign-arms-v1": 4,
            "doe-parity-v1": 9,
            "adaptive-wave2-assay-power-v0": 5,
            "scientific-swarm-v0": 11,
            "evidence-executor-v0": 4,
        }
        for pack_id, expected_count in expected_counts.items():
            with self.subTest(pack_id=pack_id), tempfile.TemporaryDirectory() as tmp:
                result = generate_issue_pack(DOE_REFERENCE_MANIFEST, Path(tmp), [pack_id])

            self.assertEqual(result["packs"][0]["pack_id"], pack_id)
            self.assertEqual(result["packs"][0]["issue_count"], expected_count)
            self.assertEqual(len(result["issues"]), expected_count)
            self.assertTrue(all(issue["pack_id"] == pack_id for issue in result["issues"]))
            self.assertNotEqual([issue["issue_id"] for issue in result["issues"]], ["W0-01", "W1-01", "W1-02", "W2-01", "W3-01", "W4-01"])

    def test_json_pack_path_loads_with_same_dependency_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "json-pack"
            issue_dir = pack_dir / "issues"
            issue_dir.mkdir(parents=True)
            (issue_dir / "01-alpha.md").write_text("# Alpha Issue\n\n## Expected Artifacts\n\n- `alpha.json`\n")
            (issue_dir / "02-beta.md").write_text("# Beta Issue\n")
            pack_path = pack_dir / "pack.json"
            pack_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "pack_id": "json-test-v0",
                        "pack_type": "issue_pack",
                        "name": "JSON Test Pack",
                        "parallelism_policy": {"J0": 1},
                        "issues": [
                            {"id": "alpha", "file": "issues/01-alpha.md", "wave": "J0", "blocks": ["beta"]},
                            {"id": "beta", "file": "issues/02-beta.md", "wave": "J1", "blocks": []},
                        ],
                    }
                )
                + "\n"
            )
            out = Path(tmp) / "out"
            result = generate_issue_pack(DOE_REFERENCE_MANIFEST, out, [str(pack_path)])
            alpha_body = (out / "alpha-alpha-issue.md").read_text()

        self.assertEqual(result["packs"][0]["pack_id"], "json-test-v0")
        self.assertEqual(result["parallelism_policy"], {"J0": 1})
        self.assertEqual(result["issues"][1]["depends_on"], ["alpha"])
        self.assertIn("alpha.json", alpha_body)
        self.assertIn("pack_issue_id: alpha", alpha_body)

    def test_unknown_explicit_pack_does_not_emit_default_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                generate_issue_pack(DOE_REFERENCE_MANIFEST, Path(tmp), ["not-a-real-pack"])


if __name__ == "__main__":
    unittest.main()
