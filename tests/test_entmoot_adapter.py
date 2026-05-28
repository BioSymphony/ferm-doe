"""Tests for the ENTMOOT v2 routed adapter.

Coverage map (mirrors `docs/ENTMOOT_SWAP_DESIGN.md` test plan):

- Translation tests (no entmoot import needed):
  - manifest -> normalized constraints
  - `routing_decision` fires on NChooseK + on explicit backend request
- Live-execution tests (gated by `@skipUnless`):
  - install smoke (one ask on a 3-factor problem)
  - NChooseK emission (closes RISK #1 — `min_count` honored)
  - solver fallback (`glpk` if available; HiGHS otherwise)
  - tie-cycle detection (closes RISK #3 — `tie_cycle_detected: True`)
  - 4-component reproduction smoke (NChooseK(1,2), cost $1.20/L, 4 iters,
    cardinality_pass_count == 4)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe import adapters  # noqa: E402
from biosymphony_ferm_doe.adapters import entmoot_strategy  # noqa: E402


# ---------------------------------------------------------------------------
# Translation / routing tests — no live execution required
# ---------------------------------------------------------------------------


def _three_factor_state(**overrides) -> dict:
    state: dict = {
        "campaign_id": "entmoot-smoke",
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


def _five_component_state(min_count: int, max_count: int) -> dict:
    return {
        "campaign_id": "entmoot-five-component",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "c1", "type": "continuous", "low": 0.0, "high": 30.0},
            {"factor_id": "c2", "type": "continuous", "low": 0.0, "high": 30.0},
            {"factor_id": "c3", "type": "continuous", "low": 0.0, "high": 30.0},
            {"factor_id": "c4", "type": "continuous", "low": 0.0, "high": 30.0},
            {"factor_id": "c5", "type": "continuous", "low": 0.0, "high": 30.0},
        ],
        "constraints": [
            {
                "constraint_id": "min_k_max_k",
                "type": "nchoosek",
                "features": ["c1", "c2", "c3", "c4", "c5"],
                "min_count": min_count,
                "max_count": max_count,
            }
        ],
        "design_policy": {"run_budget": 4},
    }


def _four_component_state() -> dict:
    """Mirror `examples/entmoot-nchoosek-smoke/smoke.py`: 4 carbons, NChooseK(1,2),
    cost ceiling $1.20/L. Cost coefficients in $/g (USD per gram of media).
    """
    return {
        "campaign_id": "entmoot-four-component-repro",
        "responses": [{"response_id": "y", "direction": "minimize"}],
        "factors": [
            {"factor_id": "glucose", "type": "continuous", "low": 0.0, "high": 40.0},
            {"factor_id": "glycerol", "type": "continuous", "low": 0.0, "high": 40.0},
            {"factor_id": "lactose", "type": "continuous", "low": 0.0, "high": 30.0},
            {"factor_id": "sucrose", "type": "continuous", "low": 0.0, "high": 30.0},
        ],
        "constraints": [
            {
                "constraint_id": "at_most_two_carbons",
                "type": "nchoosek",
                "features": ["glucose", "glycerol", "lactose", "sucrose"],
                "min_count": 1,
                "max_count": 2,
            },
            {
                "constraint_id": "cost_ceiling",
                "type": "linear",
                "coefficients": {
                    "glucose": 0.00070,
                    "glycerol": 0.00170,
                    "lactose": 0.00090,
                    "sucrose": 0.00110,
                },
                "operator": "<=",
                "rhs": 1.20,
            },
        ],
        "design_policy": {"run_budget": 4},
    }


class RoutingDecisionTests(unittest.TestCase):
    def test_does_not_route_on_box_constrained_state_without_backend(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(entmoot_strategy, "is_available", return_value=False):
            decision = entmoot_strategy.routing_decision(state)
        self.assertFalse(decision["should_route"])
        self.assertEqual(decision["reasons"], [])

    def test_routes_when_explicit_backend_entmoot(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(entmoot_strategy, "is_available", return_value=False):
            decision = entmoot_strategy.routing_decision(state, backend="entmoot")
        self.assertTrue(decision["should_route"])
        self.assertIn("tree_surrogate_requested", decision["reasons"])

    def test_routes_on_nchoosek_constraint(self) -> None:
        state = _five_component_state(min_count=1, max_count=2)
        with mock.patch.object(entmoot_strategy, "is_available", return_value=False):
            decision = entmoot_strategy.routing_decision(state)
        self.assertTrue(decision["should_route"])
        self.assertIn("nchoosek_constraint_with_bo", decision["reasons"])
        self.assertEqual(decision["strategy_kind"], "nchoosek_bo")


class PlanReportShapeTests(unittest.TestCase):
    def test_not_routed_emits_route_decision(self) -> None:
        state = _three_factor_state()
        with mock.patch.object(entmoot_strategy, "is_available", return_value=False):
            report = entmoot_strategy.plan_entmoot_wave2(
                state, [], remaining_budget=4
            )
        self.assertEqual(report["adapter_status"], "not_routed")
        self.assertEqual(report["candidate_design_count"], 0)
        self.assertEqual(report["candidate_design"], [])
        self.assertEqual(report["claim_level"], entmoot_strategy.CLAIM_LEVEL)

    def test_routed_but_not_installed_emits_not_available(self) -> None:
        state = _five_component_state(min_count=1, max_count=2)
        with mock.patch.object(entmoot_strategy, "is_available", return_value=False):
            report = entmoot_strategy.plan_entmoot_wave2(
                state, [], remaining_budget=4
            )
        self.assertEqual(report["adapter_status"], "not_available")
        self.assertEqual(report["candidate_design_count"], 0)
        self.assertIn("ENTMOOT is not installed", report["issues"][0])


# ---------------------------------------------------------------------------
# Live-execution tests — gated on entmoot + solver
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    entmoot_strategy.is_available()
    and entmoot_strategy._solver_available(entmoot_strategy.DEFAULT_SOLVER),
    "ENTMOOT or APPSI HiGHS solver not available",
)
class EntmootLiveExecutionTests(unittest.TestCase):
    """Live ENTMOOT smoke tests. Skipped when entmoot or solver are absent."""

    def test_install_smoke(self) -> None:
        """Instantiate on 3-factor problem, tell + ask once, check shape."""
        import random
        state = _three_factor_state()
        strategy = entmoot_strategy.EntmootStrategy(state, seed=7)
        # LightGBM (default ENTMOOT settings: num_boost_round=100,
        # min_data_in_leaf, etc.) needs ~10+ diverse training points to
        # produce a non-trivial tree ensemble. Three collinear points
        # would yield an empty-tree assert in ``meta_tree_ensemble.py``.
        rng = random.Random(7)
        X = [[rng.uniform(0, 10), rng.uniform(0, 10), rng.uniform(0, 10)] for _ in range(20)]
        Y = [[(row[0] - 5) ** 2 + (row[1] - 3) ** 2 + 0.5 * row[2]] for row in X]
        strategy.tell(X, Y)
        result = strategy.ask()

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
            "solver_wall_time_s",
            "elapsed_s",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["iteration"], 1)
        self.assertEqual(set(result["amounts"].keys()), {"x1", "x2", "x3"})
        # No NChooseK constraints, so binary is empty dict.
        self.assertEqual(result["binary"], {})
        self.assertEqual(result["solver_status"], "optimal")

    def test_nchoosek_min_count_emission(self) -> None:
        """RISK #1 closure: min_count=2 yields candidates with >= 2 active components.

        Without the adapter's explicit min_count constraint, ENTMOOT's shipped
        ``NChooseKConstraint._get_expr`` would silently drop the lower bound
        and the optimizer would return a degenerate single-active or zero-active
        point as the cheapest cost.
        """
        state = _five_component_state(min_count=2, max_count=4)
        strategy = entmoot_strategy.EntmootStrategy(state, seed=11)

        # Seed with cardinality-2 training data.
        X = [
            [10.0, 10.0, 0.0, 0.0, 0.0, 1, 1, 0, 0, 0],
            [0.0, 10.0, 10.0, 0.0, 0.0, 0, 1, 1, 0, 0],
            [0.0, 0.0, 10.0, 10.0, 0.0, 0, 0, 1, 1, 0],
            [0.0, 0.0, 0.0, 10.0, 10.0, 0, 0, 0, 1, 1],
        ]
        Y = [[1.0], [2.0], [3.0], [4.0]]
        strategy.tell(X, Y)

        seen_active_counts: list[int] = []
        for _ in range(4):
            result = strategy.ask()
            seen_active_counts.append(result["n_active"])
            self.assertGreaterEqual(
                result["n_active"],
                2,
                f"min_count=2 violated: only {result['n_active']} active in candidate",
            )
            self.assertLessEqual(result["n_active"], 4)
            self.assertTrue(result["cardinality_ok"])

        # Sanity: at least one ask hit the lower bound exactly.
        self.assertIn(2, seen_active_counts)

    def test_tie_cycle_detection(self) -> None:
        """RISK #3 closure: when a repeat candidate is detected the adapter
        sets ``tie_cycle_detected: True`` and perturbs the continuous slice.

        We exercise the detection path directly (the adapter's private
        check + perturb) rather than trying to force the LightGBM +
        Pyomo loop to land on an exact-repeat point, which depends on
        seed and solver tie-breaking.
        """
        import random
        state = _three_factor_state()
        strategy = entmoot_strategy.EntmootStrategy(state, seed=23)

        # Seed with diverse training data so the surrogate fits.
        rng = random.Random(23)
        X = [[rng.uniform(0, 10), rng.uniform(0, 10), rng.uniform(0, 10)] for _ in range(20)]
        Y = [[(row[0] - 2) ** 2 + (row[1] - 7) ** 2 + 0.3 * row[2]] for row in X]
        strategy.tell(X, Y)

        # First real ask — populates internal _told_X.
        result1 = strategy.ask()
        self.assertIn("tie_cycle_detected", result1)
        self.assertIsInstance(result1["tie_cycle_detected"], bool)

        # Directly verify the adapter's private collision-check + perturb:
        # 1) inject a known point into _told_X
        # 2) call _approx_equal on a near-identical tuple
        # 3) call _perturb and confirm the continuous slice moved.
        known = (3.0, 4.0, 5.0)
        strategy._told_X.append(known)
        self.assertTrue(strategy._approx_equal(known, known))
        self.assertTrue(strategy._approx_equal(known, (3.0 + 1e-9, 4.0 - 1e-9, 5.0)))

        amounts = {"x1": 3.0, "x2": 4.0, "x3": 5.0}
        binary: dict[str, float] = {}
        new_point, new_amounts, _ = strategy._perturb([3.0, 4.0, 5.0], amounts, binary)
        # All three continuous values must have moved (perturbation is
        # nonzero for every continuous feature).
        self.assertNotEqual(new_amounts["x1"], 3.0)
        self.assertNotEqual(new_amounts["x2"], 4.0)
        self.assertNotEqual(new_amounts["x3"], 5.0)
        # Within ±TIE_CYCLE_PERTURBATION_FRAC * range of original.
        span = 10.0
        max_kick = entmoot_strategy.TIE_CYCLE_PERTURBATION_FRAC * span + 1e-9
        for key, original in [("x1", 3.0), ("x2", 4.0), ("x3", 5.0)]:
            self.assertLessEqual(abs(new_amounts[key] - original), max_kick)

    def test_solver_fallback_glpk(self) -> None:
        """Pass `solver_name='glpk'` — should either work or fail loudly.

        GLPK is a system package and may not be installed in the test
        environment. If it is not available, ENTMOOT's instantiation
        should raise a clear runtime error rather than silently falling
        through to HiGHS.
        """
        state = _three_factor_state()
        if not entmoot_strategy._solver_available("glpk"):
            with self.assertRaises(RuntimeError) as cm:
                entmoot_strategy.EntmootStrategy(state, solver_name="glpk")
            self.assertIn("glpk", str(cm.exception).lower())
            return

        strategy = entmoot_strategy.EntmootStrategy(state, solver_name="glpk", seed=3)
        strategy.tell([[1.0, 1.0, 1.0], [5.0, 5.0, 5.0]], [[1.0], [25.0]])
        result = strategy.ask()
        self.assertEqual(result["solver_status"], "optimal")

    def test_reproduces_four_component_smoke(self) -> None:
        """4-component, NChooseK(1,2), cost ceiling $1.20/L, 4 iters.

        Mirrors `examples/entmoot-nchoosek-smoke/smoke.py` / `result.json` —
        cardinality_pass_count must equal 4.
        """
        state = _four_component_state()
        strategy = entmoot_strategy.EntmootStrategy(state, seed=42)

        # Seed with the same 30-row cardinality-feasible random training
        # set the smoke uses (compressed to a small representative subset
        # to keep the test fast).
        import random
        rng = random.Random(42)
        carbons = ["glucose", "glycerol", "lactose", "sucrose"]
        carbon_max = [40.0, 40.0, 30.0, 30.0]
        cost_per_g = [0.00070, 0.00170, 0.00090, 0.00110]
        cost_ceiling = 1.20

        X: list[list[float]] = []
        Y: list[list[float]] = []
        while len(X) < 12:
            n_active = rng.randint(1, 2)
            active_idx = rng.sample(range(4), n_active)
            amounts = [0.0, 0.0, 0.0, 0.0]
            for idx in active_idx:
                amounts[idx] = rng.uniform(1.0, carbon_max[idx])
            cost = sum(amounts[i] * cost_per_g[i] for i in range(4))
            if cost > cost_ceiling:
                continue
            binary = [1.0 if i in active_idx else 0.0 for i in range(4)]
            # Synthetic objective: cost-per-titer-proxy
            titer_proxy = sum(amounts[i] * (0.8 if binary[i] < 0.5 else 1.0) for i in range(4))
            y = cost / (max(titer_proxy, 0.1) + 1e-3)
            X.append(amounts + binary)
            Y.append([y])

        strategy.tell(X, Y)

        candidates: list[dict] = []
        for _ in range(4):
            candidates.append(strategy.ask())

        cardinality_pass_count = sum(1 for c in candidates if c["cardinality_ok"])
        self.assertEqual(
            cardinality_pass_count,
            4,
            f"Expected 4/4 cardinality-passing candidates, "
            f"got {cardinality_pass_count}/4. Candidates: {candidates}",
        )

        # Every candidate must have 1-2 active carbons.
        for i, c in enumerate(candidates):
            self.assertGreaterEqual(c["n_active"], 1, f"candidate {i}: n_active < 1")
            self.assertLessEqual(c["n_active"], 2, f"candidate {i}: n_active > 2")

        # Cost ceiling — strict honoring (linear constraint, MIP-enforced).
        for i, c in enumerate(candidates):
            row_cost = sum(
                c["amounts"][carbons[j]] * cost_per_g[j]
                for j in range(4)
            )
            self.assertLessEqual(
                row_cost,
                cost_ceiling + 1e-6,
                f"candidate {i} cost ${row_cost:.4f}/L > ${cost_ceiling}/L",
            )


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class AdapterRegistryTests(unittest.TestCase):
    def test_entmoot_in_adapters_tuple(self) -> None:
        self.assertIn("entmoot", adapters.ADAPTERS)

    def test_get_adapter_returns_module_when_available(self) -> None:
        result = adapters.get_adapter("entmoot")
        if entmoot_strategy.is_available():
            self.assertIs(result, entmoot_strategy)
        else:
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
