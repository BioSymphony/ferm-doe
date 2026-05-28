from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.cli import main as cli_main  # noqa: E402
from biosymphony_ferm_doe.orchestration_brief import build_agent_brief, render_agent_brief_markdown  # noqa: E402


class OrchestrationBriefTests(unittest.TestCase):
    def test_agent_brief_captures_boundary_and_workstreams(self) -> None:
        brief = build_agent_brief(
            ROOT / "examples" / "demo-pb-screening-public",
            goal="Screen factors, then hand off follow-up through a Linear-style orchestrator.",
            command_style="public",
            compute_policy="cloud-prep",
            tracker="linear",
        )
        self.assertEqual(brief["brief_kind"], "biosymphony_ferm_doe_agent_brief")
        self.assertEqual(brief["campaign"]["campaign_id"], "demo-pb-screening-public")
        self.assertIn("orchestrator_owns", brief["orchestrator_boundary"])
        workstream_ids = {item["id"] for item in brief["workstreams"]}
        self.assertIn("intake", workstream_ids)
        self.assertIn("adaptive-wave2", workstream_ids)
        self.assertIn("remote-execution-prep", workstream_ids)

    def test_agent_brief_cli_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "brief.json"
            md_out = Path(tmp) / "brief.md"
            code = cli_main(
                [
                    "agent-brief",
                    str(ROOT / "examples" / "demo-pb-screening-public"),
                    "--goal",
                    "Use Codex or Symphony to plan the next safe action.",
                    "--out",
                    str(out),
                    "--md-out",
                    str(md_out),
                ]
            )
            self.assertEqual(code, 0)
            brief = json.loads(out.read_text())
            self.assertEqual(brief["brief_kind"], "biosymphony_ferm_doe_agent_brief")
            self.assertIn("Agent Brief", md_out.read_text())
            self.assertIn("First Commands", render_agent_brief_markdown(brief))

    def test_public_agent_brief_normalizes_private_command_style(self) -> None:
        brief = build_agent_brief(
            ROOT / "examples" / "demo-pb-screening-public",
            command_style="private",
        )
        commands = [command["command"] for command in brief["starter_commands"]]
        self.assertTrue(all("score-readiness" not in command for command in commands))
        self.assertTrue(all("compile-state" not in command for command in commands))
        self.assertTrue(any("generate-design" in check for item in brief["workstreams"] for check in item["acceptance_checks"]))
