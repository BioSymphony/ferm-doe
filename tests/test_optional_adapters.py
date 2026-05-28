from __future__ import annotations

import json
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe import adapters  # noqa: E402
from biosymphony_ferm_doe.adapters import bofire_strategy  # noqa: E402
from biosymphony_ferm_doe.analysis import analyze_results  # noqa: E402
from biosymphony_ferm_doe.doe_power import compute_doe_power  # noqa: E402


class AdapterRegistryTests(unittest.TestCase):
    def test_unknown_adapter_returns_none(self) -> None:
        self.assertIsNone(adapters.get_adapter("not-a-real-adapter"))

    def test_known_adapter_registry_is_lazy(self) -> None:
        for name in adapters.ADAPTERS:
            result = adapters.get_adapter(name)
            self.assertEqual(adapters.is_available(name), result is not None)


class FakeScipyAdapter:
    @staticmethod
    def t_test_two_sided_pvalue(t_stat: float, df: int) -> float:
        return 0.123456

    @staticmethod
    def t_critical(alpha: float, df: int) -> float:
        return 3.0

    @staticmethod
    def normal_quantile(p: float) -> float:
        return 0.84


def _manifest() -> dict:
    return {
        "campaign_id": "adapter-smoke",
        "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True}],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0, "high": 1},
            {"factor_id": "x2", "type": "numeric", "low": 0, "high": 1},
        ],
        "doe": {"family": "full_factorial", "model_terms": ["main_effects"], "randomized": False},
    }


class OptionalAdapterUseTests(unittest.TestCase):
    def test_analysis_uses_scipy_adapter_when_present(self) -> None:
        rows = [
            {"design_run_id": "D1", "x1": 0, "x2": 0, "y": 1.0},
            {"design_run_id": "D2", "x1": 1, "x2": 0, "y": 4.0},
            {"design_run_id": "D3", "x1": 0, "x2": 1, "y": 2.0},
            {"design_run_id": "D4", "x1": 1, "x2": 1, "y": 5.0},
            {"design_run_id": "D5", "x1": 0.5, "x2": 0.5, "y": 3.2},
        ]
        with mock.patch.object(adapters, "get_adapter", return_value=FakeScipyAdapter):
            result = analyze_results(_manifest(), rows, n_permutations=20, n_bootstrap=20, seed=0)
        self.assertTrue(result["scipy_pvalues_used"])
        self.assertTrue(any("t_test_p" in coef for coef in result["coefficients"]))

    def test_doe_power_uses_student_t_basis_when_adapter_present(self) -> None:
        with mock.patch.object(adapters, "get_adapter", return_value=FakeScipyAdapter):
            result = compute_doe_power(_manifest(), sigma=1.0)
        self.assertEqual(result["critical_basis"], "student_t")
        self.assertAlmostEqual(result["mde_multiplier"], 3.84, places=2)

    def test_doe_power_falls_back_without_adapter(self) -> None:
        with mock.patch.object(adapters, "get_adapter", return_value=None):
            result = compute_doe_power(_manifest(), sigma=1.0)
        self.assertEqual(result["critical_basis"], "normal_approximation")


def _bofire_state(**overrides: object) -> dict[str, object]:
    state: dict[str, object] = {
        "campaign_id": "bofire-route-smoke",
        "responses": [{"response_id": "titer", "direction": "maximize", "unit": "g/L"}],
        "objective": {"response_id": "titer", "direction": "maximize"},
        "factors": [
            {"factor_id": "glucose", "type": "continuous", "min": 0, "max": 50, "allow_zero": True},
            {"factor_id": "glycerol", "type": "continuous", "min": 0, "max": 50, "allow_zero": True},
            {"factor_id": "vitamins_x", "type": "continuous", "min": 0, "max": 2},
            {"factor_id": "trace_metals", "type": "discrete", "levels": [0, 1]},
        ],
        "constraints": [],
        "design_policy": {"run_budget": 8},
    }
    state.update(overrides)
    return state


class BofireStrategyAdapterRoutingTests(unittest.TestCase):
    def test_routes_for_supported_constrained_design_without_importing_bofire(self) -> None:
        state = _bofire_state(
            constraints=[
                {
                    "constraint_id": "total_carbon_lte_80",
                    "type": "linear",
                    "coefficients": {"glucose": 1, "glycerol": 1},
                    "operator": "<=",
                    "rhs": 80,
                },
                {
                    "constraint_id": "at_most_one_carbon",
                    "type": "nchoosek",
                    "features": ["glucose", "glycerol"],
                    "max_count": 1,
                },
                {
                    "constraint_id": "trace_metals_requires_vitamins",
                    "type": "conditional",
                    "if": {"trace_metals": 1},
                    "then": {"vitamins_x": {">=": 1}},
                },
            ]
        )
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            decision = bofire_strategy.routing_decision(state)
            report = bofire_strategy.plan_bofire_wave2(state, [], backend="bofire", remaining_budget=4)

        self.assertTrue(decision["should_route"])
        self.assertEqual(decision["strategy_kind"], "constrained_doe")
        self.assertEqual(report["adapter_status"], "not_available")
        self.assertEqual([item["type"] for item in report["domain_spec"]["constraints"]], ["linear", "nchoosek", "linear"])
        self.assertEqual(report["domain_spec"]["constraints"][2]["source_type"], "conditional_binary_threshold")
        self.assertEqual(report["domain_spec"]["unsupported_constraints"], [])
        self.assertEqual(report["candidate_design"], [])

    def test_routes_multiobjective_and_multifidelity_cases(self) -> None:
        multiobjective = _bofire_state(
            responses=[
                {"response_id": "titer", "direction": "maximize"},
                {"response_id": "lactate", "direction": "minimize"},
            ]
        )
        multifidelity = _bofire_state(
            scale_context={"from_scale": "plate", "to_scale": "reactor"},
            campaign_arms=[
                {"arm_id": "plate", "purpose": "screening"},
                {"arm_id": "reactor", "purpose": "confirmation"},
            ],
        )
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            mo = bofire_strategy.routing_decision(multiobjective)
            mf = bofire_strategy.routing_decision(multifidelity, usable_rows=[{"arm_id": "plate"}, {"arm_id": "reactor"}])

        self.assertTrue(mo["should_route"])
        self.assertEqual(mo["strategy_kind"], "multi_objective")
        self.assertTrue(mf["should_route"])
        self.assertEqual(mf["strategy_kind"], "multi_fidelity")
        self.assertEqual(bofire_strategy.build_domain_spec(multifidelity)["fidelity"]["key"], "scale_fidelity")

    def test_box_constrained_single_objective_stays_on_default_path_unless_requested(self) -> None:
        state = _bofire_state()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            default = bofire_strategy.routing_decision(state)
            requested = bofire_strategy.routing_decision(state, backend="bofire")

        self.assertFalse(default["should_route"])
        self.assertTrue(requested["should_route"])
        self.assertEqual(requested["strategy_kind"], "single_objective")

    def test_unsupported_constraint_translation_blocks_execution(self) -> None:
        state = _bofire_state(
            constraints=[
                {
                    "constraint_id": "trace_metals_requires_vitamins",
                    "type": "conditional",
                    "if": {"trace_metals": "present"},
                    "then": {"vitamins_x": {">=": 1}},
                }
            ]
        )
        with mock.patch.object(bofire_strategy, "is_available", return_value=True):
            report = bofire_strategy.plan_bofire_wave2(state, [], backend="bofire", remaining_budget=2)

        self.assertEqual(report["adapter_status"], "translation_blocked")
        self.assertEqual(report["domain_spec"]["unsupported_constraints"], ["trace_metals_requires_vitamins"])


MEDIA_COST_FIXTURE = (
    ROOT / "examples" / "demo-media-cost-bofire" / "campaign_manifest.json"
)

CARBON_FACTORS = ("glucose", "glycerol", "lactose", "sucrose", "xylose")

COST_COEFFICIENTS_USD_PER_G = {
    "glucose": 0.00070,
    "glycerol": 0.00170,
    "lactose": 0.00090,
    "sucrose": 0.00110,
    "xylose": 0.00200,
    "ammonium_sulfate": 0.00025,
    "corn_steep_liquor": 0.00080,
    "yeast_extract": 0.00350,
    "tryptone": 0.01200,
}

COST_BUDGET_USD_PER_L = 0.80
TOTAL_CARBON_LIMIT_G_PER_L = 100.0
MAX_ACTIVE_CARBONS = 2
ACTIVE_THRESHOLD_G_PER_L = 1e-6


def _load_media_cost_state() -> dict[str, object]:
    return json.loads(MEDIA_COST_FIXTURE.read_text())


class BofireMediaCostFixtureTests(unittest.TestCase):
    """Verify the cost-constrained media manifest translates without requiring BoFire."""

    def test_fixture_loads_and_routes_to_constrained_doe(self) -> None:
        state = _load_media_cost_state()
        decision = bofire_strategy.routing_decision(state)
        self.assertTrue(decision["should_route"])
        self.assertEqual(decision["strategy_kind"], "constrained_doe")
        self.assertIn("non_box_constraints", decision["reasons"])

    def test_translation_emits_all_three_constraint_types_without_blocking(self) -> None:
        state = _load_media_cost_state()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            report = bofire_strategy.plan_bofire_wave2(
                state, [], backend="bofire", remaining_budget=12
            )
        self.assertEqual(report["adapter_status"], "not_available")
        self.assertEqual(report["domain_spec"]["unsupported_constraints"], [])
        constraint_types = [item["type"] for item in report["domain_spec"]["constraints"]]
        self.assertEqual(constraint_types.count("linear"), 2)
        self.assertEqual(constraint_types.count("nchoosek"), 1)


def _carbon_activity(row: dict[str, float]) -> int:
    return sum(1 for name in CARBON_FACTORS if abs(row.get(name, 0.0)) > ACTIVE_THRESHOLD_G_PER_L)


def _row_total_carbon(row: dict[str, float]) -> float:
    return sum(row.get(name, 0.0) for name in CARBON_FACTORS)


def _row_cost_usd_per_L(row: dict[str, float]) -> float:
    return sum(row.get(name, 0.0) * coeff for name, coeff in COST_COEFFICIENTS_USD_PER_G.items())


@unittest.skipUnless(adapters.is_available("bofire"), "BoFire not installed")
class BofireMediaCostLiveExecutionTests(unittest.TestCase):
    """Live execution behind a skipUnless gate. Asserts every generated row is feasible."""

    def test_live_strategy_emits_only_feasible_candidate_rows(self) -> None:
        state = _load_media_cost_state()
        report = bofire_strategy.plan_bofire_wave2(
            state, [], backend="bofire", remaining_budget=12, seed=42
        )
        self.assertEqual(report["adapter_status"], "executed")
        self.assertEqual(report["candidate_design_count"], len(report["candidate_design"]))
        self.assertGreater(report["candidate_design_count"], 0)
        for index, row in enumerate(report["candidate_design"]):
            with self.subTest(row=index):
                self.assertLessEqual(
                    _row_total_carbon(row),
                    TOTAL_CARBON_LIMIT_G_PER_L + 1e-6,
                    f"row {index} violates total-carbon constraint",
                )
                self.assertLessEqual(
                    _carbon_activity(row),
                    MAX_ACTIVE_CARBONS,
                    f"row {index} has > {MAX_ACTIVE_CARBONS} active carbon sources",
                )
                self.assertGreaterEqual(
                    _carbon_activity(row),
                    1,
                    f"row {index} has zero active carbon sources (min_count=1)",
                )
                self.assertLessEqual(
                    _row_cost_usd_per_L(row),
                    COST_BUDGET_USD_PER_L + 1e-6,
                    f"row {index} cost ${_row_cost_usd_per_L(row):.4f}/L > budget ${COST_BUDGET_USD_PER_L}/L",
                )


SCALE_BRIDGE_FIXTURE = ROOT / "examples" / "demo-shakeflask-to-2l-bofire" / "campaign_manifest.json"
SCALE_BRIDGE_ROWS = ROOT / "examples" / "demo-shakeflask-to-2l-bofire" / "inputs" / "historical_run_ledger.csv"


def _load_scale_bridge_state() -> dict[str, object]:
    return json.loads(SCALE_BRIDGE_FIXTURE.read_text())


def _load_scale_bridge_rows() -> list[dict[str, str]]:
    import csv

    with SCALE_BRIDGE_ROWS.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def _load_bofire_smoke_script():
    scripts_dir = ROOT / "skills" / "biosymphony-ferm-doe" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("run_bofire_smoke_for_tests", scripts_dir / "run_bofire_smoke.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BofireScaleBridgeFixtureTests(unittest.TestCase):
    """Shake-flask to 2 L fixture routes as a multi-fidelity BoFire candidate."""

    def test_fixture_routes_to_multi_fidelity_with_prior_rows(self) -> None:
        state = _load_scale_bridge_state()
        rows = _load_scale_bridge_rows()
        decision = bofire_strategy.routing_decision(state, rows)
        self.assertTrue(decision["should_route"])
        self.assertEqual(decision["strategy_kind"], "multi_fidelity")
        self.assertIn("scale_fidelity_structure", decision["reasons"])

    def test_fixture_domain_declares_target_fidelity(self) -> None:
        state = _load_scale_bridge_state()
        domain = bofire_strategy.build_domain_spec(state)
        self.assertEqual(domain["fidelity"]["key"], "scale_fidelity")
        self.assertEqual(domain["fidelity"]["categories"], ["shake_flask_10ml", "bioreactor_2l"])
        self.assertEqual(domain["fidelity"]["fidelities"], [1, 0])

    def test_fixture_smoke_report_uses_prior_rows_without_bofire(self) -> None:
        state = _load_scale_bridge_state()
        rows = _load_scale_bridge_rows()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            report = bofire_strategy.plan_bofire_wave2(state, rows, backend="bofire", remaining_budget=2)
        self.assertEqual(report["adapter_status"], "not_available")
        self.assertEqual(report["strategy_kind"], "multi_fidelity")
        self.assertEqual(report["remaining_run_budget"], 2)


class BofireSmokeScriptTests(unittest.TestCase):
    def test_strict_execution_errors_fail_closed(self) -> None:
        module = _load_bofire_smoke_script()
        errors = module.strict_execution_errors(
            {"adapter_status": "not_available", "candidate_design_count": 0},
            require_executed=True,
            require_candidates=True,
        )

        self.assertEqual(
            errors,
            [
                "adapter_status must be executed, got not_available",
                "candidate_design_count must be greater than zero",
            ],
        )

    def test_strict_execution_errors_pass_for_executed_candidates(self) -> None:
        module = _load_bofire_smoke_script()
        self.assertEqual(
            module.strict_execution_errors(
                {"adapter_status": "executed", "candidate_design_count": 3},
                require_executed=True,
                require_candidates=True,
            ),
            [],
        )


class BofireHtmlReporterTests(unittest.TestCase):
    """Stdlib-only HTML reporter renders without BoFire installed."""

    def test_render_not_available_report_contains_factors_and_constraints(self) -> None:
        from biosymphony_ferm_doe.reporters import bofire_html

        state = _load_media_cost_state()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            report = bofire_strategy.plan_bofire_wave2(
                state, [], backend="bofire", remaining_budget=12
            )
        rendered = bofire_html.render_to_string(report, manifest=state)

        self.assertTrue(rendered.startswith("<!DOCTYPE html>"))
        self.assertIn(str(report["campaign_id"]), rendered)
        self.assertIn("Non-claim:", rendered)
        self.assertIn("not_available", rendered)
        self.assertIn("constrained_doe", rendered)
        for factor_id in CARBON_FACTORS:
            self.assertIn(factor_id, rendered)
        self.assertIn("total_carbon_lte_100", rendered)
        self.assertIn("at_most_two_carbons", rendered)
        self.assertIn("media_cost_lte_080_per_L", rendered)
        self.assertIn('<script type="application/ld+json">', rendered)
        self.assertIn("<svg", rendered)  # pipeline SVG always renders

    def test_pipeline_svg_highlights_strategy_kind(self) -> None:
        from biosymphony_ferm_doe.reporters import _pipeline_svg

        report = {
            "campaign_id": "test",
            "strategy_kind": "constrained_doe",
            "adapter_status": "executed",
            "candidate_design_count": 12,
            "route": {
                "should_route": True,
                "reasons": ["non_box_constraints"],
            },
        }
        svg = _pipeline_svg.render_pipeline_svg(report)
        self.assertIn("<svg", svg)
        self.assertIn("DoEStrategy", svg)
        self.assertIn("12 candidate", svg)
        self.assertIn("non_box_constraints", svg)

    def test_charts_module_soft_imports_gracefully(self) -> None:
        from biosymphony_ferm_doe.reporters import _charts

        # Whether or not Plotly is available, calling render fns should not raise.
        state = _load_media_cost_state()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            report = bofire_strategy.plan_bofire_wave2(
                state, [], backend="bofire", remaining_budget=12
            )
        slice_html = _charts.render_constraint_slice(report, state)
        cost_html = _charts.render_cost_stack(report, state)
        heatmap_html = _charts.render_factor_heatmap(report, state)

        if _charts.is_available():
            self.assertIn("plotly", slice_html.lower())
        else:
            self.assertEqual(slice_html, "")
            self.assertEqual(cost_html, "")
            self.assertEqual(heatmap_html, "")

    def test_render_with_injected_rows_flags_feasibility_correctly(self) -> None:
        from biosymphony_ferm_doe.reporters import bofire_html

        state = _load_media_cost_state()
        with mock.patch.object(bofire_strategy, "is_available", return_value=False):
            report = bofire_strategy.plan_bofire_wave2(
                state, [], backend="bofire", remaining_budget=4
            )
        report["candidate_design"] = [
            {"run_id": "FEASIBLE-1", "glucose": 40.0, "ammonium_sulfate": 5.0},
            {"run_id": "INFEASIBLE-COST", "tryptone": 20.0, "yeast_extract": 25.0, "glucose": 30.0},
            {"run_id": "INFEASIBLE-CARBON", "glucose": 60.0, "glycerol": 60.0},
        ]
        report["candidate_design_count"] = 3
        rendered = bofire_html.render_to_string(report, manifest=state)

        self.assertIn("FEASIBLE-1", rendered)
        self.assertIn("infeasible", rendered)
        self.assertIn("class='bad'", rendered)
        self.assertIn("class='ok'", rendered)


@unittest.skipUnless(adapters.is_available("salib"), "SALib not installed")
class SalibSensitivityAdapterTests(unittest.TestCase):
    def test_pawn_and_delta_indices_on_arbitrary_design(self) -> None:
        adapter = adapters.get_adapter("salib")
        assert adapter is not None
        factors = [
            {"factor_id": "x1", "low": 0.0, "high": 1.0},
            {"factor_id": "x2", "low": 0.0, "high": 1.0},
            {"factor_id": "x3", "low": 0.0, "high": 1.0},
        ]
        import numpy as _np
        rng = _np.random.default_rng(0)
        X = rng.uniform(0.0, 1.0, size=(256, 3))
        Y = 3.0 * X[:, 0] + 0.2 * X[:, 1] + 0.0 * X[:, 2] + 0.05 * rng.standard_normal(256)
        pawn = adapter.pawn_indices(factors, X, Y, S=10)
        self.assertEqual(set(pawn.keys()), {"x1", "x2", "x3"})
        self.assertGreater(pawn["x1"]["median"], pawn["x3"]["median"])
        delta = adapter.delta_indices(factors, X, Y, num_resamples=50)
        self.assertEqual(set(delta.keys()), {"x1", "x2", "x3"})
        self.assertGreater(delta["x1"]["delta"], delta["x3"]["delta"])

    def test_sobol_indices_with_saltelli_sample(self) -> None:
        adapter = adapters.get_adapter("salib")
        assert adapter is not None
        factors = [
            {"factor_id": "x1", "low": 0.0, "high": 1.0},
            {"factor_id": "x2", "low": 0.0, "high": 1.0},
        ]
        X = adapter.saltelli_sample(factors, n_base=128, calc_second_order=False)
        Y = 2.0 * X[:, 0] + 0.5 * X[:, 1]
        sobol = adapter.sobol_indices(factors, Y, calc_second_order=False)
        self.assertGreater(sobol["x1"]["ST"], sobol["x2"]["ST"])
        self.assertGreater(sobol["x1"]["S1"], 0.5)


if __name__ == "__main__":
    unittest.main()
