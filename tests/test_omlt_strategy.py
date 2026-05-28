"""Tests for the OMLT-backed routed adapter.

Coverage map (mirrors the OMLT design notes in `docs/ADAPTER_DESIGN_NOTES.md`
and the OMLT-supersedes-ENTMOOT finding in `docs/BACKEND_EVAL_FINDINGS.md`):

- Translation tests (no omlt import needed):
  - `is_available` flips correctly when imports are mocked away
  - `routing_decision` fires on NChooseK
  - `routing_decision` fires on linear constraints
  - `routing_decision` fires on categorical factors
  - `build_domain_spec` produces the expected canonical shape
- Live-execution tests (gated on omlt + solver):
  - `_train_surrogate` completes on minimal data
  - `_encode_surrogate_as_pyomo` produces a solvable model
  - `ask_batch` returns N candidates
  - NChooseK constraint is honored in solutions
  - linear constraint is honored in solutions
  - integration test with `cardinality_heavy_media` fixture
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.adapters import omlt_strategy  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _three_factor_state(**overrides) -> dict:
    state: dict = {
        "campaign_id": "omlt-smoke",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "x1", "type": "continuous", "low": 0.0, "high": 10.0},
            {"factor_id": "x2", "type": "continuous", "low": 0.0, "high": 10.0},
            {"factor_id": "x3", "type": "continuous", "low": 0.0, "high": 10.0},
        ],
        "constraints": [],
        "design_policy": {"run_budget": 4},
    }
    state.update(overrides)
    return state


def _four_component_nchoosek_state() -> dict:
    """4 continuous + NChooseK(1,2) — mirrors cardinality_heavy_media."""
    return {
        "campaign_id": "omlt-cardinality-test",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "c1", "type": "continuous", "low": 0.0, "high": 40.0},
            {"factor_id": "c2", "type": "continuous", "low": 0.0, "high": 40.0},
            {"factor_id": "c3", "type": "continuous", "low": 0.0, "high": 40.0},
            {"factor_id": "c4", "type": "continuous", "low": 0.0, "high": 40.0},
        ],
        "constraints": [
            {
                "constraint_id": "one_or_two",
                "type": "nchoosek",
                "features": ["c1", "c2", "c3", "c4"],
                "min_count": 1,
                "max_count": 2,
            }
        ],
        "design_policy": {"run_budget": 4},
    }


def _linear_state() -> dict:
    return {
        "campaign_id": "omlt-linear-test",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "a", "type": "continuous", "low": 0.0, "high": 10.0},
            {"factor_id": "b", "type": "continuous", "low": 0.0, "high": 10.0},
        ],
        "constraints": [
            {
                "constraint_id": "sum_le_5",
                "type": "linear",
                "coefficients": {"a": 1.0, "b": 1.0},
                "operator": "<=",
                "rhs": 5.0,
            }
        ],
        "design_policy": {"run_budget": 4},
    }


def _categorical_state() -> dict:
    return {
        "campaign_id": "omlt-cat-test",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "f1", "type": "categorical", "levels": ["A", "B"]},
            {"factor_id": "x1", "type": "continuous", "low": 0.0, "high": 10.0},
        ],
        "constraints": [],
        "design_policy": {"run_budget": 4},
    }


# ---------------------------------------------------------------------------
# Translation / routing tests — no live execution required
# ---------------------------------------------------------------------------


class AvailabilityTests(unittest.TestCase):
    def test_is_available_returns_false_when_omlt_missing(self) -> None:
        original = omlt_strategy.importlib.util.find_spec

        def fake_find_spec(name):
            if name == "omlt":
                return None
            return original(name)

        with mock.patch.object(
            omlt_strategy.importlib.util, "find_spec", side_effect=fake_find_spec
        ):
            self.assertFalse(omlt_strategy.is_available())

    def test_is_available_returns_false_when_onnxmltools_missing(self) -> None:
        original = omlt_strategy.importlib.util.find_spec

        def fake_find_spec(name):
            if name == "onnxmltools":
                return None
            return original(name)

        with mock.patch.object(
            omlt_strategy.importlib.util, "find_spec", side_effect=fake_find_spec
        ):
            self.assertFalse(omlt_strategy.is_available())


class RoutingDecisionTests(unittest.TestCase):
    def test_routing_does_not_fire_on_box_constrained_state(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            decision = omlt_strategy.routing_decision(state)
        self.assertFalse(decision["should_route"])
        self.assertEqual(decision["reasons"], [])
        self.assertEqual(decision["strategy_kind"], "not_routed")

    def test_routes_when_explicit_backend_omlt(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            decision = omlt_strategy.routing_decision(state, backend="omlt")
        self.assertTrue(decision["should_route"])
        self.assertIn("operator_requested_omlt", decision["reasons"])

    def test_routes_on_nchoosek_constraint(self) -> None:
        state = _four_component_nchoosek_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            decision = omlt_strategy.routing_decision(state)
        self.assertTrue(decision["should_route"])
        self.assertIn("non_box_constraints", decision["reasons"])
        self.assertEqual(decision["strategy_kind"], "constrained_mip_over_surrogate")

    def test_routes_on_linear_constraint(self) -> None:
        state = _linear_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            decision = omlt_strategy.routing_decision(state)
        self.assertTrue(decision["should_route"])
        self.assertIn("non_box_constraints", decision["reasons"])

    def test_routes_on_categorical_factor(self) -> None:
        state = _categorical_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            decision = omlt_strategy.routing_decision(state)
        self.assertTrue(decision["should_route"])
        self.assertIn("categorical_factor_present", decision["reasons"])

    def test_does_not_route_when_backend_hard_off(self) -> None:
        state = _four_component_nchoosek_state()
        decision = omlt_strategy.routing_decision(state, backend="entmoot")
        self.assertFalse(decision["should_route"])


class BuildDomainSpecTests(unittest.TestCase):
    def test_continuous_factor_emits_low_high(self) -> None:
        state = _three_factor_state()
        domain = omlt_strategy.OmltStrategy.build_domain_spec(state)
        self.assertEqual(len(domain["factors"]), 3)
        for f in domain["factors"]:
            self.assertEqual(f["type"], "continuous")
            self.assertEqual(f["low"], 0.0)
            self.assertEqual(f["high"], 10.0)

    def test_categorical_factor_carries_levels(self) -> None:
        state = _categorical_state()
        domain = omlt_strategy.OmltStrategy.build_domain_spec(state)
        cat = next(f for f in domain["factors"] if f["factor_id"] == "f1")
        self.assertEqual(cat["type"], "categorical")
        self.assertEqual(cat["levels"], ["A", "B"])

    def test_responses_normalized_to_minimize_maximize(self) -> None:
        state = _four_component_nchoosek_state()
        domain = omlt_strategy.OmltStrategy.build_domain_spec(state)
        self.assertEqual(domain["responses"][0]["direction"], "minimize")


class PlanReportShapeTests(unittest.TestCase):
    def test_not_routed_emits_route_decision(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            report = omlt_strategy.plan_omlt_wave2(state, [], remaining_budget=4)
        self.assertEqual(report["adapter_status"], "not_routed")
        self.assertEqual(report["candidate_design_count"], 0)
        self.assertEqual(report["claim_level"], omlt_strategy.CLAIM_LEVEL)

    def test_routed_but_not_installed_emits_not_available(self) -> None:
        state = _four_component_nchoosek_state()
        with mock.patch.object(omlt_strategy, "is_available", return_value=False):
            report = omlt_strategy.plan_omlt_wave2(state, [], remaining_budget=4)
        self.assertEqual(report["adapter_status"], "not_available")
        self.assertIn("OMLT is not installed", report["issues"][0])


# ---------------------------------------------------------------------------
# Live-execution tests — gated on omlt + solver
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    omlt_strategy.is_available()
    and omlt_strategy._solver_available(omlt_strategy.DEFAULT_SOLVER),
    "OMLT or APPSI HiGHS solver not available",
)
class OmltLiveExecutionTests(unittest.TestCase):
    """Live OMLT smoke tests. Skipped when omlt or solver are absent."""

    def test_train_surrogate_completes(self) -> None:
        """Surrogate fit + ONNX export + OMLT wrap succeeds on minimal data."""
        import numpy as np

        state = _three_factor_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=7)
        rng = np.random.default_rng(7)
        X = rng.uniform(0, 10, size=(20, 3))
        y = ((X[:, 0] - 5) ** 2 + (X[:, 1] - 3) ** 2 + 0.5 * X[:, 2])
        gbt, bounds = strategy._train_surrogate(X, y)
        self.assertIsNotNone(gbt)
        self.assertEqual(set(bounds.keys()), {0, 1, 2})
        for i in range(3):
            self.assertEqual(bounds[i], (0.0, 10.0))

    def test_encode_surrogate_produces_solvable_model(self) -> None:
        """_encode_surrogate_as_pyomo + solver returns an optimal solution."""
        import numpy as np
        import pyomo.environ as pyo

        state = _three_factor_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=11)
        rng = np.random.default_rng(11)
        X = rng.uniform(0, 10, size=(20, 3))
        y = ((X[:, 0] - 5) ** 2 + (X[:, 1] - 3) ** 2 + 0.5 * X[:, 2])
        gbt, bounds = strategy._train_surrogate(X, y)
        pyomo_model = strategy._encode_surrogate_as_pyomo(gbt, bounds)
        solver = pyo.SolverFactory(omlt_strategy.DEFAULT_SOLVER)
        result = solver.solve(pyomo_model, tee=False)
        term = str(result.solver.termination_condition).lower()
        self.assertIn("optimal", term)

    def test_ask_batch_returns_n_candidates(self) -> None:
        """ask_batch(N) returns exactly N candidates with the expected shape."""
        import numpy as np

        state = _three_factor_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=23)
        rng = np.random.default_rng(23)
        X = rng.uniform(0, 10, size=(20, 3)).tolist()
        Y = [
            [(row[0] - 5) ** 2 + (row[1] - 3) ** 2 + 0.5 * row[2]]
            for row in X
        ]
        strategy.tell(X, Y)
        candidates = strategy.ask_batch(3)
        self.assertEqual(len(candidates), 3)
        for c in candidates:
            for key in (
                "iteration",
                "amounts",
                "binary",
                "n_active",
                "active_components",
                "objective_estimate",
                "cardinality_ok",
                "tie_cycle_detected",
                "solver_status",
            ):
                self.assertIn(key, c)
            self.assertEqual(set(c["amounts"].keys()), {"x1", "x2", "x3"})

    def test_nchoosek_constraint_honored(self) -> None:
        """min/max count constraints hold for every candidate in the batch.

        With NChooseK(min=1, max=2) every candidate must have 1 or 2 active
        binary indicators and cardinality_ok must be True.
        """
        state = _four_component_nchoosek_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=31)
        # Tell zero rows — adapter synthesizes training data.
        candidates = strategy.ask_batch(4)
        self.assertEqual(len(candidates), 4)
        for c in candidates:
            self.assertTrue(c["cardinality_ok"], f"cardinality leak: {c}")
            self.assertGreaterEqual(c["n_active"], 1)
            self.assertLessEqual(c["n_active"], 2)

    def test_linear_constraint_honored(self) -> None:
        """sum <= 5 constraint holds for every candidate."""
        state = _linear_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=37)
        candidates = strategy.ask_batch(2)
        self.assertGreaterEqual(len(candidates), 1)
        for c in candidates:
            total = c["amounts"]["a"] + c["amounts"]["b"]
            self.assertLessEqual(total, 5.0 + 1e-6, f"linear leak: {c}")

    def test_no_good_cuts_produce_diverse_binary_combos(self) -> None:
        """ask_batch should give different binary-indicator configurations."""
        state = _four_component_nchoosek_state()
        strategy = omlt_strategy.OmltStrategy(state, seed=41)
        candidates = strategy.ask_batch(3)
        combos = {
            tuple(sorted(c["active_components"]))
            for c in candidates
        }
        # At least 2 distinct binary configurations across 3 candidates.
        self.assertGreaterEqual(
            len(combos),
            2,
            f"no_good cuts did not produce diverse combos: {combos}",
        )

    def test_integration_cardinality_heavy_media_fixture(self) -> None:
        """End-to-end integration on the actual cardinality_heavy_media fixture."""
        manifest_path = (
            ROOT
            / "examples"
            / "adaptive-backend-eval"
            / "cardinality_heavy_media"
            / "campaign_manifest.json"
        )
        runs_path = (
            ROOT
            / "examples"
            / "adaptive-backend-eval"
            / "cardinality_heavy_media"
            / "inputs"
            / "prior_runs.csv"
        )
        manifest = json.loads(manifest_path.read_text())
        import csv as _csv
        rows = list(_csv.DictReader(runs_path.open()))
        for row in rows:
            for k, v in list(row.items()):
                try:
                    row[k] = float(v)
                except (ValueError, TypeError):
                    pass
        report = omlt_strategy.plan_omlt_wave2(
            manifest, rows, remaining_budget=4, backend="omlt", seed=42
        )
        self.assertEqual(report["adapter_status"], "executed")
        self.assertGreaterEqual(report["candidate_design_count"], 1)
        # Every candidate must respect the 1<=k<=2 cardinality cap.
        for c in report["candidate_design"]:
            self.assertTrue(c["cardinality_ok"], f"cardinality leak in fixture: {c}")
        sys.path.insert(0, str(ROOT / "scripts"))
        from _contract_emitter import check_constraints  # noqa: E402

        contract_rows = []
        for i, candidate in enumerate(report["candidate_design"]):
            row = {"run_id": f"omlt-{i + 1:03d}"}
            row.update(candidate.get("amounts") or {})
            contract_rows.append(row)
        check = check_constraints(contract_rows, manifest)
        self.assertTrue(check["nchoosek_pass"], f"amount-based cardinality leak: {check}")


if __name__ == "__main__":
    unittest.main()
