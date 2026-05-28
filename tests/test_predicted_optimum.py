from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.adaptive import _generate_augment_rows  # noqa: E402
from biosymphony_ferm_doe.analysis import analyze_results  # noqa: E402


def _quadratic_manifest() -> dict:
    return {
        "campaign_id": "demo-pred-opt-test",
        "claim_level": "public_synthetic_demo",
        "responses": [
            {"response_id": "y", "class": "titer", "direction": "maximize", "assay_required": True}
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0.0, "high": 10.0},
            {"factor_id": "x2", "type": "numeric", "low": 0.0, "high": 10.0},
        ],
        "doe": {
            "family": "central_composite",
            "model_terms": ["main_effects", "two_factor_interactions", "quadratic"],
        },
        "adaptive_wave2": {"primary_response_id": "y"},
    }


def _ccd_rows_with_known_optimum() -> list[dict]:
    """Synthetic CCD rows with a known optimum at x1=6.0, x2=4.0 (engineering units)."""
    factor_levels = []
    for x1_coded in (-1, 1):
        for x2_coded in (-1, 1):
            factor_levels.append((x1_coded, x2_coded))
    for x1_coded, x2_coded in [(-1.4142, 0), (1.4142, 0), (0, -1.4142), (0, 1.4142)]:
        factor_levels.append((x1_coded, x2_coded))
    factor_levels.extend([(0, 0)] * 5)

    rows = []
    for index, (x1c, x2c) in enumerate(factor_levels):
        x1 = 5.0 + 5.0 * x1c
        x2 = 5.0 + 5.0 * x2c
        # True surface: y = 50 - (x1 - 6)^2 - (x2 - 4)^2 (peak at x1=6, x2=4).
        y = 50.0 - (x1 - 6.0) ** 2 - (x2 - 4.0) ** 2
        rows.append(
            {
                "design_run_id": f"D{index+1}",
                "qc_status": "pass",
                "inclusion_status": "include",
                "trust_score": "0.95",
                "x1": x1,
                "x2": x2,
                "y": y,
            }
        )
    return rows


class PredictedOptimumComputationTests(unittest.TestCase):
    def test_optimum_recovered_within_factor_range(self) -> None:
        manifest = _quadratic_manifest()
        rows = _ccd_rows_with_known_optimum()
        analysis = analyze_results(manifest, rows, seed=0, n_permutations=200, n_bootstrap=100)
        signal = analysis["wave2_signal"]
        optimum = signal["predicted_optimum"]
        self.assertIsNotNone(optimum)
        self.assertEqual(optimum["kind"], "stationary_point")
        self.assertTrue(optimum["interior_to_factor_ranges"])
        engineering = optimum["engineering_units"]
        self.assertAlmostEqual(engineering["x1"], 6.0, places=2)
        self.assertAlmostEqual(engineering["x2"], 4.0, places=2)

    def test_no_curvature_returns_none(self) -> None:
        manifest = _quadratic_manifest()
        manifest["doe"]["model_terms"] = ["main_effects"]
        rows = _ccd_rows_with_known_optimum()
        analysis = analyze_results(manifest, rows, seed=0, n_permutations=100, n_bootstrap=50)
        self.assertIsNone(analysis["wave2_signal"]["predicted_optimum"])

    def test_exterior_optimum_flagged(self) -> None:
        manifest = _quadratic_manifest()
        rows = _ccd_rows_with_known_optimum()
        # Shift the response surface so the peak lies way outside the factor ranges.
        for row in rows:
            row["y"] = float(row["y"]) + 100.0 * float(row["x1"])  # adds linear pull, peak shoots beyond +1
        analysis = analyze_results(manifest, rows, seed=0, n_permutations=100, n_bootstrap=50)
        optimum = analysis["wave2_signal"]["predicted_optimum"]
        self.assertIsNotNone(optimum)
        self.assertFalse(optimum["interior_to_factor_ranges"])


class PredictedOptimumDrivesAugmentRowsTests(unittest.TestCase):
    def test_narrow_rows_interpolate_toward_predicted_optimum(self) -> None:
        manifest = _quadratic_manifest()
        # best_row at corner x1=10, x2=10. Predicted optimum at x1=6, x2=4 (interior).
        rows = [
            {"design_run_id": "B", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "10", "x2": "10", "y": "20"},
            {"design_run_id": "C", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "5", "x2": "5", "y": "5"},
        ]
        recommendation = {
            "recommended_action": "narrow",
            "best_run_id": "B",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        signal = {
            "active_factor_ids": ["x1", "x2"],
            "per_factor": [
                {"factor_id": "x1", "main_effect": 5.0, "ascent_sign": 1, "active": True},
                {"factor_id": "x2", "main_effect": 5.0, "ascent_sign": 1, "active": True},
            ],
            "predicted_optimum": {
                "kind": "stationary_point",
                "coded": {"x1": 0.2, "x2": -0.2},
                "engineering_units": {"x1": 6.0, "x2": 4.0},
                "interior_to_factor_ranges": True,
                "warnings": [],
            },
        }
        augment = _generate_augment_rows(manifest, recommendation, rows, 3, wave2_signal=signal)
        self.assertEqual(augment[0]["scoring_mode"], "model_informed_optimum")
        # Best is x1=10; predicted opt is 6. Fractions 0.25, 0.5, 0.75 → values 9, 8, 7.
        self.assertAlmostEqual(augment[0]["x1"], 9.0, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 8.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 7.0, places=4)
        # Best is x2=10; predicted opt is 4. Fractions 0.25, 0.5, 0.75 → values 8.5, 7, 5.5.
        self.assertAlmostEqual(augment[0]["x2"], 8.5, places=4)
        self.assertAlmostEqual(augment[1]["x2"], 7.0, places=4)
        self.assertAlmostEqual(augment[2]["x2"], 5.5, places=4)

    def test_exterior_optimum_falls_back_to_ascent_path(self) -> None:
        manifest = _quadratic_manifest()
        rows = [
            {"design_run_id": "B", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "8", "x2": "8", "y": "20"},
            {"design_run_id": "C", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "x1": "5", "x2": "5", "y": "5"},
        ]
        recommendation = {
            "recommended_action": "narrow",
            "best_run_id": "B",
            "best_arm_id": "",
            "primary_response_id": "y",
        }
        signal = {
            "active_factor_ids": ["x1"],
            "per_factor": [
                {"factor_id": "x1", "main_effect": 5.0, "ascent_sign": 1, "active": True},
                {"factor_id": "x2", "main_effect": 0.05, "ascent_sign": 1, "active": False},
            ],
            "predicted_optimum": {
                "kind": "stationary_point",
                "coded": {"x1": 5.0, "x2": -3.0},
                "engineering_units": {"x1": 30.0, "x2": -10.0},
                "interior_to_factor_ranges": False,
                "warnings": ["stationary_point_outside_declared_factor_ranges"],
            },
        }
        augment = _generate_augment_rows(manifest, recommendation, rows, 3, wave2_signal=signal)
        # Falls back to ascent-direction logic. Step = 5% of 10 = 0.5; x1=8 + (1, 2, 3)*0.5 = 8.5, 9.0, 9.5.
        self.assertEqual(augment[0]["scoring_mode"], "model_informed")
        self.assertAlmostEqual(augment[0]["x1"], 8.5, places=4)
        self.assertAlmostEqual(augment[1]["x1"], 9.0, places=4)
        self.assertAlmostEqual(augment[2]["x1"], 9.5, places=4)


if __name__ == "__main__":
    unittest.main()
