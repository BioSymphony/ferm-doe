from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe import adapters  # noqa: E402


class AdapterRegistryTests(unittest.TestCase):
    def test_get_adapter_unknown_returns_none(self) -> None:
        self.assertIsNone(adapters.get_adapter("not-a-real-adapter"))

    def test_get_adapter_scipy_returns_module_or_none(self) -> None:
        result = adapters.get_adapter("scipy")
        # CI environments may or may not have scipy. Either is valid.
        self.assertIn(result, (None,) if result is None else (result,))
        if result is not None:
            self.assertTrue(hasattr(result, "t_test_two_sided_pvalue"))
            self.assertTrue(hasattr(result, "t_critical"))

    def test_get_adapter_caches_or_reimports_consistently(self) -> None:
        first = adapters.get_adapter("scipy")
        second = adapters.get_adapter("scipy")
        self.assertIs(first, second)

    def test_is_available_matches_get_adapter(self) -> None:
        for name in adapters.ADAPTERS:
            self.assertEqual(adapters.is_available(name), adapters.get_adapter(name) is not None)


@unittest.skipUnless(adapters.is_available("scipy"), "scipy adapter not installed")
class ScipyAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scipy = adapters.get_adapter("scipy")

    def test_t_critical_above_normal_at_small_df(self) -> None:
        # At df=4, t_{0.025} > 1.96 (the normal approx).
        t_crit = self.scipy.t_critical(0.05, df=4)
        self.assertGreater(t_crit, 1.96)

    def test_t_test_pvalue_symmetric_in_sign(self) -> None:
        p_pos = self.scipy.t_test_two_sided_pvalue(2.5, df=10)
        p_neg = self.scipy.t_test_two_sided_pvalue(-2.5, df=10)
        self.assertAlmostEqual(p_pos, p_neg, places=6)

    def test_f_test_pvalue_in_unit_interval(self) -> None:
        p = self.scipy.f_test_pvalue(2.0, 3, 10)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_normal_quantile_round_trip_at_half(self) -> None:
        z = self.scipy.normal_quantile(0.5)
        self.assertAlmostEqual(z, 0.0, places=6)


class AnalysisFallbackTests(unittest.TestCase):
    """Verify analyze still works whether scipy is present or not."""

    def test_analysis_runs_without_scipy(self) -> None:
        from biosymphony_ferm_doe.analysis import analyze_results

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
            ],
            "doe": {"family": "fractional_factorial", "model_terms": ["main_effects"]},
        }
        rows = []
        for i, (a, b) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)] * 2):
            x1 = 1.0 if a == 1 else 0.0
            x2 = 1.0 if b == 1 else 0.0
            rows.append({"design_run_id": f"D{i+1}", "x1": x1, "x2": x2, "y": 5.0 + 2.0 * a + 0.5 * b + 0.1 * (i % 3)})
        with mock.patch.object(adapters, "get_adapter", return_value=None):
            result = analyze_results(manifest, rows, seed=0, n_permutations=50, n_bootstrap=50)
        self.assertFalse(result["scipy_pvalues_used"])
        for coef in result["coefficients"]:
            self.assertNotIn("t_test_p", coef)

    @unittest.skipUnless(adapters.is_available("scipy"), "scipy adapter not installed")
    def test_analysis_includes_t_test_p_when_scipy_present(self) -> None:
        from biosymphony_ferm_doe.analysis import analyze_results

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
            ],
            "doe": {"family": "fractional_factorial", "model_terms": ["main_effects"]},
        }
        rows = []
        for i, (a, b) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)] * 2):
            x1 = 1.0 if a == 1 else 0.0
            x2 = 1.0 if b == 1 else 0.0
            rows.append({"design_run_id": f"D{i+1}", "x1": x1, "x2": x2, "y": 5.0 + 2.0 * a + 0.5 * b + 0.1 * (i % 3)})
        result = analyze_results(manifest, rows, seed=0, n_permutations=50, n_bootstrap=50)
        self.assertTrue(result["scipy_pvalues_used"])
        with_p = [coef for coef in result["coefficients"] if "t_test_p" in coef]
        self.assertGreater(len(with_p), 0)


@unittest.skipUnless(adapters.is_available("botorch"), "BoTorch adapter not installed")
class BoTorchAdapterTests(unittest.TestCase):
    def test_plan_bo_wave2_emits_candidates(self) -> None:
        adapter = adapters.get_adapter("botorch")
        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 10},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 10},
                {"factor_id": "x3", "type": "numeric", "low": 0, "high": 10},
            ],
        }
        # Synthetic surface with optimum near (7, 4, 6) inside [0, 10]^3.
        rows = [
            {"design_run_id": "D1", "x1": 2, "x2": 2, "x3": 2, "y": 5},
            {"design_run_id": "D2", "x1": 8, "x2": 2, "x3": 2, "y": 12},
            {"design_run_id": "D3", "x1": 2, "x2": 8, "x3": 2, "y": 6},
            {"design_run_id": "D4", "x1": 8, "x2": 8, "x3": 2, "y": 10},
            {"design_run_id": "D5", "x1": 5, "x2": 5, "x3": 5, "y": 18},
            {"design_run_id": "D6", "x1": 7, "x2": 4, "x3": 6, "y": 25},
        ]
        plan = adapter.plan_bo_wave2(manifest, rows, n_candidates=3, seed=0, raw_samples=64, num_restarts=4)
        self.assertEqual(plan["claim_level"], "bayesian_optimization_planned")
        self.assertEqual(plan["n_candidates"], 3)
        self.assertEqual(len(plan["candidate_design"]), 3)
        for row in plan["candidate_design"]:
            self.assertEqual(row["scoring_mode"], "bayesian_optimization")
            for fid in ("x1", "x2", "x3"):
                self.assertIn(fid, row)

    def test_short_circuits_below_min_observations(self) -> None:
        adapter = adapters.get_adapter("botorch")
        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize"}],
            "factors": [{"factor_id": "x1", "type": "numeric", "low": 0, "high": 1}],
        }
        rows = [{"design_run_id": "D1", "x1": 0.5, "y": 1.0}]
        plan = adapter.plan_bo_wave2(manifest, rows, n_candidates=2, seed=0)
        self.assertIn("short_circuit_reason", plan)


@unittest.skipUnless(adapters.is_available("pydoe3"), "pyDOE3 adapter not installed")
class PyDoE3AdapterTests(unittest.TestCase):
    def test_box_behnken_k5_produces_design_via_pydoe3(self) -> None:
        from biosymphony_ferm_doe.doe_generators import generate_design

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize"}],
            "factors": [
                {"factor_id": f"x{i}", "type": "numeric", "low": 0, "high": 10}
                for i in range(1, 6)
            ],
            "doe": {"family": "box_behnken", "model_terms": ["main_effects", "quadratic"], "randomized": False},
        }
        design = generate_design(manifest, seed=0)
        self.assertEqual(design["family"], "box_behnken")
        self.assertEqual(design["metadata"].get("backend"), "pydoe3")
        self.assertGreater(design["n_runs"], 0)

    def test_lhs_maximin_via_pydoe3(self) -> None:
        from biosymphony_ferm_doe.doe_generators import generate_design

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize"}],
            "factors": [
                {"factor_id": f"x{i}", "type": "numeric", "low": 0, "high": 10}
                for i in range(1, 4)
            ],
            "doe": {"family": "latin_hypercube", "n_runs": 12, "criterion": "maximin", "randomized": False},
        }
        design = generate_design(manifest, seed=0)
        self.assertEqual(design["metadata"]["backend"], "pydoe3")
        self.assertEqual(design["n_runs"], 12)


class DoePowerCriticalBasisTests(unittest.TestCase):
    def test_critical_basis_normal_when_no_scipy(self) -> None:
        from biosymphony_ferm_doe.doe_power import compute_doe_power

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x3", "type": "numeric", "low": 0, "high": 1},
            ],
            "doe": {"family": "central_composite", "model_terms": ["main_effects"], "n_center_points": 4, "randomized": False},
        }
        with mock.patch.object(adapters, "get_adapter", return_value=None):
            result = compute_doe_power(manifest, sigma=1.0, alpha=0.05, target_power=0.8)
        self.assertEqual(result["critical_basis"], "normal_approximation")
        # Normal approx gives mde_factor ~= 1.96 + 0.84 = 2.80
        self.assertAlmostEqual(result["mde_multiplier"], 2.80, places=1)

    @unittest.skipUnless(adapters.is_available("scipy"), "scipy adapter not installed")
    def test_critical_basis_t_distribution_when_scipy_present(self) -> None:
        from biosymphony_ferm_doe.doe_power import compute_doe_power

        manifest = {
            "campaign_id": "demo",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
                {"factor_id": "x3", "type": "numeric", "low": 0, "high": 1},
            ],
            "doe": {"family": "central_composite", "model_terms": ["main_effects"], "n_center_points": 4, "randomized": False},
        }
        result = compute_doe_power(manifest, sigma=1.0, alpha=0.05, target_power=0.8)
        self.assertEqual(result["critical_basis"], "student_t")
        # Student-t at small df has critical > 1.96, so MDE multiplier should be > 2.80.
        self.assertGreater(result["mde_multiplier"], 2.80)


if __name__ == "__main__":
    unittest.main()
