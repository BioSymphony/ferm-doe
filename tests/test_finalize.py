from __future__ import annotations

import csv
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

from biosymphony_ferm_doe.finalize import (  # noqa: E402
    CLAIM_LEVEL,
    compose_run_packet,
    render_run_packet_markdown,
)


def _manifest() -> dict:
    return {
        "campaign_id": "demo-finalize-test",
        "claim_level": "public_synthetic_demo",
        "profiles": ["screening"],
        "objective": "Test the run packet composer end-to-end.",
        "system": {"organism_label": "public_demo_microbe", "privacy": "synthetic_or_public_only", "scale": "shake_flask"},
        "responses": [
            {
                "response_id": "y",
                "class": "titer",
                "direction": "maximize",
                "assay_required": True,
                "objective_lower": 0.0,
                "objective_upper": 30.0,
            }
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0.0, "high": 10.0},
            {"factor_id": "x2", "type": "numeric", "low": 0.0, "high": 10.0},
            {"factor_id": "x3", "type": "numeric", "low": 0.0, "high": 10.0},
        ],
        "doe": {
            "family": "fractional_factorial",
            "model_terms": ["main_effects"],
            "design_table_path": "expected/selected_wave_1_design.csv",
        },
        "decision_rules": [],
        "stop_rules": [
            {"rule_id": "stop-on-assay-failure", "condition": "linearity not established", "action": "pause"}
        ],
        "risk_register": [
            {"risk_id": "r1", "category": "measurement", "likelihood": "low", "impact": "medium", "mitigation": "qualify assay", "status": "open"}
        ],
        "assumptions": [
            {"assumption_id": "a1", "statement": "synthetic data", "status": "inferred"}
        ],
        "readiness_expectation": "YELLOW",
    }


def _campaign_dir(root: Path) -> Path:
    campaign = root / "campaign"
    campaign.mkdir()
    (campaign / "campaign_manifest.json").write_text(json.dumps(_manifest(), indent=2), encoding="utf-8")
    inputs = campaign / "inputs"
    inputs.mkdir()
    (inputs / "evidence_table.csv").write_text("evidence_id,description,source\nEV-1,demo,synthetic\n", encoding="utf-8")
    (inputs / "historical_run_ledger.csv").write_text("run_id,note\nH1,synthetic\n", encoding="utf-8")
    expected = campaign / "expected"
    expected.mkdir()
    return campaign


def _result_rows() -> list[dict]:
    return [
        {"design_run_id": "D1", "qc_status": "pass", "x1": "2", "x2": "2", "x3": "2", "y": "10"},
        {"design_run_id": "D2", "qc_status": "pass", "x1": "8", "x2": "2", "x3": "2", "y": "30"},
        {"design_run_id": "D3", "qc_status": "pass", "x1": "2", "x2": "8", "x3": "2", "y": "12"},
        {"design_run_id": "D4", "qc_status": "pass", "x1": "8", "x2": "8", "x3": "2", "y": "32"},
        {"design_run_id": "D5", "qc_status": "pass", "x1": "5", "x2": "5", "x3": "8", "y": "25"},
    ]


class ComposeRunPacketTests(unittest.TestCase):
    def test_packet_returns_required_top_level_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["claim_level"], CLAIM_LEVEL)
            self.assertEqual(packet["campaign_id"], "demo-finalize-test")
            for section in ("readiness", "goals", "scale_recipe", "assay_power", "wave1_design", "wave1_results", "wave1_analysis", "wave2_plan", "biosafety"):
                self.assertIn(section, packet)

    def test_goals_section_available_when_objective_bounds_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["goals"]["status"], "AVAILABLE")
            self.assertEqual(len(packet["goals"]["objectives"]), 1)

    def test_scale_recipe_skipped_without_scale_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["scale_recipe"]["status"], "NOT_AVAILABLE")
            self.assertEqual(packet["scale_recipe"]["reason"], "no_scale_context_declared")

    def test_wave1_design_section_renders_preview_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["wave1_design"]["status"], "AVAILABLE")
            self.assertEqual(packet["wave1_design"]["family"], "fractional_factorial")
            self.assertGreater(len(packet["wave1_design"]["preview_rows"]), 0)

    def test_results_and_analysis_run_when_results_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            results = Path(tmp) / "results.csv"
            with results.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["design_run_id", "qc_status", "x1", "x2", "x3", "y"])
                writer.writeheader()
                writer.writerows(_result_rows())
            packet = compose_run_packet(campaign, results_path=results, n_permutations=100, n_bootstrap=50)
            self.assertEqual(packet["wave1_results"]["status"], "AVAILABLE")
            self.assertEqual(packet["wave1_results"]["n_rows"], 5)
            self.assertEqual(packet["wave1_analysis"]["status"], "AVAILABLE")
            self.assertEqual(packet["wave1_analysis"]["response_id"], "y")

    def test_wave1_analysis_skipped_when_results_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["wave1_analysis"]["status"], "NOT_AVAILABLE")

    def test_family_recommendation_section_available_for_screening_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["family_recommendation"]["status"], "AVAILABLE")
            self.assertIsNotNone(packet["family_recommendation"]["recommended_family"])

    def test_sampling_plan_section_available_when_assayed_responses_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["sampling_plan"]["status"], "AVAILABLE")
            self.assertGreater(packet["sampling_plan"]["n_samples"], 0)

    def test_bridge_qualification_skipped_without_arms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["bridge_qualification"]["status"], "NOT_AVAILABLE")
            self.assertEqual(packet["bridge_qualification"]["reason"], "no_arms_declared")

    def test_wave2_plan_picked_up_when_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            wave2_dir = campaign / "wave2"
            wave2_dir.mkdir()
            (wave2_dir / "wave2_recommendation.json").write_text(
                json.dumps({"recommended_action": "narrow", "best_run_id": "D2", "claim_level": "planned_wave2_design"}),
                encoding="utf-8",
            )
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["wave2_plan"]["status"], "AVAILABLE")
            self.assertEqual(packet["wave2_plan"]["recommendation"]["recommended_action"], "narrow")


class BiosafetyTriggerTests(unittest.TestCase):
    def test_recombinant_label_triggers_biosafety_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _manifest()
            manifest["system"]["organism_label"] = "recombinant_e_coli_demo"
            campaign = Path(tmp) / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["biosafety"]["status"], "TRIGGERED")
            self.assertTrue(any("organism_label" in t for t in packet["biosafety"]["triggers"]))

    def test_no_trigger_for_clean_demo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            packet = compose_run_packet(campaign)
            self.assertEqual(packet["biosafety"]["status"], "NOT_TRIGGERED")


class MarkdownRenderingTests(unittest.TestCase):
    def test_markdown_includes_all_section_headers_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            results = Path(tmp) / "results.csv"
            with results.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["design_run_id", "qc_status", "x1", "x2", "x3", "y"])
                writer.writeheader()
                writer.writerows(_result_rows())
            packet = compose_run_packet(campaign, results_path=results, n_permutations=100, n_bootstrap=50)
            md = render_run_packet_markdown(packet)
            self.assertIn("# Run packet", md)
            self.assertIn("## Readiness", md)
            self.assertIn("## Optimization goals", md)
            self.assertIn("## first-batch design", md)
            self.assertIn("## first-batch results", md)
            self.assertIn("## first-batch analysis", md)
            self.assertIn("## Risks", md)


class CliFinalizeTests(unittest.TestCase):
    def test_cli_emits_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = _campaign_dir(Path(tmp))
            md_out = Path(tmp) / "run_packet.md"
            json_out = Path(tmp) / "run_packet.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "finalize",
                    str(campaign), "--out", str(md_out), "--json-out", str(json_out),
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertIn("readiness", summary["sections_available"])
            self.assertTrue(md_out.is_file())
            self.assertTrue(json_out.is_file())


if __name__ == "__main__":
    unittest.main()
