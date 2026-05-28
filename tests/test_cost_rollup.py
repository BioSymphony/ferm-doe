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

from biosymphony_ferm_doe.cost_rollup import (  # noqa: E402
    CLAIM_LEVEL,
    compute_cost_rollup,
    render_cost_rollup_markdown,
)


def _manifest(*, resource_costs: dict | None = None, sampling_policy: dict | None = None) -> dict:
    out = {
        "campaign_id": "demo-cost-test",
        "claim_level": "public_synthetic_demo",
        "responses": [
            {"response_id": "y", "direction": "maximize", "assay_required": True, "measurement_type": "assayed"}
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
            {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
            {"factor_id": "x3", "type": "numeric", "low": 0, "high": 1},
        ],
        "doe": {"family": "fractional_factorial", "n_runs": 8, "model_terms": ["main_effects"], "randomized": False},
    }
    if resource_costs:
        out["resource_costs"] = resource_costs
    if sampling_policy:
        out["sampling_policy"] = sampling_policy
    return out


class ComputeCostRollupTests(unittest.TestCase):
    def test_no_unit_costs_emits_zero_total_with_warning(self) -> None:
        rollup = compute_cost_rollup(_manifest())
        self.assertEqual(rollup["claim_level"], CLAIM_LEVEL)
        self.assertEqual(rollup["campaign_total"], 0.0)
        self.assertTrue(any("no_unit_costs_declared" in w for w in rollup["warnings"]))

    def test_per_run_cost_multiplies_correctly(self) -> None:
        rollup = compute_cost_rollup(_manifest(resource_costs={"per_run_cost": 100.0}))
        self.assertEqual(rollup["wave1_n_runs"], 8)
        self.assertEqual(rollup["wave1_total"], 800.0)

    def test_sample_and_volume_costs_aggregate(self) -> None:
        rollup = compute_cost_rollup(
            _manifest(
                resource_costs={
                    "per_run_cost": 100.0,
                    "per_sample_cost": 5.0,
                    "per_volume_ml_cost": 0.5,
                }
            )
        )
        # 8 runs * $100 + n_samples * $5 + total_volume_ml * $0.50
        # samples come from default sampling plan: 1 assayed response * 12 samples = 12
        self.assertGreater(rollup["wave1_total"], 800.0)

    def test_wave2_estimate_adds_to_campaign_total(self) -> None:
        rollup = compute_cost_rollup(
            _manifest(resource_costs={"per_run_cost": 100.0, "wave2_runs_estimate": 3})
        )
        self.assertEqual(rollup["wave1_total"], 800.0)
        self.assertEqual(rollup["wave2_total"], 300.0)
        self.assertEqual(rollup["campaign_total"], 1100.0)

    def test_cli_flags_override_manifest_costs(self) -> None:
        rollup = compute_cost_rollup(
            _manifest(resource_costs={"per_run_cost": 100.0}),
            per_run_cost=200.0,
        )
        self.assertEqual(rollup["wave1_total"], 1600.0)

    def test_run_duration_cost_uses_sampling_policy_duration(self) -> None:
        rollup = compute_cost_rollup(
            _manifest(
                resource_costs={"per_run_duration_h_cost": 10.0},
                sampling_policy={"run_duration_h": 24, "responses": []},
            )
        )
        # 8 runs * 24 h * $10 = $1920
        self.assertEqual(rollup["wave1_total"], 1920.0)

    def test_currency_propagates(self) -> None:
        rollup = compute_cost_rollup(_manifest(resource_costs={"currency": "EUR", "per_run_cost": 50.0}))
        self.assertEqual(rollup["currency"], "EUR")

    def test_breakdown_has_six_line_items(self) -> None:
        rollup = compute_cost_rollup(_manifest())
        line_items = [item["line_item"] for item in rollup["breakdown"]]
        for expected in ("wave1_runs", "wave1_run_duration", "samples", "sample_volume_ml", "wave2_runs_estimate", "wave2_run_duration_estimate"):
            self.assertIn(expected, line_items)


class MarkdownTests(unittest.TestCase):
    def test_markdown_renders_subtotals(self) -> None:
        rollup = compute_cost_rollup(_manifest(resource_costs={"per_run_cost": 100.0, "wave2_runs_estimate": 3}))
        md = render_cost_rollup_markdown(rollup)
        self.assertIn("Cost rollup", md)
        self.assertIn("first-batch subtotal", md)
        self.assertIn("follow-up subtotal", md)
        self.assertIn("Campaign total", md)


class CliCostRollupTests(unittest.TestCase):
    def test_cli_emits_summary_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(
                json.dumps(_manifest(resource_costs={"per_run_cost": 100.0, "wave2_runs_estimate": 3})),
                encoding="utf-8",
            )
            out = root / "cost.json"
            md_out = root / "cost.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "cost-rollup",
                    str(campaign), "--out", str(out), "--md-out", str(md_out),
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["campaign_total"], 1100.0)
            self.assertTrue(out.is_file())
            self.assertTrue(md_out.is_file())


if __name__ == "__main__":
    unittest.main()
