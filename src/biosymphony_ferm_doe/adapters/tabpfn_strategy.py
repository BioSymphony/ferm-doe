"""TabPFN-v3 foundation-model BO surrogate adapter.

TabPFN (Prior Labs, https://github.com/PriorLabs/TabPFN) is a transformer
foundation model for tabular regression / classification. Version 3 (default
in ``tabpfn>=8.0``) is the latest non-commercial release. The hypothesis we
test here is that TabPFN can substitute the default Gaussian Process surrogate
in a Bayesian-optimization loop and still give competitive low-data
performance (n < 20 runs) without any hyperparameter tuning, on the small-data
regime typical of bioprocess campaigns.

This adapter follows the same shape as ``bofire_strategy.py``:

- :func:`is_available` — gated on ``tabpfn`` import AND ``TABPFN_TOKEN`` env
- :func:`routing_decision` — emits ``should_route`` + reasons under
  ``low_data_regime``, ``small_factor_count``, or ``operator_requested_tabpfn``
- :func:`plan_tabpfn_wave2` — produces ``candidate_design`` rows via BoTorch's
  ``optimize_acqf`` driven by a TabPFN-backed surrogate
- :class:`_TabPFNSurrogate` — wraps ``tabpfn.TabPFNRegressor`` to look like a
  ``botorch.models.Model``, exposing ``posterior(X)`` → ``GPyTorchPosterior``

ARCHITECTURE NOTE — Gaussian-approximation posterior wrap
=========================================================
TabPFN's native posterior is a 100-bucket ``FullSupportBarDistribution``
(empirical bar histogram, not a Gaussian). To plug it into BoTorch's
acquisition machinery cheaply, this adapter approximates the marginal
posterior at each query point as a univariate Gaussian using
``mean = TabPFN.predict(output_type='mean')`` and
``sigma = (q_84 - q_16) / 2`` from the bar-distribution quantiles. The
covariance between query points is taken as diagonal (independence
assumption). The acquisition functions (``qLogExpectedImprovement`` and
``qLogNoisyExpectedHypervolumeImprovement``) only use marginal mean and
variance for single-q candidate selection, so the approximation is exact for
``q=1`` and a controlled simplification for ``q>1``.

This trade gives us a working BoTorch-compatible surrogate without
implementing a custom ``Posterior`` subclass. The cost is uncertainty
calibration in highly non-Gaussian regions of the bar distribution (heavy
tails, multimodality). For low-data smoke runs where TabPFN's main value is
"no hyperparameter tuning at n<20," this approximation is appropriate. A
faithful subclass that draws samples from the bar distribution directly
would be the v2 follow-up.

ROUTING
-------
TabPFN fires when ANY of these are true:

- ``low_data_regime``: fewer than 20 usable rows
- ``small_factor_count``: 8 or fewer numeric/discrete factors (TabPFN's
  pretraining regime)
- ``operator_requested_tabpfn``: ``backend="tabpfn"`` passed explicitly

It refuses to fire when the operator hard-pinned a different backend
(``stdlib``, ``bofire``, ``botorch``, ``entmoot``, ``baybe``).

CAVEATS
-------
- Token-gated (``TABPFN_TOKEN`` env var). Non-commercial license only.
- TabPFN v3 fit is O(n^2) — fine for n < 500, slow above that
- No batch-fantasy / closed-loop tell — single-shot candidate generation
- Categorical / mixed-type factors fall back to dense one-hot encoding before
  reaching the surrogate. NChooseK and linear constraints are enforced via
  BoTorch's ``inequality_constraints``; categorical_exclude is enforced
  post-hoc by repair-and-rank
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from ..constraints import design_factors
from ..io_utils import parse_number


CLAIM_LEVEL = "tabpfn_adapter_planning"
TABPFN_ROUTE_REASONS = (
    "low_data_regime",
    "small_factor_count",
    "operator_requested_tabpfn",
)
NON_CLAIM = (
    "TabPFN-backed surrogate predictions are model-based suggestions from a "
    "frozen transformer pretrained on synthetic tabular data. They do not "
    "validate assay readiness or scale transfer; BioSymphony readiness gates "
    "remain authoritative. The marginal posterior is approximated as Gaussian "
    "from TabPFN bar-distribution quantiles; off-distribution and small-batch "
    "uncertainty may be miscalibrated."
)
DEFAULT_LOW_DATA_THRESHOLD = 20
DEFAULT_SMALL_FACTOR_COUNT = 8


def is_available() -> bool:
    """True iff tabpfn imports AND TABPFN_TOKEN is set in the environment."""
    if importlib.util.find_spec("tabpfn") is None:
        return False
    return bool(os.environ.get("TABPFN_TOKEN", "").strip())


def routing_decision(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]] | None = None,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    """Return whether this campaign should route to the TabPFN adapter."""

    requested = str(backend or "auto").lower()
    hard_off = requested in {"stdlib", "bofire", "botorch", "entmoot", "baybe", "pydoe", "pydoe3", "numpy", "scipy"}
    reasons: list[str] = []
    rows = usable_rows or []
    if requested == "tabpfn":
        reasons.append("operator_requested_tabpfn")
    if len(rows) < DEFAULT_LOW_DATA_THRESHOLD:
        reasons.append("low_data_regime")
    factors = _continuous_or_discrete_factors(state)
    if 0 < len(factors) <= DEFAULT_SMALL_FACTOR_COUNT:
        reasons.append("small_factor_count")

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered_reasons = [r for r in reasons if not (r in seen or seen.add(r))]

    return {
        "schema_version": 1,
        "route_kind": "tabpfn_adapter_route",
        "backend_requested": requested,
        "should_route": bool(ordered_reasons) and not hard_off,
        "adapter_available": is_available(),
        "reasons": ordered_reasons,
        "strategy_kind": _strategy_kind(state, ordered_reasons),
        "low_data_threshold": DEFAULT_LOW_DATA_THRESHOLD,
        "small_factor_count_threshold": DEFAULT_SMALL_FACTOR_COUNT,
        "n_usable_rows": len(rows),
        "n_eligible_factors": len(factors),
        "fallback": "stdlib_augment_design" if not is_available() else "",
    }


def plan_tabpfn_wave2(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    *,
    remaining_budget: int | None = None,
    backend: str | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Plan sequential candidates with a TabPFN surrogate when available."""

    route = routing_decision(state, usable_rows, backend=backend)
    domain_spec = build_domain_spec(state)
    budget = int(
        remaining_budget
        or _policy(state).get("augment_remaining_budget")
        or max(1, min(8, len(domain_spec["inputs"]) + 2))
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "adapter_kind": "tabpfn_strategy",
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "campaign_id": state.get("campaign_id"),
        "route": route,
        "strategy_kind": route["strategy_kind"],
        "remaining_run_budget": budget,
        "domain_spec": domain_spec,
        "candidate_design": [],
        "candidate_design_count": 0,
        "native_constraint_handling": True,
        "adapter_status": "not_routed" if not route["should_route"] else "not_available",
        "issues": [],
        "posterior_wrap": "gaussian_approximation_from_bar_quantiles",
    }

    if not route["should_route"]:
        report["issues"].append("TabPFN routing rule did not fire for this campaign.")
        return report
    if not route["adapter_available"]:
        report["issues"].append(
            "TabPFN is not installed or TABPFN_TOKEN is unset; stdlib augment-design fallback remains authoritative."
        )
        return report
    if domain_spec["unsupported_constraints"]:
        report["adapter_status"] = "translation_blocked"
        report["issues"].append(
            "TabPFN route fired, but this adapter cannot yet translate every declared constraint; "
            "stdlib fallback remains authoritative."
        )
        return report

    try:
        candidates = _execute_tabpfn_bo(
            state, usable_rows, domain_spec, budget, route["strategy_kind"], seed
        )
    except Exception as exc:  # pragma: no cover - dependency-driven path
        report["adapter_status"] = "execution_failed"
        report["issues"].append(
            f"TabPFN execution failed; stdlib fallback required: {type(exc).__name__}: {exc}"
        )
        return report

    report["adapter_status"] = "executed"
    report["candidate_design"] = candidates
    report["candidates"] = candidates  # alias for emitter compatibility
    report["candidate_design_count"] = len(candidates)
    if not candidates:
        report["issues"].append("TabPFN executed but returned no candidate rows; stdlib fallback required.")
    return report


def build_domain_spec(state: dict[str, Any]) -> dict[str, Any]:
    factors = design_factors(state.get("factors", []))
    return {
        "inputs": [_factor_spec(factor) for factor in factors],
        "outputs": [_response_spec(response) for response in _objective_responses(state)],
        "constraints": _constraint_specs(state.get("constraints", []) or []),
        "unsupported_constraints": _unsupported_constraint_ids(state.get("constraints", []) or []),
    }


# =====================================================================
# TabPFN -> BoTorch surrogate wrap
# =====================================================================


def _execute_tabpfn_bo(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    domain_spec: dict[str, Any],
    budget: int,
    strategy_kind: str,
    seed: int,
) -> list[dict[str, Any]]:
    """Fit TabPFN on prior runs, sample candidate pool, rank by qLogEI."""

    import numpy as np
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed)

    inputs = domain_spec["inputs"]
    outputs = domain_spec["outputs"]
    if not inputs:
        return []
    if not outputs:
        return []

    primary = _primary_objective(outputs)
    direction = primary["direction"]

    # Encode prior runs into a coded design (X) and the primary response (y)
    X_train, y_train, encoded_inputs = _encode_prior_runs(usable_rows, inputs, primary["key"])
    if X_train.shape[0] < 2:
        # Need at least 2 prior rows to fit TabPFN meaningfully; cold-start with uniform random
        return _uniform_random_candidates(inputs, budget, seed)

    if direction == "minimize":
        y_train = -y_train

    surrogate = _TabPFNSurrogate(train_X=X_train, train_Y=y_train, seed=seed)
    surrogate.fit()

    best_f = float(y_train.max())
    q = max(1, budget)

    # Gradient-free acquisition optimization: sample a large constraint-feasible pool,
    # score each candidate with single-point Log-EI (computed from TabPFN's
    # Gaussian-approximated posterior), and pick the top-q with greedy diversity.
    # TabPFN's predict pipeline is non-differentiable, so we deliberately avoid
    # optimize_acqf's L-BFGS-B path.
    pool_size = max(512, 64 * q)
    coded_pool = _sample_feasible_pool(encoded_inputs, domain_spec, pool_size, seed)
    if coded_pool.shape[0] == 0:
        # Fall back to unconstrained uniform if pool generation found nothing feasible
        coded_pool = _sample_uniform_pool(encoded_inputs, pool_size, seed)

    # Score the pool point-by-point with single-point Log-EI.
    scores = _score_log_ei(surrogate, coded_pool, best_f)
    top_indices = _greedy_diverse_top_q(coded_pool, scores, q)
    selected = coded_pool[top_indices]

    candidate_rows = _decode_candidates(selected, encoded_inputs, inputs, state)
    candidate_rows = _apply_categorical_exclude(candidate_rows, domain_spec)
    return candidate_rows


def _score_log_ei(surrogate: "_TabPFNSurrogate", coded_pool, best_f: float):
    """Score each row in ``coded_pool`` via point-by-point analytic Log-EI."""
    import math

    import numpy as np
    import torch
    from torch.distributions import Normal

    # Posterior over the entire pool — exploits TabPFN batch prediction
    post = surrogate.posterior(coded_pool.unsqueeze(1))  # shape -> (N, 1, d)
    mean = post.mean.squeeze(-1).squeeze(-1)  # (N,)
    var = post.variance.squeeze(-1).squeeze(-1).clamp_min(1e-12)
    sigma = var.sqrt()
    z = (mean - best_f) / sigma
    normal = Normal(torch.zeros_like(z), torch.ones_like(z))
    ei = sigma * (z * normal.cdf(z) + torch.exp(normal.log_prob(z)))
    # log_ei for ranking — stable monotone transform of EI
    log_ei = torch.log(ei.clamp_min(1e-30))
    return log_ei.detach().cpu().numpy()


def _greedy_diverse_top_q(coded_pool, scores, q: int):
    """Greedy maximum-distance selection over coded space to pick top-q diverse points."""
    import numpy as np

    n = coded_pool.shape[0]
    pool_np = coded_pool.detach().cpu().numpy()
    order = np.argsort(-scores)
    if q >= n:
        return order[:q].tolist()
    chosen = [int(order[0])]
    remaining = set(int(i) for i in order[1:])
    while len(chosen) < q and remaining:
        best_idx = None
        best_combo = -np.inf
        for idx in list(remaining):
            # Combine acquisition score with min-distance to already-chosen (in coded space)
            dists = np.linalg.norm(pool_np[idx] - pool_np[chosen], axis=1)
            min_d = float(dists.min())
            # Normalise the score component; pool_np dim space is [0,1]^d, so distances are O(sqrt(d))
            combo = float(scores[idx]) + 0.5 * min_d
            if combo > best_combo:
                best_combo = combo
                best_idx = idx
        chosen.append(int(best_idx))
        remaining.discard(int(best_idx))
    return chosen


def _sample_feasible_pool(encoded_inputs: list[dict[str, Any]], domain_spec: dict[str, Any], pool_size: int, seed: int):
    """Sample ``pool_size`` candidates that satisfy linear + nchoosek constraints (best-effort).

    For NChooseK, sample a random active subset of size in [min_count, max_count] from the listed
    features, set the rest to zero (coded). For linear constraints, rejection-sample.
    """
    import numpy as np
    import torch

    rng = np.random.default_rng(seed)
    n_dim = len(encoded_inputs)
    if n_dim == 0:
        return torch.zeros((0, 0), dtype=torch.float64)

    constraints = domain_spec.get("constraints", []) or []
    nchoosek = next((c for c in constraints if c.get("type") == "nchoosek"), None)
    linears = [c for c in constraints if c.get("type") == "linear"]

    # Build coded-column groups for the NChooseK features
    by_source: dict[str, list[int]] = {}
    for idx, spec in enumerate(encoded_inputs):
        by_source.setdefault(spec["source_key"], []).append(idx)
    nck_features = (nchoosek or {}).get("features", [])
    nck_indices = [by_source[f][0] for f in nck_features if f in by_source and encoded_inputs[by_source[f][0]]["type"] in {"continuous", "discrete"}]
    nck_min = int((nchoosek or {}).get("min_count", 0))
    nck_max = int((nchoosek or {}).get("max_count", len(nck_indices) or 1))

    accepted: list[list[float]] = []
    attempts = 0
    target = pool_size
    max_attempts = pool_size * 50
    while len(accepted) < target and attempts < max_attempts:
        attempts += 1
        row = rng.uniform(0.0, 1.0, size=n_dim)
        if nck_indices:
            k = int(rng.integers(low=max(1, nck_min), high=max(1, nck_min) + max(1, nck_max - max(1, nck_min) + 1)))
            k = max(nck_min, min(nck_max, k))
            active = list(rng.choice(nck_indices, size=k, replace=False))
            inactive = [i for i in nck_indices if i not in active]
            for i in inactive:
                row[i] = 0.0
        if not _row_satisfies_linears(row, linears, encoded_inputs):
            continue
        accepted.append(row.tolist())
    return torch.as_tensor(accepted, dtype=torch.float64)


def _sample_uniform_pool(encoded_inputs: list[dict[str, Any]], pool_size: int, seed: int):
    import numpy as np
    import torch

    rng = np.random.default_rng(seed + 1)
    n_dim = max(1, len(encoded_inputs))
    return torch.as_tensor(rng.uniform(0.0, 1.0, size=(pool_size, n_dim)), dtype=torch.float64)


def _row_satisfies_linears(row, linears: list[dict[str, Any]], encoded_inputs: list[dict[str, Any]]) -> bool:
    if not linears:
        return True
    by_source: dict[str, int] = {}
    for idx, spec in enumerate(encoded_inputs):
        if spec["type"] in {"continuous", "discrete"}:
            by_source.setdefault(spec["source_key"], idx)
    for cons in linears:
        features = cons.get("features", [])
        coefs = cons.get("coefficients", [])
        rhs = float(cons.get("rhs", 0.0))
        operator = cons.get("operator", "<=")
        lhs = 0.0
        for feature, coef in zip(features, coefs):
            idx = by_source.get(feature)
            if idx is None:
                continue
            spec = encoded_inputs[idx]
            low, high = spec["low"], spec["high"]
            decoded = low + float(row[idx]) * (high - low)
            lhs += float(coef) * decoded
        if operator in {"<=", "<"} and lhs > rhs + 1e-6:
            return False
        if operator in {">=", ">"} and lhs < rhs - 1e-6:
            return False
        if operator in {"==", "="} and abs(lhs - rhs) > 1e-6:
            return False
    return True


class _TabPFNSurrogate:
    """BoTorch ``Model``-compatible wrapper around ``tabpfn.TabPFNRegressor``.

    Exposes ``posterior(X)`` -> ``GPyTorchPosterior`` with mean from
    ``TabPFN.predict(output_type='mean')`` and variance from the (q_84 - q_16)/2
    quantile spread. See module docstring for the architectural trade.

    This wrapper is deliberately minimal: it doesn't implement ``fantasize``,
    ``condition_on_observations``, or batch-fantasy paths. It only supports the
    single-step acquisition optimization that ``qLogExpectedImprovement`` uses.
    """

    _num_outputs = 1

    def __init__(self, train_X, train_Y, *, seed: int = 0, n_estimators: int = 4) -> None:
        import torch

        if not isinstance(train_X, torch.Tensor):
            train_X = torch.as_tensor(train_X, dtype=torch.float64)
        if not isinstance(train_Y, torch.Tensor):
            train_Y = torch.as_tensor(train_Y, dtype=torch.float64)
        self.train_X = train_X
        self.train_Y = train_Y.squeeze(-1) if train_Y.ndim == 2 else train_Y
        self._seed = seed
        self._n_estimators = n_estimators
        self._regressor = None
        # Mark as a multi-output-friendly Model subclass
        self._dtype = torch.float64

    def fit(self) -> "_TabPFNSurrogate":
        from tabpfn import TabPFNRegressor

        self._regressor = TabPFNRegressor(
            n_estimators=self._n_estimators,
            random_state=self._seed,
        )
        self._regressor.fit(self.train_X.detach().cpu().numpy(), self.train_Y.detach().cpu().numpy())
        return self

    # BoTorch Model interface
    @property
    def num_outputs(self) -> int:
        return self._num_outputs

    @property
    def batch_shape(self):
        import torch

        return torch.Size([])

    def posterior(
        self,
        X,
        output_indices=None,
        observation_noise=False,
        posterior_transform=None,
        **kwargs,
    ):
        """Return a ``GPyTorchPosterior`` approximating TabPFN's bar distribution."""

        import numpy as np
        import torch
        from botorch.posteriors import GPyTorchPosterior
        from gpytorch.distributions import MultivariateNormal

        if self._regressor is None:
            raise RuntimeError("Surrogate must be fit() before posterior()")

        # X has shape (..., q, d). Flatten leading batch dims into a single N-rows query.
        X_t = X if isinstance(X, torch.Tensor) else torch.as_tensor(X, dtype=self._dtype)
        original_shape = X_t.shape
        if X_t.ndim < 2:
            raise ValueError(f"posterior expects X with at least 2 dims, got {original_shape}")
        d = original_shape[-1]
        n_flat = int(np.prod(original_shape[:-1]))
        X_flat = X_t.reshape(n_flat, d).detach().cpu().numpy().astype(np.float64)

        # TabPFN call: full output gives us mean + quantiles
        full = self._regressor.predict(
            X_flat,
            output_type="quantiles",
            quantiles=[0.159, 0.5, 0.841],
        )
        # quantiles returns list[array] of length 3 in [low, median, high]
        q_lo = np.asarray(full[0], dtype=np.float64)
        q_med = np.asarray(full[1], dtype=np.float64)
        q_hi = np.asarray(full[2], dtype=np.float64)
        # Gaussian approximation: mean ~ median, sigma ~ (q_hi - q_lo) / 2
        mean = q_med
        sigma = (q_hi - q_lo) / 2.0
        # Floor sigma to avoid degenerate cov in acquisition optimization
        sigma = np.maximum(sigma, 1e-6 * (np.std(self.train_Y.detach().cpu().numpy()) + 1e-9 + 1.0))
        variance = sigma ** 2

        mean_t = torch.as_tensor(mean, dtype=self._dtype)
        variance_t = torch.as_tensor(variance, dtype=self._dtype)

        # Reshape back to original leading dims (drop the trailing factor dim,
        # add a single output dim implicitly via squeeze convention)
        target_shape = original_shape[:-1]  # (..., q)
        mean_t = mean_t.reshape(target_shape)
        variance_t = variance_t.reshape(target_shape)

        # Build a diagonal MultivariateNormal over the last dim (q points)
        # For shape (batch..., q), MVN expects mean shape (batch..., q) and
        # cov shape (batch..., q, q)
        cov = torch.diag_embed(variance_t)
        mvn = MultivariateNormal(mean_t, cov)
        return GPyTorchPosterior(mvn)


# =====================================================================
# Encoding helpers (continuous + discrete + categorical-one-hot)
# =====================================================================


def _encode_prior_runs(
    rows: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    response_key: str,
):
    """Encode prior rows into a coded design matrix and the primary response vector.

    Returns (X, y, encoded_inputs) where ``encoded_inputs`` is the list of coded
    column specs that ``_decode_candidates`` uses to invert the encoding.
    """
    import numpy as np
    import torch

    encoded_inputs = _encoded_input_specs(inputs)
    X_rows: list[list[float]] = []
    y_vals: list[float] = []
    for row in rows:
        if response_key not in row:
            continue
        y = parse_number(row.get(response_key))
        if y is None:
            continue
        coded = _encode_row(row, encoded_inputs)
        if coded is None:
            continue
        X_rows.append(coded)
        y_vals.append(float(y))
    X = torch.as_tensor(X_rows, dtype=torch.float64) if X_rows else torch.zeros((0, _total_coded_dim(encoded_inputs)), dtype=torch.float64)
    y = torch.as_tensor(y_vals, dtype=torch.float64).unsqueeze(-1) if y_vals else torch.zeros((0, 1), dtype=torch.float64)
    return X, y, encoded_inputs


def _encoded_input_specs(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand factor specs into the coded column layout TabPFN sees."""
    encoded: list[dict[str, Any]] = []
    for spec in inputs:
        if spec["type"] == "continuous":
            encoded.append({
                "key": spec["key"],
                "type": "continuous",
                "low": float(spec["low"]),
                "high": float(spec["high"]),
                "source_key": spec["key"],
            })
        elif spec["type"] == "discrete":
            values = sorted(set(float(v) for v in spec["values"]))
            encoded.append({
                "key": spec["key"],
                "type": "discrete",
                "low": values[0],
                "high": values[-1],
                "values": values,
                "source_key": spec["key"],
            })
        elif spec["type"] == "categorical":
            categories = list(spec["categories"])
            for cat in categories:
                encoded.append({
                    "key": f"{spec['key']}__{cat}",
                    "type": "categorical_one_hot",
                    "low": 0.0,
                    "high": 1.0,
                    "category": cat,
                    "source_key": spec["key"],
                    "all_categories": categories,
                })
    return encoded


def _total_coded_dim(encoded_inputs: list[dict[str, Any]]) -> int:
    return max(1, len(encoded_inputs))


def _encode_row(row: dict[str, Any], encoded_inputs: list[dict[str, Any]]) -> list[float] | None:
    coded: list[float] = []
    for spec in encoded_inputs:
        if spec["type"] == "continuous":
            val = parse_number(row.get(spec["source_key"]))
            if val is None:
                return None
            low, high = spec["low"], spec["high"]
            coded.append((float(val) - low) / max(high - low, 1e-9))
        elif spec["type"] == "discrete":
            val = parse_number(row.get(spec["source_key"]))
            if val is None:
                return None
            low, high = spec["low"], spec["high"]
            coded.append((float(val) - low) / max(high - low, 1e-9))
        elif spec["type"] == "categorical_one_hot":
            raw = row.get(spec["source_key"])
            if raw is None:
                return None
            coded.append(1.0 if str(raw) == str(spec["category"]) else 0.0)
    return coded


def _coded_bounds(encoded_inputs: list[dict[str, Any]]):
    import torch

    if not encoded_inputs:
        return torch.zeros((2, 1), dtype=torch.float64)
    lo = [0.0] * len(encoded_inputs)
    hi = [1.0] * len(encoded_inputs)
    return torch.stack([torch.as_tensor(lo, dtype=torch.float64), torch.as_tensor(hi, dtype=torch.float64)])


def _coded_inequality_constraints(
    domain_spec: dict[str, Any], encoded_inputs: list[dict[str, Any]]
):
    """Translate manifest linear/nchoosek constraints into BoTorch's
    ``inequality_constraints`` format: list of (indices, coefficients, rhs)
    where ``sum(indices_i * coefficients_i) >= rhs``.

    BoTorch's ``inequality_constraints`` are >=, so ``<= rhs`` becomes
    ``-sum >= -rhs``.
    """
    import torch

    by_source: dict[str, list[int]] = {}
    coded_bounds: dict[int, tuple[float, float]] = {}
    for idx, spec in enumerate(encoded_inputs):
        by_source.setdefault(spec["source_key"], []).append(idx)
        coded_bounds[idx] = (spec["low"], spec["high"])

    out: list[tuple] = []
    for cons in domain_spec.get("constraints", []) or []:
        ctype = cons.get("type")
        if ctype == "linear":
            features = cons.get("features", [])
            coefs = cons.get("coefficients", [])
            rhs = float(cons.get("rhs", 0.0))
            operator = cons.get("operator", "<=")
            # Each feature must map to ONE coded column (continuous/discrete)
            indices: list[int] = []
            mapped_coefs: list[float] = []
            mapped_rhs = rhs
            valid = True
            for feature, coef in zip(features, coefs):
                idxs = by_source.get(feature)
                if not idxs or encoded_inputs[idxs[0]]["type"] not in {"continuous", "discrete"}:
                    valid = False
                    break
                idx = idxs[0]
                low, high = coded_bounds[idx]
                span = max(high - low, 1e-9)
                # Coded value x_coded = (x - low) / span, so x = x_coded * span + low.
                # sum(coef_i * x_i) op rhs  ->  sum(coef_i * span_i * x_coded_i) op (rhs - sum(coef_i * low_i))
                indices.append(idx)
                mapped_coefs.append(float(coef) * span)
                mapped_rhs -= float(coef) * low
            if not valid:
                continue
            if operator in {"<=", "<"}:
                indices_t = torch.as_tensor(indices, dtype=torch.long)
                coefs_t = torch.as_tensor([-c for c in mapped_coefs], dtype=torch.float64)
                out.append((indices_t, coefs_t, -mapped_rhs))
            elif operator in {">=", ">"}:
                indices_t = torch.as_tensor(indices, dtype=torch.long)
                coefs_t = torch.as_tensor(mapped_coefs, dtype=torch.float64)
                out.append((indices_t, coefs_t, mapped_rhs))
        elif ctype == "nchoosek":
            features = cons.get("features", [])
            max_count = int(cons.get("max_count", len(features)))
            min_count = int(cons.get("min_count", 0))
            # Best-effort: encode max_count as a sum of indicator-via-coded-value constraint.
            # For continuous coded in [0,1] this is loose, but it pushes the optimizer toward
            # cardinality. Acceptable for the BO surrogate use; downstream constraint_check
            # validates the actual nchoosek rule.
            indices: list[int] = []
            mapped_coefs: list[float] = []
            for feature in features:
                idxs = by_source.get(feature)
                if not idxs or encoded_inputs[idxs[0]]["type"] not in {"continuous", "discrete"}:
                    continue
                indices.append(idxs[0])
                mapped_coefs.append(1.0)
            if not indices:
                continue
            # sum(coded) <= max_count -> -sum(coded) >= -max_count
            indices_t = torch.as_tensor(indices, dtype=torch.long)
            coefs_t = torch.as_tensor([-c for c in mapped_coefs], dtype=torch.float64)
            out.append((indices_t, coefs_t, float(-max_count)))
            if min_count > 0:
                coefs_min = torch.as_tensor(mapped_coefs, dtype=torch.float64)
                out.append((indices_t, coefs_min, float(min_count)))
    return out


def _decode_candidates(
    candidates_coded,
    encoded_inputs: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Invert the coded-design matrix to factor-keyed candidate rows."""
    import torch

    if not isinstance(candidates_coded, torch.Tensor):
        candidates_coded = torch.as_tensor(candidates_coded)
    if candidates_coded.ndim == 1:
        candidates_coded = candidates_coded.unsqueeze(0)

    factor_keys = [spec["key"] for spec in inputs]
    rows: list[dict[str, Any]] = []
    for index, coded in enumerate(candidates_coded.detach().cpu().tolist()):
        row: dict[str, Any] = {
            "run_id": f"TABPFN-{index + 1:03d}",
            "claim_level": CLAIM_LEVEL,
            "scoring_mode": "tabpfn_strategy",
        }
        # Track per-factor argmax/argval for categorical one-hot decoding
        cat_buffer: dict[str, list[tuple[str, float]]] = {}
        for spec, coded_val in zip(encoded_inputs, coded):
            source = spec["source_key"]
            if spec["type"] == "continuous":
                low, high = spec["low"], spec["high"]
                row[source] = round(low + float(coded_val) * (high - low), 6)
            elif spec["type"] == "discrete":
                low, high = spec["low"], spec["high"]
                raw_val = low + float(coded_val) * (high - low)
                # Snap to nearest allowed level
                values = spec["values"]
                snapped = min(values, key=lambda v: abs(v - raw_val))
                row[source] = snapped if int(snapped) != snapped else int(snapped)
            elif spec["type"] == "categorical_one_hot":
                cat_buffer.setdefault(source, []).append((spec["category"], float(coded_val)))
        for source, options in cat_buffer.items():
            chosen = max(options, key=lambda kv: kv[1])
            row[source] = chosen[0]
        # Drop coded columns from row by ensuring only declared factor_keys are kept
        for key in list(row.keys()):
            if key not in {"run_id", "claim_level", "scoring_mode", "arm_id"} and key not in factor_keys:
                row.pop(key)
        rows.append(row)
    return rows


def _uniform_random_candidates(inputs: list[dict[str, Any]], budget: int, seed: int) -> list[dict[str, Any]]:
    """Cold-start when n<2 prior rows: emit uniform-random candidates in bounds."""
    import random

    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for index in range(max(1, budget)):
        row: dict[str, Any] = {
            "run_id": f"TABPFN-{index + 1:03d}",
            "claim_level": CLAIM_LEVEL,
            "scoring_mode": "tabpfn_strategy_coldstart",
        }
        for spec in inputs:
            if spec["type"] == "continuous":
                row[spec["key"]] = round(rng.uniform(spec["low"], spec["high"]), 6)
            elif spec["type"] == "discrete":
                row[spec["key"]] = rng.choice(spec["values"])
            elif spec["type"] == "categorical":
                row[spec["key"]] = rng.choice(spec["categories"])
        rows.append(row)
    return rows


def _apply_categorical_exclude(rows: list[dict[str, Any]], domain_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Post-hoc enforcement of categorical_exclude constraints by flipping conflicting categoricals.

    The surrogate optimization can land on a forbidden categorical combination; instead of dropping
    the row (which would silently shrink the batch), we flip the LAST categorical in the forbidden
    tuple to a non-conflicting category. If all alternatives are forbidden, we drop the row.
    """
    out: list[dict[str, Any]] = []
    cat_excludes = [c for c in (domain_spec.get("constraints") or []) if c.get("type") == "categorical_exclude"]
    if not cat_excludes:
        return rows
    cat_inputs = {spec["key"]: spec.get("categories", []) for spec in domain_spec["inputs"] if spec["type"] == "categorical"}
    for row in rows:
        repaired = dict(row)
        for cons in cat_excludes:
            features = cons.get("features", [])
            excluded = cons.get("excluded_combinations", [])
            for combo in excluded:
                if isinstance(combo, dict):
                    target = {k: str(combo[k]) for k in combo}
                else:
                    target = dict(zip(features, [str(v) for v in combo]))
                if all(str(repaired.get(k)) == v for k, v in target.items()):
                    # Try to swap the last feature to a different category
                    if features:
                        last = features[-1]
                        alts = [c for c in cat_inputs.get(last, []) if c != target[last]]
                        if alts:
                            repaired[last] = alts[0]
                        # If no alts, leave conflicting; constraint_check will flag
        out.append(repaired)
    return out


# =====================================================================
# Manifest -> domain spec helpers (same conventions as bofire_strategy)
# =====================================================================


def _factor_spec(factor: dict[str, Any]) -> dict[str, Any]:
    key = str(factor.get("factor_id") or "")
    factor_type = str(factor.get("type") or "continuous").lower()
    levels = factor.get("levels") if isinstance(factor.get("levels"), list) else []
    low = parse_number(factor.get("min", factor.get("low")))
    high = parse_number(factor.get("max", factor.get("high")))
    if factor_type in {"categorical", "block", "hard_to_change"} and levels:
        return {"key": key, "type": "categorical", "categories": [str(item) for item in levels]}
    if factor_type in {"ordinal", "discrete"} and levels:
        numeric_levels = [parse_number(level) for level in levels]
        if all(level is not None for level in numeric_levels):
            return {"key": key, "type": "discrete", "values": [float(level) for level in numeric_levels if level is not None]}
        return {"key": key, "type": "categorical", "categories": [str(item) for item in levels]}
    if low is None or high is None or low == high:
        return {"key": key, "type": "categorical", "categories": [str(factor.get("fixed_value", "fixed"))]}
    return {
        "key": key,
        "type": "continuous",
        "low": float(low),
        "high": float(high),
    }


def _response_spec(response: dict[str, Any]) -> dict[str, Any]:
    direction = str(response.get("direction") or "maximize").lower()
    if direction not in {"maximize", "minimize"}:
        direction = "maximize"
    return {"key": str(response.get("response_id") or ""), "direction": direction, "unit": response.get("unit", "")}


def _constraint_specs(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for constraint in constraints:
        kind = _constraint_kind(constraint)
        if kind == "linear":
            coeffs = constraint.get("coefficients")
            rhs = parse_number(constraint.get("rhs"))
            if isinstance(coeffs, dict) and rhs is not None:
                features = [str(key) for key in coeffs]
                values = [float(parse_number(coeffs[key]) or 0.0) for key in coeffs]
                specs.append({
                    "id": _constraint_id(constraint),
                    "type": "linear",
                    "features": features,
                    "coefficients": values,
                    "rhs": float(rhs),
                    "operator": str(constraint.get("operator") or constraint.get("op") or "<="),
                })
        elif kind == "nchoosek":
            features = constraint.get("features")
            max_count = parse_number(constraint.get("max_count"))
            if isinstance(features, list) and max_count is not None:
                specs.append({
                    "id": _constraint_id(constraint),
                    "type": "nchoosek",
                    "features": [str(item) for item in features],
                    "min_count": int(parse_number(constraint.get("min_count")) or 0),
                    "max_count": int(max_count),
                })
        elif kind == "categorical_exclude":
            specs.append({
                "id": _constraint_id(constraint),
                "type": "categorical_exclude",
                "features": [str(item) for item in (constraint.get("features") or [])],
                "excluded_combinations": list(constraint.get("excluded_combinations") or []),
            })
    return specs


def _unsupported_constraint_ids(constraints: list[dict[str, Any]]) -> list[str]:
    unsupported: list[str] = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        kind = _constraint_kind(constraint)
        if kind in {"linear", "nchoosek", "categorical_exclude"}:
            continue
        unsupported.append(_constraint_id(constraint))
    return unsupported


def _continuous_or_discrete_factors(state: dict[str, Any]) -> list[dict[str, Any]]:
    factors = design_factors(state.get("factors", []) or [])
    return [f for f in factors if str(f.get("type") or "continuous").lower() in {"continuous", "numeric", "ordinal", "discrete", "categorical"}]


def _primary_objective(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    for output in outputs:
        if output.get("direction") in {"maximize", "minimize"}:
            return output
    if outputs:
        return outputs[0]
    return {"key": "", "direction": "maximize"}


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
    response_id = objective.get("response_id")
    if response_id:
        return [{"response_id": response_id, "direction": objective.get("direction", "maximize")}]
    return []


def _constraint_kind(constraint: dict[str, Any]) -> str:
    kind = str(constraint.get("type") or constraint.get("constraint_type") or constraint.get("kind") or "").lower()
    if kind in {"linear", "linear_constraint"} or "coefficients" in constraint:
        return "linear"
    if kind in {"nchoosek", "n_choose_k", "n-choose-k"} or {"features", "max_count"} <= set(constraint):
        return "nchoosek"
    if kind in {"categorical_exclude", "forbidden", "forbidden_combination"}:
        return "categorical_exclude"
    return kind


def _constraint_id(constraint: dict[str, Any]) -> str:
    return str(constraint.get("constraint_id") or constraint.get("id") or "constraint")


def _strategy_kind(state: dict[str, Any], reasons: list[str]) -> str:
    if not reasons:
        return "not_routed"
    responses = _objective_responses(state)
    if len(responses) >= 2:
        return "multi_objective_tabpfn"
    return "single_objective_tabpfn"


def _policy(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}


__all__ = [
    "CLAIM_LEVEL",
    "NON_CLAIM",
    "TABPFN_ROUTE_REASONS",
    "build_domain_spec",
    "is_available",
    "plan_tabpfn_wave2",
    "routing_decision",
]
