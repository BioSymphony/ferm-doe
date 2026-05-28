"""Tests for the TabPFN-v3 BoTorch surrogate adapter.

These tests exercise the live TabPFN model (no mocking of the regressor itself)
except where explicitly verifying token-gating fallback behavior.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.adapters import tabpfn_strategy  # noqa: E402


FIXTURES_ROOT = ROOT / "examples" / "adaptive-backend-eval"


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


TABPFN_LIVE_AVAILABLE = (
    tabpfn_strategy.is_available()
    and _has_module("torch")
    and _has_module("botorch")
    and _has_module("gpytorch")
)


def _coerce(v):
    if v in (None, ""):
        return None
    try:
        return float(v) if any(c in str(v) for c in ".eE") or str(v).lstrip("-").isdigit() else v
    except ValueError:
        return v


def _load_fixture(name: str):
    manifest = json.loads((FIXTURES_ROOT / name / "campaign_manifest.json").read_text())
    rows_path = FIXTURES_ROOT / name / "inputs" / "prior_runs.csv"
    if rows_path.exists():
        with rows_path.open() as fh:
            rows = [{k: _coerce(v) for k, v in row.items()} for row in csv.DictReader(fh)]
    else:
        rows = []
    return manifest, rows


def _check_constraints(candidates, manifest):
    sys.path.insert(0, str(ROOT / "scripts"))
    from _contract_emitter import check_constraints  # noqa: E402

    return check_constraints(candidates, manifest)


class IsAvailableTests(unittest.TestCase):
    @unittest.skipUnless(
        tabpfn_strategy.is_available(),
        "TabPFN package/token not available in this environment",
    )
    def test_is_available_true_with_token_and_package(self) -> None:
        # Token must be present in test env (see SKILL ENV)
        self.assertTrue(os.environ.get("TABPFN_TOKEN", "").strip(), msg="TABPFN_TOKEN env required")
        self.assertTrue(tabpfn_strategy.is_available())

    def test_is_available_false_without_token(self) -> None:
        with mock.patch.dict(os.environ, {"TABPFN_TOKEN": ""}, clear=False):
            self.assertFalse(tabpfn_strategy.is_available())


class RoutingDecisionTests(unittest.TestCase):
    def test_routes_for_low_data_regime(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        # Default fixture has 4 rows (<20)
        decision = tabpfn_strategy.routing_decision(manifest, rows)
        self.assertTrue(decision["should_route"], msg=f"reasons={decision['reasons']}")
        self.assertIn("low_data_regime", decision["reasons"])

    def test_does_not_route_when_hard_off(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        decision = tabpfn_strategy.routing_decision(manifest, rows, backend="bofire")
        self.assertFalse(decision["should_route"])

    def test_does_not_route_at_high_data_and_many_factors_unless_requested(self) -> None:
        # Build a synthetic state with many factors and many usable rows
        manifest = {
            "factors": [
                {"factor_id": f"f{i}", "type": "continuous", "min": 0, "max": 1}
                for i in range(12)  # > small_factor_count_threshold
            ],
            "responses": [{"response_id": "y", "direction": "maximize"}],
        }
        rows = [{**{f"f{i}": 0.5 for i in range(12)}, "y": 1.0} for _ in range(30)]
        decision = tabpfn_strategy.routing_decision(manifest, rows)
        self.assertFalse(decision["should_route"])

    def test_routes_when_explicitly_requested_even_at_high_data(self) -> None:
        manifest = {
            "factors": [
                {"factor_id": f"f{i}", "type": "continuous", "min": 0, "max": 1}
                for i in range(12)
            ],
            "responses": [{"response_id": "y", "direction": "maximize"}],
        }
        rows = [{**{f"f{i}": 0.5 for i in range(12)}, "y": 1.0} for _ in range(30)]
        decision = tabpfn_strategy.routing_decision(manifest, rows, backend="tabpfn")
        self.assertTrue(decision["should_route"])
        self.assertIn("operator_requested_tabpfn", decision["reasons"])


class BuildDomainSpecTests(unittest.TestCase):
    def test_continuous_only(self) -> None:
        manifest, _ = _load_fixture("static_constrained_media")
        spec = tabpfn_strategy.build_domain_spec(manifest)
        kinds = {item["type"] for item in spec["inputs"]}
        self.assertEqual(kinds, {"continuous"})
        self.assertEqual(len(spec["outputs"]), 1)

    def test_categorical_handled_via_one_hot_dimension(self) -> None:
        manifest, _ = _load_fixture("low_data_hybrid_transfer")
        spec = tabpfn_strategy.build_domain_spec(manifest)
        kinds = {item["type"] for item in spec["inputs"]}
        # Domain spec preserves the original categorical kind; one-hot expansion is internal
        self.assertIn("categorical", kinds)
        # categorical_exclude must be present as a supported constraint
        self.assertTrue(
            any(c["type"] == "categorical_exclude" for c in spec["constraints"]),
            msg=f"constraints={spec['constraints']}",
        )


@unittest.skipUnless(TABPFN_LIVE_AVAILABLE, "TabPFN live stack not available")
class SurrogateTests(unittest.TestCase):
    def test_surrogate_fits_on_small_data(self) -> None:
        import torch

        train_X = torch.rand(8, 4, dtype=torch.float64)
        train_Y = torch.rand(8, dtype=torch.float64)
        surrogate = tabpfn_strategy._TabPFNSurrogate(train_X=train_X, train_Y=train_Y, seed=42)
        surrogate.fit()
        self.assertIsNotNone(surrogate._regressor)

    def test_posterior_returns_finite_mean_and_variance(self) -> None:
        import torch

        train_X = torch.rand(10, 3, dtype=torch.float64)
        train_Y = torch.rand(10, dtype=torch.float64)
        surrogate = tabpfn_strategy._TabPFNSurrogate(train_X=train_X, train_Y=train_Y, seed=42)
        surrogate.fit()
        X_query = torch.rand(5, 1, 3, dtype=torch.float64)
        posterior = surrogate.posterior(X_query)
        self.assertTrue(torch.isfinite(posterior.mean).all())
        self.assertTrue(torch.isfinite(posterior.variance).all())
        self.assertTrue((posterior.variance > 0).all())


@unittest.skipUnless(TABPFN_LIVE_AVAILABLE, "TabPFN live stack not available")
class PlanTabPFNFollowUpTests(unittest.TestCase):
    def test_returns_n_candidates_respecting_budget(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        report = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=4, seed=42)
        self.assertEqual(report["adapter_status"], "executed")
        self.assertEqual(report["candidate_design_count"], 4)

    def test_respects_linear_constraints(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        report = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=8, seed=7)
        self.assertEqual(report["adapter_status"], "executed")
        # Manifest has a total_carbon <= 60 linear cap; check the candidate rows
        check = _check_constraints(report["candidate_design"], manifest)
        self.assertTrue(check["linear_constraints_pass"], msg=f"violations={check['violations']}")
        self.assertTrue(check["factor_bounds_pass"])

    def test_respects_nchoosek_best_effort(self) -> None:
        manifest, rows = _load_fixture("cardinality_heavy_media")
        report = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=8, seed=11)
        self.assertEqual(report["adapter_status"], "executed")
        check = _check_constraints(report["candidate_design"], manifest)
        # NChooseK is enforced best-effort via random-active-subset sampling, so the leak
        # rate must be 0 for an adapter that's actively gating cardinality at sample time
        self.assertTrue(check["nchoosek_pass"], msg=f"violations={check['violations']}")


@unittest.skipUnless(TABPFN_LIVE_AVAILABLE, "TabPFN live stack not available")
class IntegrationTests(unittest.TestCase):
    def test_integration_static_constrained_media(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        report = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=4, seed=42)
        self.assertEqual(report["adapter_status"], "executed")
        self.assertGreaterEqual(report["candidate_design_count"], 1)
        # Every candidate row must carry the claim_level + scoring_mode contract
        for row in report["candidate_design"]:
            self.assertEqual(row["claim_level"], tabpfn_strategy.CLAIM_LEVEL)
            self.assertTrue(row["scoring_mode"].startswith("tabpfn_strategy"))
            self.assertIn("run_id", row)


@unittest.skipUnless(TABPFN_LIVE_AVAILABLE, "TabPFN live stack not available")
class ReproducibilityTests(unittest.TestCase):
    def test_same_seed_same_candidates(self) -> None:
        manifest, rows = _load_fixture("static_constrained_media")
        report_a = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=4, seed=42)
        report_b = tabpfn_strategy.plan_tabpfn_wave2(manifest, rows, remaining_budget=4, seed=42)
        # Compare candidate factor values (ignore run_id labels)
        keys = [f["factor_id"] for f in manifest["factors"]]

        def _project(rows):
            return [tuple(round(float(r.get(k, 0.0) or 0.0), 4) for k in keys) for r in rows]

        self.assertEqual(_project(report_a["candidate_design"]), _project(report_b["candidate_design"]))


if __name__ == "__main__":
    unittest.main()
