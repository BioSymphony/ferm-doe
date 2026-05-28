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

from biosymphony_ferm_doe.sampling import (  # noqa: E402
    CLAIM_LEVEL,
    compute_sampling_plan,
    render_sampling_markdown,
)


def _manifest(*, sampling_policy: dict | None = None, responses: list[dict] | None = None) -> dict:
    base_responses = responses or [
        {"response_id": "titer_g_l", "class": "titer", "direction": "maximize", "assay_required": True, "measurement_type": "assayed"},
        {"response_id": "biomass_od600", "class": "biomass", "direction": "maximize", "measurement_type": "instrument"},
        {"response_id": "run_cost_usd", "class": "cost", "direction": "minimize", "measurement_type": "derived"},
    ]
    out = {
        "campaign_id": "demo-sampling-test",
        "claim_level": "public_synthetic_demo",
        "responses": base_responses,
        "factors": [{"factor_id": "x", "type": "numeric", "low": 0, "high": 1}],
    }
    if sampling_policy:
        out["sampling_policy"] = sampling_policy
    return out


class DefaultPolicyTests(unittest.TestCase):
    def test_default_48h_run_emits_schedule_for_assayed_and_instrument(self) -> None:
        plan = compute_sampling_plan(_manifest())
        self.assertEqual(plan["claim_level"], CLAIM_LEVEL)
        self.assertEqual(plan["run_duration_h"], 48.0)
        rids = {sample["response_id"] for sample in plan["samples"]}
        self.assertEqual(rids, {"titer_g_l", "biomass_od600"})
        self.assertNotIn("run_cost_usd", rids)

    def test_default_frequency_4h_produces_expected_count(self) -> None:
        plan = compute_sampling_plan(_manifest())
        per_response = plan["totals"]["samples_per_response"]
        # 48h - 4h = 44h window, freq 4h -> samples at 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48 = 12 each
        self.assertEqual(per_response["titer_g_l"], 12)
        self.assertEqual(per_response["biomass_od600"], 12)
        self.assertEqual(plan["totals"]["n_samples"], 24)

    def test_phases_assigned_to_samples(self) -> None:
        plan = compute_sampling_plan(_manifest())
        phases = {sample["phase"] for sample in plan["samples"]}
        self.assertIn("active", phases)


class CustomPolicyTests(unittest.TestCase):
    def test_explicit_policy_overrides_defaults(self) -> None:
        policy = {
            "run_duration_h": 24,
            "phases": [
                {"name": "lag", "start_h": 0, "end_h": 4},
                {"name": "active", "start_h": 4, "end_h": 24},
            ],
            "responses": [
                {"response_id": "titer_g_l", "frequency_h": 6, "active_window_h": [6, 24], "sample_volume_ml": 2.0}
            ],
        }
        plan = compute_sampling_plan(_manifest(sampling_policy=policy))
        self.assertEqual(plan["run_duration_h"], 24)
        # samples at 6, 12, 18, 24 → 4 samples
        titer_samples = [s for s in plan["samples"] if s["response_id"] == "titer_g_l"]
        self.assertEqual(len(titer_samples), 4)
        self.assertEqual(titer_samples[0]["sample_volume_ml"], 2.0)
        # titer: 4 samples * 2mL = 8mL.
        # biomass: default freq=4h over (4, 24) -> t=4,8,12,16,20,24 = 6 samples * 1mL = 6mL.
        self.assertEqual(plan["totals"]["total_volume_ml"], 14.0)

    def test_zero_frequency_warns_and_skips(self) -> None:
        policy = {
            "responses": [
                {"response_id": "titer_g_l", "frequency_h": 0, "active_window_h": [4, 48], "sample_volume_ml": 1.0}
            ],
        }
        plan = compute_sampling_plan(_manifest(sampling_policy=policy))
        self.assertTrue(any("frequency_h_must_be_positive" in w for w in plan["warnings"]))
        rids = {s["response_id"] for s in plan["samples"]}
        self.assertNotIn("titer_g_l", rids)


class TotalsTests(unittest.TestCase):
    def test_totals_aggregate_correctly(self) -> None:
        plan = compute_sampling_plan(_manifest())
        totals = plan["totals"]
        self.assertEqual(totals["n_samples"], sum(totals["samples_per_response"].values()))
        self.assertAlmostEqual(totals["total_volume_ml"], totals["n_samples"] * 1.0)


class MarkdownTests(unittest.TestCase):
    def test_markdown_renders_first_20_samples(self) -> None:
        plan = compute_sampling_plan(_manifest())
        md = render_sampling_markdown(plan)
        self.assertIn("# Sampling plan", md)
        self.assertIn("Total samples", md)
        self.assertIn("Schedule preview", md)


class CliSamplingPlanTests(unittest.TestCase):
    def test_cli_emits_csv_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(json.dumps(_manifest()), encoding="utf-8")
            csv_out = root / "sampling.csv"
            md_out = root / "sampling.md"
            json_out = root / "sampling.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "sampling-plan",
                    str(campaign), "--out", str(csv_out), "--md-out", str(md_out),
                    "--json-out", str(json_out),
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["run_duration_h"], 48.0)
            self.assertGreater(summary["n_samples"], 0)
            with csv_out.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), summary["n_samples"])
            self.assertTrue(md_out.is_file())
            self.assertTrue(json_out.is_file())


if __name__ == "__main__":
    unittest.main()
