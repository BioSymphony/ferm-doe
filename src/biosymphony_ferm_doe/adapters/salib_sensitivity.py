"""SALib adapter — global sensitivity analysis for DoE responses.

Adds variance-based and moment-independent sensitivity indices on top of
the OLS effect estimates the stdlib path already produces. Useful as a
second opinion when calling "active factors" from a screening design,
and as the right tool when factor counts grow past what a Plackett-Burman
plot can usefully visualize.

Three families exposed:

- ``pawn_indices`` — model-free, works on **any** (X, Y) data, including
  designs not built for variance decomposition (PB, fractional factorial,
  CCD, BBD, custom). The right default for public planning fixtures because it does
  not constrain how the campaign sampled its space.
- ``delta_indices`` — moment-independent (Borgonovo's delta); also works
  on arbitrary (X, Y). Reports both delta and a first-order Sobol estimate.
- ``sobol_indices`` — classical variance decomposition (S1 / ST / S2).
  Requires the design to be a Saltelli sample; use ``saltelli_sample``
  to generate one.

All public functions accept the engine's ``factors`` list-of-dicts
shape and return plain-Python dicts keyed by ``factor_id``, so the
caller never has to look at SALib's internal problem structure.

Public API:

- :func:`pawn_indices` (factors, X, Y, S=10) → dict[factor_id, dict]
- :func:`delta_indices` (factors, X, Y, num_resamples=100) → dict[factor_id, dict]
- :func:`sobol_indices` (factors, Y, calc_second_order=False) → dict[factor_id, dict]
- :func:`saltelli_sample` (factors, n_base, calc_second_order=False) → np.ndarray
- :func:`is_available` () → True
"""

from __future__ import annotations

from typing import Any

import numpy as np  # noqa: F401  fail at import time if numpy missing
from SALib.analyze import delta as _delta
from SALib.analyze import pawn as _pawn
from SALib.analyze import sobol as _sobol
from SALib.sample import sobol as _sobol_sample


def _make_problem(factors: list[dict[str, Any]]) -> dict[str, Any]:
    names: list[str] = []
    bounds: list[list[float]] = []
    for factor in factors:
        factor_id = factor.get("factor_id") or factor.get("name")
        if factor_id is None:
            raise ValueError("factor missing factor_id / name")
        low = factor.get("low", factor.get("min"))
        high = factor.get("high", factor.get("max"))
        if low is None or high is None:
            raise ValueError(f"factor {factor_id} missing low/high (or min/max) bounds")
        names.append(str(factor_id))
        bounds.append([float(low), float(high)])
    return {"num_vars": len(names), "names": names, "bounds": bounds}


def _to_array(X: Any, n_factors: int) -> np.ndarray:
    arr = np.asarray(X, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != n_factors:
        raise ValueError(f"X must be shape (n_runs, {n_factors}); got {arr.shape}")
    return arr


def pawn_indices(factors: list[dict[str, Any]], X: Any, Y: Any, S: int = 10) -> dict[str, dict[str, float]]:
    """PAWN sensitivity for an arbitrary (X, Y) design.

    Returns ``{factor_id: {"mean": float, "median": float, "min": float, "max": float, "cv": float}}``.
    Larger ``mean``/``median`` => stronger first-order effect. ``S`` is the
    number of conditioning slices (10-20 is typical).
    """
    problem = _make_problem(factors)
    X_arr = _to_array(X, problem["num_vars"])
    Y_arr = np.asarray(Y, dtype=float).ravel()
    if Y_arr.shape[0] != X_arr.shape[0]:
        raise ValueError(f"Y length {Y_arr.shape[0]} does not match X rows {X_arr.shape[0]}")
    raw = _pawn.analyze(problem, X_arr, Y_arr, S=S, print_to_console=False)
    out: dict[str, dict[str, float]] = {}
    for index, name in enumerate(problem["names"]):
        out[name] = {
            "mean": float(raw["mean"][index]),
            "median": float(raw["median"][index]),
            "min": float(raw["minimum"][index]),
            "max": float(raw["maximum"][index]),
            "cv": float(raw["CV"][index]),
        }
    return out


def delta_indices(factors: list[dict[str, Any]], X: Any, Y: Any, num_resamples: int = 100) -> dict[str, dict[str, float]]:
    """Borgonovo's delta + first-order Sobol estimate for arbitrary (X, Y).

    Returns ``{factor_id: {"delta": float, "delta_conf": float, "S1": float, "S1_conf": float}}``.
    Confidence intervals come from bootstrap resampling at ``num_resamples``.
    """
    problem = _make_problem(factors)
    X_arr = _to_array(X, problem["num_vars"])
    Y_arr = np.asarray(Y, dtype=float).ravel()
    if Y_arr.shape[0] != X_arr.shape[0]:
        raise ValueError(f"Y length {Y_arr.shape[0]} does not match X rows {X_arr.shape[0]}")
    raw = _delta.analyze(problem, X_arr, Y_arr, num_resamples=num_resamples, print_to_console=False)
    out: dict[str, dict[str, float]] = {}
    for index, name in enumerate(problem["names"]):
        out[name] = {
            "delta": float(raw["delta"][index]),
            "delta_conf": float(raw["delta_conf"][index]),
            "S1": float(raw["S1"][index]),
            "S1_conf": float(raw["S1_conf"][index]),
        }
    return out


def saltelli_sample(factors: list[dict[str, Any]], n_base: int, calc_second_order: bool = False) -> np.ndarray:
    """Generate a Saltelli sample suitable for ``sobol_indices``.

    Returns an array of shape ``(n_base * (2D + 2), D)`` when
    ``calc_second_order`` is True, else ``(n_base * (D + 2), D)``.
    """
    problem = _make_problem(factors)
    return _sobol_sample.sample(problem, n_base, calc_second_order=calc_second_order)


def sobol_indices(factors: list[dict[str, Any]], Y: Any, calc_second_order: bool = False) -> dict[str, dict[str, float]]:
    """Classical Sobol variance decomposition. Requires a Saltelli-sampled design.

    Returns ``{factor_id: {"S1": float, "S1_conf": float, "ST": float, "ST_conf": float}}``.
    Caller is responsible for evaluating ``Y`` on the rows produced by
    :func:`saltelli_sample` with the same ``calc_second_order`` flag.
    """
    problem = _make_problem(factors)
    Y_arr = np.asarray(Y, dtype=float).ravel()
    raw = _sobol.analyze(problem, Y_arr, calc_second_order=calc_second_order, print_to_console=False)
    out: dict[str, dict[str, float]] = {}
    for index, name in enumerate(problem["names"]):
        out[name] = {
            "S1": float(raw["S1"][index]),
            "S1_conf": float(raw["S1_conf"][index]),
            "ST": float(raw["ST"][index]),
            "ST_conf": float(raw["ST_conf"][index]),
        }
    return out


def is_available() -> bool:
    return True


__all__ = ["pawn_indices", "delta_indices", "sobol_indices", "saltelli_sample", "is_available"]
