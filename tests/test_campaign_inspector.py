from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.campaign_inspector import catalog_campaigns, inspect_campaign  # noqa: E402
from biosymphony_ferm_doe.cli import main as cli_main  # noqa: E402


class CampaignInspectorTests(unittest.TestCase):
    def test_inspect_campaign_summarizes_manifest_and_next_commands(self) -> None:
        report = inspect_campaign(ROOT / "examples" / "demo-pb-screening-public", command_style="public")
        self.assertEqual(report["campaign_id"], "demo-pb-screening-public")
        self.assertEqual(report["readiness"]["overall"], "YELLOW")
        self.assertEqual(report["counts"]["factors"], 7)
        self.assertTrue(report["capabilities"]["can_generate_wave1_design"])
        command_ids = {command["id"] for command in report["recommended_next_commands"]}
        self.assertIn("validate", command_ids)
        self.assertIn("generate-design", command_ids)

    def test_inspect_campaign_cli_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "inspection.json"
            code = cli_main(["inspect-campaign", str(ROOT / "examples" / "demo-pb-screening-public"), "--out", str(out)])
            self.assertEqual(code, 0)
            report = json.loads(out.read_text())
            self.assertEqual(report["inspection_kind"], "biosymphony_ferm_doe_campaign_inspection")
            self.assertIn("recommended_next_commands", report)

    def test_catalog_campaigns_summarizes_examples(self) -> None:
        report = catalog_campaigns(ROOT / "examples", command_style="public")
        self.assertEqual(report["catalog_kind"], "biosymphony_ferm_doe_campaign_catalog")
        self.assertGreaterEqual(report["campaign_count"], 5)
        self.assertGreaterEqual(report["capability_counts"]["can_generate_wave1_design"], 5)
        campaign_ids = {campaign["campaign_id"] for campaign in report["campaigns"]}
        self.assertIn("demo-pb-screening-public", campaign_ids)
        self.assertIn("screening", report["profile_counts"])

    def test_catalog_campaigns_cli_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "catalog.json"
            code = cli_main(["list-campaigns", str(ROOT / "examples"), "--out", str(out)])
            self.assertEqual(code, 0)
            report = json.loads(out.read_text())
            self.assertGreaterEqual(report["campaign_count"], 5)
            self.assertIn("campaigns", report)

    def test_public_inspector_does_not_emit_private_only_commands(self) -> None:
        report = inspect_campaign(ROOT / "examples" / "demo-pb-screening-public", command_style="private")
        commands = [command["command"] for command in report["recommended_next_commands"]]
        self.assertTrue(commands)
        self.assertTrue(all("score-readiness" not in command for command in commands))
        self.assertTrue(all("compile-state" not in command for command in commands))
        self.assertTrue(all("check-public-dossier" not in command for command in commands))
