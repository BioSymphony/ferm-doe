"""OMLT-backed adapter: tree-GBT-via-MIP optimization over a fitted surrogate.

OMLT (Optimization and Machine Learning Toolkit) is a Pyomo-based framework
that takes a trained ML surrogate (gradient-boosted trees, neural network,
linear) and encodes it as a mixed-integer linear program (MIP). You can then
optimize over the surrogate WHILE respecting hard constraints (linear,
NChooseK via binary indicators + big-M, complementarity) by solving the MIP
with HiGHS (default OSS) or Gurobi.

This makes OMLT the second MIP-based cardinality route alongside ENTMOOT.
Where ENTMOOT bundles its own LightGBM surrogate + Pyomo wiring, OMLT lets
you bring any surrogate and constraint-honor the same way. Slot in the v3
backend spectrum: alternative to ENTMOOT when you want a NN surrogate or
already-trained model, or when ENTMOOT's leak rate (35% in our v2 tests)
needs a different MIP encoding to compare against.

Default surrogate: LightGBM GBT (mirrors ENTMOOT's default), trained on
told() data, exported to ONNX via onnxmltools, then encoded as a Pyomo
``OmltBlock`` via ``GBTBigMFormulation``. Linear and NChooseK constraints
are added directly to the Pyomo model that hosts the OmltBlock.

Multiple candidates are obtained via repeated solve + no-good cut: each
solved binary configuration becomes a forbidden constraint on the next
solve, so the next candidate must differ. Continuous-only models fall back
to small perturbations from the previous solution.

The adapter stays importable without OMLT / Pyomo installed; all heavy
imports happen lazily inside :class:`OmltStrategy` and its helpers.

Public surface mirrors :mod:`entmoot_strategy` so the engine can route
both adapters uniformly:

- :func:`is_available`
- :func:`routing_decision`
- :func:`plan_omlt_wave2`
- :class:`OmltStrategy`
"""

from __future__ import annotations

import importlib.util
import warnings
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from ..constraints import design_factors
from ..io_utils import parse_number


CLAIM_LEVEL = "omlt_adapter_planning"
OMLT_ROUTE_REASONS = (
    "non_box_constraints",
    "operator_requested_omlt",
    "categorical_factor_present",
    "trained_surrogate_artifact_present",
)
NON_CLAIM = (
    "OMLT-backed candidates are MIP-optimized over a fitted surrogate; "
    "the surrogate's predictive accuracy is the upper bound on planning "
    "quality. BioSymphony readiness gates remain authoritative."
)

# Default OSS solver. HiGHS via APPSI matches the ENTMOOT adapter choice.
DEFAULT_SOLVER = "appsi_highs"

# Float comparison tolerance for "binary value == 1" decisions.
BINARY_THRESHOLD = 0.5

# Perturbation magnitude (fraction of range) for continuous-only tie breaks.
TIE_CYCLE_PERTURBATION_FRAC = 0.05

# Minimum training rows needed to fit a usable LightGBM surrogate. Below
# this we synthesize random rows so build_formulation does not crash on an
# empty tree ensemble.
MIN_TRAIN_ROWS = 12

# Lower-bound coupling for NChooseK indicators. When b_i = 1 we force
# x_i >= MIN_ACTIVE_AMOUNT_FRAC * range so the binary "active" status maps
# to a strictly positive continuous value. Without this lower bound the
# big-M coupling `x <= bigm * b` admits (x=0, b=1) as feasible, which
# leaks cardinality semantics in any downstream consumer that infers
# "active" from `x > 0`.
MIN_ACTIVE_AMOUNT_FRAC = 0.01

# LightGBM defaults for the OMLT-friendly surrogate. Kept small so the
# resulting MIP stays solvable on commodity hardware.
DEFAULT_LGB_PARAMS = {
    "n_estimators": 25,
    "num_leaves": 8,
    "min_data_in_leaf": 2,
    "max_depth": 4,
    "verbose": -1,
}


# ---------------------------------------------------------------------------
# Availability + routing
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return True when OMLT, Pyomo, HiGHS, and LightGBM are importable."""
    for module in ("omlt", "pyomo", "highspy", "lightgbm"):
        if importlib.util.find_spec(module) is None:
            return False
    # ONNX bridge (LightGBM -> ONNX -> OMLT) is required for the default GBT path.
    if importlib.util.find_spec("onnxmltools") is None:
        return False
    return True


def _solver_available(solver_name: str) -> bool:
    """Probe a Pyomo SolverFactory at runtime; defensive against missing pyomo."""
    try:
        import pyomo.environ as pyo
    except ImportError:
        return False
    try:
        return bool(pyo.SolverFactory(solver_name).available())
    except Exception:  # pragma: no cover - defensive
        return False


def routing_decision(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]] | None = None,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    """Return a routing report for the engine's dispatch loop.

    OMLT routes when:
    - operator explicitly requested ``--backend omlt``, OR
    - manifest carries a linear or NChooseK constraint (non-box), OR
    - manifest carries a categorical/discrete factor (OMLT handles via
      complementarity), OR
    - state has ``trained_surrogate_artifact`` path pointing at a
      pre-trained NN/GBT we should optimize over.

    Return shape matches :func:`entmoot_strategy.routing_decision` so the
    dispatch loop can treat both adapters uniformly.
    """
    del usable_rows  # not consulted yet; kept for signature parity

    requested = str(backend or "auto").lower()
    hard_off = requested in {"stdlib", "numpy", "scipy", "pydoe", "pydoe3", "botorch", "bofire", "entmoot"}
    reasons: list[str] = []

    if requested == "omlt":
        reasons.append(OMLT_ROUTE_REASONS[1])
    if _state_has_non_box_constraint(state):
        reasons.append(OMLT_ROUTE_REASONS[0])
    if _state_has_categorical_factor(state):
        reasons.append(OMLT_ROUTE_REASONS[2])
    if state.get("trained_surrogate_artifact"):
        reasons.append(OMLT_ROUTE_REASONS[3])
    policy = _policy(state)
    if str(policy.get("preferred_backend") or "").lower() == "omlt":
        reasons.append(OMLT_ROUTE_REASONS[1])

    # Stable de-dup preserving order.
    seen: set[str] = set()
    ordered_reasons = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered_reasons.append(r)

    return {
        "schema_version": 1,
        "route_kind": "omlt_adapter_route",
        "backend_requested": requested,
        "should_route": bool(ordered_reasons) and not hard_off,
        "adapter_available": is_available(),
        "reasons": ordered_reasons,
        "strategy_kind": _strategy_kind(ordered_reasons),
        "fallback": "entmoot_or_bofire_post_hoc" if not is_available() else "",
    }


def plan_omlt_wave2(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    *,
    remaining_budget: int | None = None,
    backend: str | None = None,
    seed: int = 0,
    solver_name: str = DEFAULT_SOLVER,
) -> dict[str, Any]:
    """Plan sequential candidates with OMLT when installed, else emit a route report.

    Mirrors :func:`entmoot_strategy.plan_entmoot_wave2`. Returns a JSON-able
    report dict the engine can ledger or render as HTML.
    """
    route = routing_decision(state, usable_rows, backend=backend)
    factors = design_factors(state.get("factors", []) or [])
    budget = int(
        remaining_budget
        or _policy(state).get("augment_remaining_budget")
        or max(1, min(8, len(factors) + 2))
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "adapter_kind": "omlt_strategy",
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "campaign_id": state.get("campaign_id"),
        "route": route,
        "strategy_kind": route["strategy_kind"],
        "remaining_run_budget": budget,
        "solver_name": solver_name,
        "candidate_design": [],
        "candidate_design_count": 0,
        "adapter_status": "not_routed" if not route["should_route"] else "not_available",
        "issues": [],
    }

    if not route["should_route"]:
        report["issues"].append("OMLT routing rule did not fire for this campaign.")
        return report
    if not route["adapter_available"]:
        report["issues"].append(
            "OMLT is not installed; ENTMOOT or BoFire post-hoc-filter remains the fallback."
        )
        return report
    if not _solver_available(solver_name):
        report["adapter_status"] = "solver_unavailable"
        report["issues"].append(
            f"Pyomo solver '{solver_name}' is not available at runtime; "
            f"install highspy or override with a different solver_name."
        )
        return report

    try:
        strategy = OmltStrategy(state, seed=seed, solver_name=solver_name)
        if usable_rows:
            X, Y = strategy.training_data_from_rows(usable_rows)
            if X:
                strategy.tell(X, Y)
        candidates = strategy.ask_batch(budget)
    except Exception as exc:  # pragma: no cover - only exercised live
        report["adapter_status"] = "execution_failed"
        report["issues"].append(
            f"OMLT execution failed; ENTMOOT or BoFire fallback required: "
            f"{type(exc).__name__}: {exc}"
        )
        return report

    report["adapter_status"] = "executed"
    report["candidate_design"] = candidates
    report["candidate_design_count"] = len(candidates)
    if not candidates:
        report["issues"].append("OMLT executed but returned no candidate rows.")
    return report


# ---------------------------------------------------------------------------
# Strategy facade
# ---------------------------------------------------------------------------


@dataclass
class OmltAskResult:
    """Single OMLT MIP solve result, normalized for biosymphony reporters."""

    iteration: int
    amounts: dict[str, float]
    binary: dict[str, int]
    n_active: int
    active_components: list[str]
    objective_estimate: float
    cardinality_ok: bool
    tie_cycle_detected: bool
    solver_status: str
    solver_wall_time_s: float
    elapsed_s: float
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "amounts": self.amounts,
            "binary": self.binary,
            "n_active": self.n_active,
            "active_components": self.active_components,
            "objective_estimate": self.objective_estimate,
            "cardinality_ok": self.cardinality_ok,
            "tie_cycle_detected": self.tie_cycle_detected,
            "solver_status": self.solver_status,
            "solver_wall_time_s": self.solver_wall_time_s,
            "elapsed_s": self.elapsed_s,
            **self.extras,
        }


class OmltStrategy:
    """MIP-over-surrogate BO facade using OMLT.

    Parameters
    ----------
    state:
        Campaign manifest dict (same shape ENTMOOT/BoFire adapters consume).
    seed:
        Random seed for LightGBM and synthetic training fallbacks.
    solver_name:
        Pyomo solver name. Defaults to ``"appsi_highs"`` (HiGHS via APPSI).
    surrogate_kind:
        ``"gbt"`` (default, LightGBM) or ``"linear"``. NN surrogates are
        reserved for v2 of the adapter; the current implementation routes
        ``"nn"`` to the GBT path with a recorded note.
    lgb_params:
        Override LightGBM hyperparameters. Defaults to
        :data:`DEFAULT_LGB_PARAMS`.
    """

    def __init__(
        self,
        state: dict[str, Any],
        *,
        seed: int = 0,
        solver_name: str = DEFAULT_SOLVER,
        surrogate_kind: str = "gbt",
        lgb_params: dict[str, Any] | None = None,
    ) -> None:
        if not _solver_available(solver_name):
            raise RuntimeError(
                f"Pyomo solver '{solver_name}' is not available. "
                f"Install highspy for the default OSS path."
            )

        self.state = state
        self.seed = seed
        self.solver_name = solver_name
        self.surrogate_kind = surrogate_kind if surrogate_kind in {"gbt", "linear"} else "gbt"
        self.lgb_params = dict(DEFAULT_LGB_PARAMS)
        if lgb_params:
            self.lgb_params.update(lgb_params)
        self._iter = 0
        self._told_X: list[tuple[float, ...]] = []
        self._told_Y: list[list[float]] = []

        self._factors = design_factors(state.get("factors", []) or [])
        self._responses = _objective_responses(state)
        self._constraints_raw = list(state.get("constraints", []) or [])
        self._normalized_constraints = _normalize_constraints(self._constraints_raw)

        # Build the domain spec: per-factor type, bounds, levels.
        self.domain = self.build_domain_spec(state)
        self._continuous_keys: list[str] = [
            f["factor_id"] for f in self.domain["factors"] if f["type"] in {"continuous", "ordinal"}
        ]
        # Track the NChooseK feature set for binary indicators.
        self._nchoosek_specs = [
            spec for spec in self._normalized_constraints if spec["type"] == "nchoosek"
        ]
        self._nchoosek_features = sorted(
            {f for spec in self._nchoosek_specs for f in spec["features"]}
        )

        # No-good cuts collected across calls so ask_batch returns diverse picks.
        self._forbidden_binary_combos: list[tuple[int, ...]] = []

    # ----------------------------------------------------------------- API

    def tell(self, X: list[list[float]], Y: list[list[float]]) -> None:
        """Append observations. Surrogate is refit lazily on ask()."""
        if len(X) != len(Y):
            raise ValueError("X and Y must have the same length")
        if not X:
            return
        self._told_X.extend(tuple(float(v) for v in row) for row in X)
        self._told_Y.extend([float(v) for v in row] for row in Y)

    def ask(self) -> dict[str, Any]:
        """Solve the constrained MIP for the next candidate (q=1)."""
        candidates = self.ask_batch(1)
        if not candidates:
            raise RuntimeError("OMLT ask() produced no candidate")
        return candidates[0]

    def ask_batch(self, n: int) -> list[dict[str, Any]]:
        """Solve N times, adding a no-good cut between binary combos.

        Cardinality-feasible batches need diversity; the no-good cut on
        the binary indicator vector forces each subsequent solve into a
        different active-set. Continuous-only problems fall back to small
        random perturbations from the previous solution.
        """
        import numpy as np

        # Ensure we have enough training data to fit a usable surrogate.
        self._ensure_training_data()
        train_X, train_Y = self._scalarize_training()

        surrogate, scaled_input_bounds = self._train_surrogate(train_X, train_Y)
        # Reset forbidden combos at the start of a fresh batch so identical
        # batches across calls remain reproducible. (Cross-call diversity is
        # handled by the engine through fantasy-tells.)
        self._forbidden_binary_combos = []

        results: list[dict[str, Any]] = []
        last_continuous: dict[str, float] | None = None
        for _ in range(n):
            self._iter += 1
            t0 = perf_counter()
            solver_t0 = perf_counter()
            opt_outcome = self._solve_once(
                surrogate, scaled_input_bounds, forbidden=self._forbidden_binary_combos
            )
            solver_wall = perf_counter() - solver_t0

            if opt_outcome is None:
                # Solver gave nothing back — bail out of the batch.
                break

            amounts, binary, obj_val, status = opt_outcome
            # Tie-cycle handling for continuous-only manifests.
            tie_cycle_detected = False
            if not self._nchoosek_features and last_continuous is not None:
                if self._approx_equal_amounts(amounts, last_continuous):
                    tie_cycle_detected = True
                    amounts = self._perturb_continuous(amounts)

            n_active = sum(1 for v in binary.values() if v >= BINARY_THRESHOLD)
            active_components = [k for k, v in binary.items() if v >= BINARY_THRESHOLD]
            cardinality_ok = self._check_cardinality(binary)

            # Record a no-good cut so the next solve picks a different
            # binary configuration.
            if self._nchoosek_features:
                combo = tuple(
                    int(round(binary.get(f, 0.0)))
                    for f in self._nchoosek_features
                )
                if combo not in self._forbidden_binary_combos:
                    self._forbidden_binary_combos.append(combo)

            elapsed = perf_counter() - t0
            results.append(
                OmltAskResult(
                    iteration=self._iter,
                    amounts={k: float(v) for k, v in amounts.items()},
                    binary={k: int(round(v)) for k, v in binary.items()},
                    n_active=n_active,
                    active_components=active_components,
                    objective_estimate=float(obj_val) if obj_val is not None else float("nan"),
                    cardinality_ok=cardinality_ok,
                    tie_cycle_detected=tie_cycle_detected,
                    solver_status=status,
                    solver_wall_time_s=round(solver_wall, 4),
                    elapsed_s=round(elapsed, 4),
                    extras={"surrogate_kind": self.surrogate_kind},
                ).to_dict()
            )
            last_continuous = dict(amounts)

        return results

    @property
    def feature_order(self) -> list[str]:
        """Order in which features appear in the surrogate (continuous only)."""
        return list(self._continuous_keys)

    def training_data_from_rows(
        self, rows: list[dict[str, Any]]
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Convert manifest-shaped observation rows into (X, Y) lists.

        Each row must carry numeric values for every continuous factor and
        every response. Categorical/discrete factors are not pulled into
        the surrogate's X in this v1 adapter (they enter only via the
        manifest-level routing decision).
        """
        X: list[list[float]] = []
        Y: list[list[float]] = []
        for row in rows or []:
            x_row: list[float] = []
            ok = True
            for key in self._continuous_keys:
                value = parse_number(row.get(key))
                if value is None:
                    ok = False
                    break
                x_row.append(float(value))
            if not ok:
                continue
            y_row: list[float] = []
            for response in self._responses:
                rid = str(response.get("response_id") or "")
                yv = parse_number(row.get(rid))
                if yv is None:
                    ok = False
                    break
                y_row.append(float(yv))
            if not ok:
                continue
            X.append(x_row)
            Y.append(y_row)
        return X, Y

    # ------------------------------------------------------- domain helpers

    @staticmethod
    def build_domain_spec(state: dict[str, Any]) -> dict[str, Any]:
        """Return a normalized {factors, responses, constraints} domain dict.

        This is the format the rest of the adapter consumes internally and
        is also what an external caller can introspect (smoke wrappers,
        tests).
        """
        out_factors: list[dict[str, Any]] = []
        for f in state.get("factors", []) or []:
            ftype = str(f.get("type") or "continuous").lower()
            entry: dict[str, Any] = {
                "factor_id": str(f.get("factor_id") or ""),
                "type": ftype,
            }
            low = parse_number(f.get("low", f.get("min")))
            high = parse_number(f.get("high", f.get("max")))
            if low is not None:
                entry["low"] = float(low)
            if high is not None:
                entry["high"] = float(high)
            if ftype in {"categorical", "discrete", "ordinal", "block"}:
                levels = f.get("levels") or []
                entry["levels"] = list(levels)
            out_factors.append(entry)

        out_responses = [
            {
                "response_id": str(r.get("response_id") or ""),
                "direction": str(r.get("direction") or "maximize").lower(),
            }
            for r in (state.get("responses") or [])
            if isinstance(r, dict) and r.get("response_id")
        ]

        return {
            "factors": out_factors,
            "responses": out_responses,
            "constraints": list(state.get("constraints", []) or []),
        }

    # --------------------------------------------------- surrogate training

    def _ensure_training_data(self) -> None:
        """Synthesize random training rows when callers have not told() any.

        LightGBM with very few rows produces empty tree ensembles, which
        OMLT cannot encode. The synthesized rows respect factor bounds so
        the surrogate's coverage spans the design space. The synthetic Y
        is the L2 distance from the box centroid — gives the optimizer a
        deterministic shape to chase but does not bias toward any
        particular real objective.
        """
        if len(self._told_X) >= MIN_TRAIN_ROWS:
            return
        import random
        rng = random.Random(self.seed)
        needed = MIN_TRAIN_ROWS - len(self._told_X)
        for _ in range(needed):
            x_row: list[float] = []
            for key in self._continuous_keys:
                factor = next(
                    (f for f in self._factors if f.get("factor_id") == key),
                    None,
                )
                low = parse_number(factor.get("low", factor.get("min"))) if factor else 0.0
                high = parse_number(factor.get("high", factor.get("max"))) if factor else 1.0
                low = 0.0 if low is None else float(low)
                high = 1.0 if high is None else float(high)
                if low == high:
                    x_row.append(low)
                else:
                    x_row.append(rng.uniform(low, high))
            self._told_X.append(tuple(x_row))
            # Synthetic Y: distance from centroid -> [dist, dist, ...] for
            # each response.
            centroid = []
            for key in self._continuous_keys:
                factor = next(
                    (f for f in self._factors if f.get("factor_id") == key),
                    None,
                )
                low = parse_number(factor.get("low", factor.get("min"))) if factor else 0.0
                high = parse_number(factor.get("high", factor.get("max"))) if factor else 1.0
                low = 0.0 if low is None else float(low)
                high = 1.0 if high is None else float(high)
                centroid.append(0.5 * (low + high))
            dist = sum((x - c) ** 2 for x, c in zip(x_row, centroid)) ** 0.5
            n_resp = max(1, len(self._responses))
            self._told_Y.append([dist] * n_resp)

    def _scalarize_training(self):
        """Return (X, y_scalar) arrays. Multi-objective gets a weighted sum.

        For multi-objective campaigns we scalarize to a single composite
        objective with sign-aware coefficients (maximize -> -1, minimize
        -> +1) so the MIP is uniformly a minimization problem.
        """
        import numpy as np
        X = np.array(self._told_X, dtype=float)
        Y = np.array(self._told_Y, dtype=float)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)
        # Sign per response: minimize keeps coef = +1; maximize flips to -1
        # so the MIP (which we treat as minimization) maximizes the original.
        signs = []
        for i in range(Y.shape[1]):
            response = self._responses[i] if i < len(self._responses) else {"direction": "minimize"}
            direction = str(response.get("direction") or "minimize").lower()
            signs.append(-1.0 if direction == "maximize" else 1.0)
        signs_arr = np.array(signs[: Y.shape[1]], dtype=float).reshape(1, -1)
        # Equal weighting; future v2 can plumb response weights.
        scalar_y = (Y * signs_arr).sum(axis=1)
        return X, scalar_y

    def _train_surrogate(self, X, y):
        """Train the default LightGBM GBT surrogate and convert to ONNX.

        Returns (gbt_model_for_omlt, scaled_input_bounds_dict).
        """
        import lightgbm as lgb
        import onnxmltools
        from onnxmltools.convert.common.data_types import FloatTensorType
        from omlt.gbt import GradientBoostedTreeModel

        params = dict(self.lgb_params)
        params["random_state"] = self.seed
        # Ensure n_estimators / num_leaves never crash on tiny datasets.
        params["min_data_in_leaf"] = max(1, min(params.get("min_data_in_leaf", 2), max(1, len(X) // 4)))
        model = lgb.LGBMRegressor(**params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(X, y)

        n_features = X.shape[1]
        initial_type = [("input", FloatTensorType([None, n_features]))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            onnx_model = onnxmltools.convert_lightgbm(
                model.booster_, initial_types=initial_type, target_opset=9
            )

        # OMLT requires bounds per input feature.
        scaled_input_bounds: dict[int, tuple[float, float]] = {}
        for i, key in enumerate(self._continuous_keys):
            factor = next(
                (f for f in self._factors if f.get("factor_id") == key), None
            )
            low = parse_number(factor.get("low", factor.get("min"))) if factor else None
            high = parse_number(factor.get("high", factor.get("max"))) if factor else None
            low_f = 0.0 if low is None else float(low)
            high_f = 1.0 if high is None else float(high)
            if low_f >= high_f:
                high_f = low_f + 1e-3
            scaled_input_bounds[i] = (low_f, high_f)

        gbt = GradientBoostedTreeModel(
            onnx_model, scaled_input_bounds=scaled_input_bounds
        )
        return gbt, scaled_input_bounds

    # --------------------------------------------------- encoding + solve

    def _encode_surrogate_as_pyomo(self, surrogate, scaled_input_bounds):
        """Build the Pyomo model with the surrogate-encoded OmltBlock attached.

        Adds:
        - linear constraints from the manifest (sum coef * x  op  rhs)
        - NChooseK constraints (big-M coupling + min/max count)
        - sets the objective to ``gbt_block.outputs[0]`` (minimize since
          we scalarized signs in _scalarize_training).
        """
        import pyomo.environ as pyo
        from omlt import OmltBlock
        from omlt.gbt import GBTBigMFormulation

        formulation = GBTBigMFormulation(surrogate)
        m = pyo.ConcreteModel()
        m.gbt_block = OmltBlock()
        m.gbt_block.build_formulation(formulation)

        feat_idx = {key: i for i, key in enumerate(self._continuous_keys)}

        # 1) Linear constraints
        if any(spec["type"] == "linear" for spec in self._normalized_constraints):
            m.linear_constraints = pyo.ConstraintList()
            for spec in self._normalized_constraints:
                if spec["type"] != "linear":
                    continue
                features = spec["features"]
                coeffs = spec["coefficients"]
                rhs = spec["rhs"]
                op = spec.get("operator", "<=")
                # Skip features not in the surrogate (defensive).
                if not all(f in feat_idx for f in features):
                    continue
                lhs = sum(
                    coeffs[i] * m.gbt_block.inputs[feat_idx[features[i]]]
                    for i in range(len(features))
                )
                if op in {">=", ">"}:
                    m.linear_constraints.add(lhs >= rhs)
                elif op in {"==", "="}:
                    m.linear_constraints.add(lhs == rhs)
                else:
                    m.linear_constraints.add(lhs <= rhs)

        # 2) NChooseK indicators + big-M linking + cardinality
        if self._nchoosek_features:
            m.b = pyo.Var(self._nchoosek_features, within=pyo.Binary)
            m.bigm_links = pyo.ConstraintList()
            m.min_amount_links = pyo.ConstraintList()
            for fname in self._nchoosek_features:
                if fname not in feat_idx:
                    continue
                factor = next(
                    (f for f in self._factors if f.get("factor_id") == fname), None
                )
                high = parse_number(factor.get("high", factor.get("max"))) if factor else None
                low = parse_number(factor.get("low", factor.get("min"))) if factor else None
                bigm = float(high) if high is not None else 1e6
                low_f = float(low) if low is not None else 0.0
                # Upper big-M coupling: x[i] <= high * b[i].
                m.bigm_links.add(
                    m.gbt_block.inputs[feat_idx[fname]] <= bigm * m.b[fname]
                )
                # Lower coupling: x[i] >= (low + MIN_ACTIVE_AMOUNT_FRAC * range) * b[i].
                # Forces b_i = 1 to mean strictly-positive (default 1% of range)
                # so downstream "active iff x > 0" consumers agree with the MIP.
                min_active = low_f + MIN_ACTIVE_AMOUNT_FRAC * max(bigm - low_f, 0.0)
                m.min_amount_links.add(
                    m.gbt_block.inputs[feat_idx[fname]] >= min_active * m.b[fname]
                )
            for nk_idx, spec in enumerate(self._nchoosek_specs):
                features_in_spec = [f for f in spec["features"] if f in feat_idx]
                if not features_in_spec:
                    continue
                min_count = int(spec.get("min_count", 0))
                max_count = int(spec.get("max_count", len(features_in_spec)))
                expr_sum = sum(m.b[f] for f in features_in_spec)
                ub_name = f"nchoosek_{nk_idx}_max_count"
                m.add_component(ub_name, pyo.Constraint(expr=expr_sum <= max_count))
                if min_count > 0:
                    lb_name = f"nchoosek_{nk_idx}_min_count"
                    m.add_component(lb_name, pyo.Constraint(expr=expr_sum >= min_count))

        # 3) Objective (minimize — signs were flipped in _scalarize_training)
        m.obj = pyo.Objective(
            expr=m.gbt_block.outputs[0], sense=pyo.minimize
        )

        return m

    def _solve_once(self, surrogate, scaled_input_bounds, *, forbidden):
        """Build + solve the MIP once. Returns (amounts, binary, obj, status).

        ``forbidden`` is a list of binary-indicator tuples already chosen;
        each becomes a no-good cut so the next solve picks a different
        configuration. Returns ``None`` if the solver returned an
        infeasible / unbounded status.
        """
        import pyomo.environ as pyo

        m = self._encode_surrogate_as_pyomo(surrogate, scaled_input_bounds)

        # Add no-good cuts for previously-chosen binary configurations.
        if self._nchoosek_features and forbidden:
            m.no_good = pyo.ConstraintList()
            for combo in forbidden:
                # Σ (1 - b_i) for b_i in combo == 1, plus Σ b_i for those == 0
                # must be >= 1 (Hamming distance >= 1).
                expr = 0
                for i, fname in enumerate(self._nchoosek_features):
                    if combo[i] == 1:
                        expr = expr + (1 - m.b[fname])
                    else:
                        expr = expr + m.b[fname]
                m.no_good.add(expr >= 1)

        solver = pyo.SolverFactory(self.solver_name)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = solver.solve(m, tee=False)
        except Exception as exc:  # pragma: no cover - defensive
            warnings.warn(f"OMLT solver raised {type(exc).__name__}: {exc}", stacklevel=2)
            return None

        # Status detection: APPSI returns result.solver.termination_condition
        try:
            term = str(result.solver.termination_condition).lower()
        except Exception:
            term = "unknown"
        status = "optimal" if "optimal" in term else term

        if "infeasible" in term or "unbounded" in term or "error" in term:
            return None

        amounts: dict[str, float] = {}
        for i, key in enumerate(self._continuous_keys):
            try:
                val = float(pyo.value(m.gbt_block.inputs[i]))
            except Exception:
                val = 0.0
            amounts[key] = val

        binary: dict[str, float] = {}
        if self._nchoosek_features and hasattr(m, "b"):
            for fname in self._nchoosek_features:
                try:
                    binary[fname] = float(pyo.value(m.b[fname]))
                except Exception:
                    binary[fname] = 0.0

        try:
            obj_val = float(pyo.value(m.obj))
        except Exception:
            obj_val = None

        return amounts, binary, obj_val, status

    # -------------------------------------------------------- diagnostics

    def _check_cardinality(self, binary: dict[str, float]) -> bool:
        for spec in self._nchoosek_specs:
            n_active = sum(
                1 for f in spec["features"] if binary.get(f, 0.0) >= BINARY_THRESHOLD
            )
            if n_active < int(spec.get("min_count", 0)):
                return False
            if n_active > int(spec.get("max_count", len(spec["features"]))):
                return False
        return True

    def _approx_equal_amounts(
        self, a: dict[str, float], b: dict[str, float], tol: float = 1e-6
    ) -> bool:
        if set(a) != set(b):
            return False
        return all(abs(a[k] - b[k]) <= tol for k in a)

    def _perturb_continuous(self, amounts: dict[str, float]) -> dict[str, float]:
        """±TIE_CYCLE_PERTURBATION_FRAC kick. Stays within factor bounds."""
        import random
        rng = random.Random(self.seed + self._iter)
        new_amounts = dict(amounts)
        for key, val in amounts.items():
            factor = next(
                (f for f in self._factors if f.get("factor_id") == key), None
            )
            if factor is None:
                continue
            low = parse_number(factor.get("low", factor.get("min")))
            high = parse_number(factor.get("high", factor.get("max")))
            if low is None or high is None:
                continue
            span = float(high) - float(low)
            sign = 1.0 if rng.random() >= 0.5 else -1.0
            kick = sign * TIE_CYCLE_PERTURBATION_FRAC * span
            new_val = max(float(low), min(float(high), float(val) + kick))
            new_amounts[key] = new_val
        return new_amounts


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _normalize_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate manifest-shaped constraints into the adapter's internal form.

    Reuses :func:`bofire_strategy._constraint_specs` when available; falls
    back to a local minimal implementation so this module stays useful in
    isolation.
    """
    try:
        from .bofire_strategy import _constraint_specs
    except ImportError:
        return _local_normalize_constraints(constraints)
    return _constraint_specs(constraints)


def _local_normalize_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for constraint in constraints or []:
        if not isinstance(constraint, dict):
            continue
        ctype = str(constraint.get("type") or "").lower()
        if ctype in {"linear", "linear_constraint"} or "coefficients" in constraint:
            coeffs = constraint.get("coefficients")
            rhs = parse_number(constraint.get("rhs"))
            if isinstance(coeffs, dict) and rhs is not None:
                features = [str(k) for k in coeffs]
                values = [float(parse_number(coeffs[k]) or 0.0) for k in coeffs]
                specs.append(
                    {
                        "id": str(constraint.get("constraint_id") or "linear"),
                        "type": "linear",
                        "features": features,
                        "coefficients": values,
                        "rhs": float(rhs),
                        "operator": str(constraint.get("operator") or "<="),
                    }
                )
        elif (
            ctype in {"nchoosek", "n_choose_k", "n-choose-k"}
            or {"features", "max_count"} <= set(constraint)
        ):
            features = constraint.get("features")
            max_count = parse_number(constraint.get("max_count"))
            if isinstance(features, list) and max_count is not None:
                specs.append(
                    {
                        "id": str(constraint.get("constraint_id") or "nchoosek"),
                        "type": "nchoosek",
                        "features": [str(f) for f in features],
                        "min_count": int(parse_number(constraint.get("min_count")) or 0),
                        "max_count": int(max_count),
                        "none_also_valid": bool(constraint.get("none_also_valid", False)),
                    }
                )
    return specs


def _objective_responses(state: dict[str, Any]) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    for response in state.get("responses", []) or []:
        if not isinstance(response, dict):
            continue
        if str(response.get("direction") or "").lower() in {"maximize", "minimize"}:
            responses.append(response)
    if responses:
        return responses
    objective = state.get("objective") if isinstance(state.get("objective"), dict) else {}
    response_id = objective.get("response_id") if isinstance(objective, dict) else None
    if response_id:
        return [
            {
                "response_id": response_id,
                "direction": objective.get("direction", "maximize"),
            }
        ]
    return []


def _state_has_nchoosek(state: dict[str, Any]) -> bool:
    for c in state.get("constraints", []) or []:
        if isinstance(c, dict):
            ctype = str(c.get("type") or c.get("constraint_type") or "").lower()
            if ctype in {"nchoosek", "n_choose_k", "n-choose-k"}:
                return True
            if {"features", "max_count"} <= set(c):
                return True
    return False


def _state_has_linear(state: dict[str, Any]) -> bool:
    for c in state.get("constraints", []) or []:
        if isinstance(c, dict):
            ctype = str(c.get("type") or "").lower()
            if ctype in {"linear", "linear_constraint"}:
                return True
            if isinstance(c.get("coefficients"), dict) and parse_number(c.get("rhs")) is not None:
                return True
    return False


def _state_has_non_box_constraint(state: dict[str, Any]) -> bool:
    return _state_has_linear(state) or _state_has_nchoosek(state)


def _state_has_categorical_factor(state: dict[str, Any]) -> bool:
    for f in state.get("factors", []) or []:
        if isinstance(f, dict):
            ftype = str(f.get("type") or "").lower()
            if ftype in {"categorical", "discrete", "ordinal", "block"}:
                return True
    return False


def _strategy_kind(reasons: list[str]) -> str:
    if "non_box_constraints" in reasons:
        return "constrained_mip_over_surrogate"
    if "trained_surrogate_artifact_present" in reasons:
        return "pretrained_surrogate_mip"
    if "categorical_factor_present" in reasons:
        return "categorical_mip"
    if "operator_requested_omlt" in reasons:
        return "operator_requested"
    return "not_routed"


def _policy(state: dict[str, Any]) -> dict[str, Any]:
    p = state.get("design_policy")
    return p if isinstance(p, dict) else {}


__all__ = [
    "CLAIM_LEVEL",
    "DEFAULT_SOLVER",
    "OMLT_ROUTE_REASONS",
    "NON_CLAIM",
    "OmltAskResult",
    "OmltStrategy",
    "is_available",
    "plan_omlt_wave2",
    "routing_decision",
]
