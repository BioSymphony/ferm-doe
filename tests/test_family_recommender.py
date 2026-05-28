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

from biosymphony_ferm_doe.family_recommender import (  # noqa: E402
    CLAIM_LEVEL,
    recommend_family,
)


def _manifest(factors: list[dict], *, profiles: list[str] | None = None) -> dict:
    return {
        "campaign_id": "demo-rec-test",
        "claim_level": "public_synthetic_demo",
        "profiles": profiles or [],
        "factors": factors,
        "responses": [{"response_id": "y", "direction": "maximize"}],
    }


def _numeric(n: int, *, prefix: str = "x") -> list[dict]:
    return [{"factor_id": f"{prefix}{i}", "type": "numeric", "low": 0.0, "high": 1.0} for i in range(1, n + 1)]


class MixturePathTests(unittest.TestCase):
    def test_unconstrained_mixture_picks_scheffe(self) -> None:
        factors = [
            {"factor_id": "c1", "type": "mixture", "low": 0.0, "high": 1.0},
            {"factor_id": "c2", "type": "mixture", "low": 0.0, "high": 1.0},
            {"factor_id": "c3", "type": "mixture", "low": 0.0, "high": 1.0},
        ]
        result = recommend_family(_manifest(factors))
        self.assertEqual(result["claim_level"], CLAIM_LEVEL)
        self.assertEqual(result["recommended_family"], "scheffe_mixture")
        self.assertEqual(result["candidates"][1]["family"], "extreme_vertices_mixture")
        self.assertIn("mixture_factors_present", result["decision_path"])

    def test_constrained_mixture_picks_extreme_vertices(self) -> None:
        factors = [
            {"factor_id": "c1", "type": "mixture", "low": 0.1, "high": 0.6},
            {"factor_id": "c2", "type": "mixture", "low": 0.2, "high": 0.7},
            {"factor_id": "c3", "type": "mixture", "low": 0.1, "high": 0.5},
        ]
        result = recommend_family(_manifest(factors))
        self.assertEqual(result["recommended_family"], "extreme_vertices_mixture")
        self.assertIn("constrained_components_detected", result["decision_path"])


class SplitPlotPathTests(unittest.TestCase):
    def test_hard_to_change_factor_recommends_split_plot(self) -> None:
        factors = [
            {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1, "hard_to_change": True},
            {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
            {"factor_id": "x3", "type": "numeric", "low": 0, "high": 1},
        ]
        result = recommend_family(_manifest(factors, profiles=["split_plot_fed_batch"]))
        self.assertEqual(result["recommended_family"], "split_plot")


class ScreeningMainPathTests(unittest.TestCase):
    def test_small_k_picks_full_factorial(self) -> None:
        result = recommend_family(_manifest(_numeric(3), profiles=["screening"]))
        self.assertEqual(result["recommended_family"], "full_factorial")

    def test_curvature_prior_yes_at_k4_picks_dsd(self) -> None:
        result = recommend_family(_manifest(_numeric(4), profiles=["screening"]), curvature_prior="yes")
        self.assertEqual(result["recommended_family"], "definitive_screening")

    def test_many_factors_picks_plackett_burman(self) -> None:
        result = recommend_family(_manifest(_numeric(10), profiles=["screening"]))
        self.assertEqual(result["recommended_family"], "plackett_burman")

    def test_interactions_prior_yes_at_moderate_k_picks_fractional(self) -> None:
        result = recommend_family(_manifest(_numeric(5), profiles=["screening"]), interactions_prior="yes")
        self.assertEqual(result["recommended_family"], "fractional_factorial")

    def test_default_screening_falls_back_to_pb(self) -> None:
        result = recommend_family(_manifest(_numeric(6), profiles=["screening"]))
        self.assertEqual(result["recommended_family"], "plackett_burman")


class OptimizationPathTests(unittest.TestCase):
    def test_small_k_optimization_picks_ccd(self) -> None:
        result = recommend_family(_manifest(_numeric(4), profiles=["optimization_rsm"]))
        self.assertEqual(result["recommended_family"], "central_composite")
        alternative_families = [c["family"] for c in result["candidates"]]
        self.assertIn("box_behnken", alternative_families)

    def test_large_k_optimization_picks_optimal_d(self) -> None:
        result = recommend_family(_manifest(_numeric(7), profiles=["optimization_rsm"]))
        self.assertEqual(result["recommended_family"], "optimal_d")


class ScaleBridgePathTests(unittest.TestCase):
    def test_scale_bridge_recommends_confirmation_plus_seq_aug(self) -> None:
        result = recommend_family(_manifest(_numeric(3), profiles=["scale_down_qualification"]))
        self.assertEqual(result["recommended_family"], "confirmation")
        self.assertIn("sequential_augmentation", [c["family"] for c in result["candidates"]])


class BudgetFilterTests(unittest.TestCase):
    def test_budget_drops_too_large_candidates(self) -> None:
        # 7 factors, full_factorial would be 2^7=128 (too large), but we don't expect
        # full_factorial here — we expect plackett_burman (8 runs) which fits a budget of 12.
        result = recommend_family(_manifest(_numeric(7), profiles=["screening"]), budget=12)
        for cand in result["candidates"]:
            runs = cand["expected_runs"]
            if isinstance(runs, str) and runs.lstrip("~").isdigit():
                self.assertLessEqual(int(runs.lstrip("~")), 12)

    def test_budget_too_small_keeps_originals_with_drop_record(self) -> None:
        result = recommend_family(_manifest(_numeric(10), profiles=["screening"]), budget=4)
        self.assertGreater(len(result["candidates"]), 0)
        self.assertTrue(any(item.startswith("budget_drops=") for item in result["decision_path"]))


class NistCitationTests(unittest.TestCase):
    def test_recommended_candidate_carries_nist_reference(self) -> None:
        result = recommend_family(_manifest(_numeric(7), profiles=["screening"]))
        candidate = result["candidates"][0]
        self.assertIn("reference", candidate)
        self.assertIn("url", candidate["reference"])
        self.assertEqual(candidate["family"], "plackett_burman")
        self.assertIn("nist.gov", candidate["reference"]["url"])

    def test_post_handbook_design_cites_primary_literature(self) -> None:
        result = recommend_family(_manifest(_numeric(4), profiles=["screening"]), curvature_prior="yes")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["family"], "definitive_screening")
        self.assertIsNone(candidate["reference"]["section"])
        self.assertIn("Jones", candidate["reference"]["title"])


class CliRecommendFamilyTests(unittest.TestCase):
    def test_cli_emits_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest(_numeric(7), profiles=["screening"])
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [sys.executable, "-m", "biosymphony_ferm_doe.cli", "recommend-family", str(campaign)],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["claim_level"], CLAIM_LEVEL)
            self.assertIsNotNone(payload["recommended_family"])

    def test_cli_writes_out_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest(_numeric(3), profiles=["screening"])
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            out = root / "rec.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            subprocess.run(
                [sys.executable, "-m", "biosymphony_ferm_doe.cli", "recommend-family", str(campaign), "--out", str(out)],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            self.assertTrue(out.is_file())
            self.assertEqual(json.loads(out.read_text())["recommended_family"], "full_factorial")


if __name__ == "__main__":
    unittest.main()
