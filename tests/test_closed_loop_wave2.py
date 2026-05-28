from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.adaptive import (  # noqa: E402
    _generate_augment_rows,
    plan_wave2,
)


def _manifest() -> dict:
    return {
        "campaign_id": "demo-closed-loop-test",
        "claim_level": "public_synthetic_demo",
        "system": {"privacy": "synthetic_or_public_only"},
        "responses": [
            {"response_id": "y", "class": "titer", "direction": "maximize", "assay_required": True},
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0.0, "high": 10.0},
            {"factor_id": "x2", "type": "numeric", "low": 0.0, "high": 10.0},
        ],
        "doe": {"family": "fractional_factorial", "model_terms": ["main_effects"]},
        "adaptive_wave2": {"primary_response_id": "y"},
    }


def _result_rows() -> list[dict]:
    return [
        {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
         "x1": "2", "x2": "2", "y": "10"},
        {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
         "x1": "8", "x2": "2", "y": "30"},
        {"design_run_id": "D3", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
         "x1": "2", "x2": "8", "y": "12"},
        {"design_run_id": "D4", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
         "x1": "8", "x2": "8", "y": "32"},
    ]


class GenerateAugmentRowsClosedLoopTests(unittest.TestCase):
    def test_legacy_path_when_no_signal(self) -> None:
        manifest = _manifest()
        recommendation = {
            "recommended_action": "narrow",
            "best_run_id": "D2",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        rows = _result_rows()
        augment = _generate_augment_rows(manifest, recommendation, rows, 3)
        self.assertEqual(len(augment), 3)
        self.assertNotIn("scoring_mode", augment[0])
        # Legacy: symmetric narrow around best (x1=8, x2=2). Step is 10% of range = 1.0.
        self.assertAlmostEqual(augment[0]["x1"], 7.0, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 9.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 6.0, places=4)

    def test_signal_active_factor_narrow_biased_toward_ascent(self) -> None:
        manifest = _manifest()
        # _best_row_for_recommendation picks D4 (y=32, the max).
        recommendation = {
            "recommended_action": "narrow",
            "best_run_id": "D4",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        rows = _result_rows()
        signal = {
            "active_factor_ids": ["x1"],
            "per_factor": [
                {"factor_id": "x1", "main_effect": 5.0, "ascent_sign": 1, "active": True},
                {"factor_id": "x2", "main_effect": 0.1, "ascent_sign": 1, "active": False},
            ],
        }
        augment = _generate_augment_rows(manifest, recommendation, rows, 3, wave2_signal=signal)
        self.assertEqual(augment[0]["scoring_mode"], "model_informed")
        # Active x1 (ascent_sign=+1) shifts toward upper bound from best=8.0 (D4);
        # informed step = 5% of (10-0) = 0.5; multipliers (1, 2, 3); upper bound clamps at 10.
        self.assertAlmostEqual(augment[0]["x1"], 8.5, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 9.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 9.5, places=4)
        # Inactive x2 holds at best (D4) value = 8.0
        for row in augment:
            self.assertAlmostEqual(row["x2"], 8.0, places=4)

    def test_signal_active_factor_negative_ascent_narrows_downward(self) -> None:
        manifest = _manifest()
        recommendation = {
            "recommended_action": "narrow",
            "best_run_id": "D1",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "2", "x2": "5", "y": "30"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "8", "x2": "5", "y": "10"},
        ]
        signal = {
            "active_factor_ids": ["x1"],
            "per_factor": [
                {"factor_id": "x1", "main_effect": -10.0, "ascent_sign": -1, "active": True},
            ],
        }
        augment = _generate_augment_rows(manifest, recommendation, rows, 3, wave2_signal=signal)
        # x1 best = 2.0, ascent_sign = -1, step = 0.5 -> rows shift downward, clamped at low=0.
        self.assertAlmostEqual(augment[0]["x1"], 1.5, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 1.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 0.5, places=4)

    def test_signal_expand_pushes_past_boundary_in_ascent_direction(self) -> None:
        manifest = _manifest()
        recommendation = {
            "recommended_action": "expand",
            "best_run_id": "D2",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        rows = _result_rows()
        signal = {
            "active_factor_ids": ["x1"],
            "per_factor": [
                {"factor_id": "x1", "main_effect": 5.0, "ascent_sign": 1, "active": True},
                {"factor_id": "x2", "main_effect": 0.1, "ascent_sign": 1, "active": False},
            ],
        }
        augment = _generate_augment_rows(manifest, recommendation, rows, 3, wave2_signal=signal)
        # Active x1 expands past upper boundary 10.0. step = 0.1 * 10 = 1.0; multipliers (1, 2, 3).
        self.assertAlmostEqual(augment[0]["x1"], 11.0, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 12.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 13.0, places=4)
        # Inactive x2 held at midpoint 5.0
        for row in augment:
            self.assertAlmostEqual(row["x2"], 5.0, places=4)


class PlanFollowUpClosedLoopIntegrationTests(unittest.TestCase):
    def test_plan_wave2_emits_wave1_analysis_when_enough_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest()
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            results = root / "results.csv"
            with results.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["design_run_id", "qc_status", "inclusion_status", "trust_score", "x1", "x2", "y"],
                )
                writer.writeheader()
                writer.writerows(_result_rows())
            out_dir = root / "wave2"
            plan = plan_wave2(campaign, results, out_dir)
            self.assertIn("wave1_analysis.json", plan["artifacts"])
            self.assertTrue((out_dir / "wave1_analysis.json").is_file())
            analysis = json.loads((out_dir / "wave1_analysis.json").read_text())
            self.assertEqual(analysis["claim_level"], "wave1_analysis_planned")

    def test_plan_wave2_augment_rows_use_signal_when_active_factor_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest()
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            results = root / "results.csv"
            with results.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["design_run_id", "qc_status", "inclusion_status", "trust_score", "x1", "x2", "y"],
                )
                writer.writeheader()
                writer.writerows(_result_rows())
            out_dir = root / "wave2"
            plan_wave2(campaign, results, out_dir)
            augment_csv = (out_dir / "augment_design.csv").read_text()
            # When the analysis succeeds and signal is used, scoring_mode appears in the row.
            # Rows produced by closed-loop path will mention model_informed; legacy fallback won't.
            self.assertIn("model_informed", augment_csv)


if __name__ == "__main__":
    unittest.main()
