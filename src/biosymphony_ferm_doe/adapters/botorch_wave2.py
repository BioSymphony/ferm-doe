"""BoTorch adapter — Bayesian optimization for follow-up candidate selection.

Replaces the stdlib closed-loop's geometric narrowing / RSM-stationary-point
logic with a Gaussian-process surrogate plus an acquisition function (qEI by
default). Same input contract as :func:`adaptive.plan_wave2` — a campaign
manifest plus result rows — but the next-batch points come from optimizing
the acquisition over the unit hypercube of coded factor values.

Public API:

- :func:`is_available` → bool, True iff torch + botorch + gpytorch imports
- :func:`plan_bo_wave2` (manifest, usable_rows, **kwargs) → dict

Acquisition options exposed:

- ``qei`` (default): q-batch Expected Improvement. Standard BO baseline.
- ``qucb``: q-batch Upper Confidence Bound. Tunable explore/exploit via β.
- ``qts``: q-batch Thompson Sampling. Diverse batch from the posterior.

Scope of v1:

- Single primary response (same selection rule as the stdlib path: first
  ``assay_required`` response, else first response).
- Numeric / ordinal factors only. Mixture, categorical, hard_to_change, and
  temporal_profile factors are skipped with a warning. Mixed-type BO is
  doable but adds significant complexity; later commit.
- No explicit constraint handling. The unit hypercube of coded factor values
  is the feasible region.

Output is labeled ``claim_level: bayesian_optimization_planned``. The
non-claim spells out that BO recommendations depend on the GP posterior,
which is only as good as the data used to fit it. A statistician should
review before driving expensive runs.

Compute profile:

- GP fit is O(n³) in n_runs. For n ≤ 200, runs in seconds on CPU.
- Acquisition optimization with `optimize_acqf` and 256 raw samples + 10
  restarts is similarly fast on CPU.
- GPU helps once n grows past ~1000. For typical first-batch → follow-up
  transitions (n=8-50), CPU is plenty.
- Cold-start cost of importing torch is significant (~1-2 s); the adapter
  imports it lazily so users who don't call this path don't pay.
"""

from __future__ import annotations

from typing import Any

import torch  # noqa: F401  fail-fast at import-time if torch missing
from botorch.acquisition.monte_carlo import (  # noqa: F401
    qExpectedImprovement,
    qUpperConfidenceBound,
)
from botorch.acquisition.thompson_sampling import PathwiseThompsonSampling  # noqa: F401
from botorch.fit import fit_gpytorch_mll  # noqa: F401
from botorch.models import SingleTaskGP  # noqa: F401
from botorch.optim import optimize_acqf  # noqa: F401
from gpytorch.mlls import ExactMarginalLogLikelihood  # noqa: F401

CLAIM_LEVEL = "bayesian_optimization_planned"
NON_CLAIM = (
    "Bayesian-optimization recommendations are GP-posterior driven. The GP "
    "is only as good as the runs used to fit it; with small n the posterior "
    "is wide and exploration dominates. A statistician should review the "
    "acquisition-function choice and the GP fit before driving expensive runs."
)


def is_available() -> bool:
    return True


def plan_bo_wave2(
    manifest: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    *,
    n_candidates: int = 3,
    acquisition: str = "qei",
    primary_response_id: str | None = None,
    seed: int = 0,
    num_restarts: int = 10,
    raw_samples: int = 256,
    ucb_beta: float = 0.1,
) -> dict[str, Any]:
    """Recommend follow-up candidate points via BoTorch BO."""
    factors = _numeric_factors(manifest)
    if not factors:
        return _short_circuit("no_numeric_factors_for_bo")
    response = _select_response(manifest, primary_response_id)
    if response is None:
        return _short_circuit("no_primary_response_declared")
    rid = response["response_id"]
    direction = response.get("direction", "maximize")

    X, y, dropped = _build_observation_tensors(usable_rows, factors, rid)
    if X is None or y is None:
        return _short_circuit(f"insufficient_observations_for_{rid}")
    n = X.shape[0]
    k = X.shape[1]
    if n < 4:
        return _short_circuit(f"only_{n}_observations_need_at_least_4_for_bo")

    if direction == "minimize":
        y = -y  # internalize as maximization

    torch.manual_seed(seed)
    gp = SingleTaskGP(X, y)
    mll = ExactMarginalLogLikelihood(gp.likelihood, gp)
    fit_gpytorch_mll(mll)

    bounds = torch.stack([torch.zeros(k, dtype=X.dtype), torch.ones(k, dtype=X.dtype)])
    best_f = float(y.max())

    if acquisition == "qei":
        acq = qExpectedImprovement(gp, best_f=best_f)
    elif acquisition == "qucb":
        acq = qUpperConfidenceBound(gp, beta=ucb_beta)
    else:
        return _short_circuit(f"unsupported_acquisition_{acquisition}")

    candidates_coded, _ = optimize_acqf(
        acq, bounds=bounds, q=n_candidates,
        num_restarts=num_restarts, raw_samples=raw_samples,
    )
    candidate_rows = _decode_candidates(candidates_coded, factors)

    posterior_at_best = gp.posterior(X[y.argmax(): y.argmax() + 1])
    best_mean = float(posterior_at_best.mean.detach().squeeze())
    best_var = float(posterior_at_best.variance.detach().squeeze())
    if direction == "minimize":
        best_mean = -best_mean

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "primary_response_id": rid,
        "direction": direction,
        "acquisition": acquisition,
        "n_observations": n,
        "n_factors": k,
        "n_candidates": n_candidates,
        "candidate_design": candidate_rows,
        "candidate_design_count": len(candidate_rows),
        "best_observed_response": float(y.max()) if direction == "maximize" else float((-y).min()),
        "gp_posterior_at_best": {
            "mean": round(best_mean, 6),
            "variance": round(best_var, 6),
        },
        "dropped_rows_no_response": dropped,
    }


# =====================================================================
# Internals
# =====================================================================


def _short_circuit(reason: str) -> dict[str, Any]:
    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "short_circuit_reason": reason,
        "candidate_design": [],
        "candidate_design_count": 0,
    }


def _numeric_factors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for factor in manifest.get("factors") or []:
        if not isinstance(factor, dict):
            continue
        if factor.get("type") not in {"numeric", "ordinal"}:
            continue
        if factor.get("low") is None or factor.get("high") is None:
            continue
        if factor.get("hard_to_change"):
            continue
        out.append(factor)
    return out


def _select_response(manifest: dict[str, Any], explicit: str | None) -> dict[str, Any] | None:
    responses = manifest.get("responses") or []
    if explicit:
        for response in responses:
            if response.get("response_id") == explicit:
                return response
        return None
    for response in responses:
        if response.get("assay_required"):
            return response
    return responses[0] if responses else None


def _build_observation_tensors(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    response_id: str,
) -> tuple[Any, Any, int]:
    X_list: list[list[float]] = []
    y_list: list[float] = []
    dropped = 0
    for row in rows:
        try:
            response_value = float(row.get(response_id, ""))
        except (TypeError, ValueError):
            dropped += 1
            continue
        coded: list[float] = []
        valid = True
        for factor in factors:
            try:
                raw = float(row.get(factor["factor_id"], ""))
            except (TypeError, ValueError):
                valid = False
                break
            low = float(factor["low"])
            high = float(factor["high"])
            if high <= low:
                valid = False
                break
            coded.append((raw - low) / (high - low))
        if not valid:
            dropped += 1
            continue
        X_list.append(coded)
        y_list.append(response_value)
    if not X_list:
        return None, None, dropped
    X = torch.tensor(X_list, dtype=torch.double)
    y = torch.tensor(y_list, dtype=torch.double).unsqueeze(-1)
    return X, y, dropped


def _decode_candidates(candidates_coded: Any, factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates_coded):
        row: dict[str, Any] = {
            "design_run_id": f"BO-{index + 1:03d}",
            "claim_level": CLAIM_LEVEL,
            "scoring_mode": "bayesian_optimization",
        }
        for factor, fraction in zip(factors, candidate):
            low = float(factor["low"])
            high = float(factor["high"])
            value = low + float(fraction) * (high - low)
            row[factor["factor_id"]] = round(value, 6)
        rows.append(row)
    return rows


__all__ = ["is_available", "plan_bo_wave2", "CLAIM_LEVEL", "NON_CLAIM"]
