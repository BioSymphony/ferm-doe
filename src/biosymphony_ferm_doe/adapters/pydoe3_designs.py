"""pyDOE3 adapter — extended k coverage and maximin LHS.

The stdlib generators in ``doe_generators`` cover the most common DoE
families exactly, but cap k at small values for Box-Behnken (k ∈ {3, 4})
and use a basic uniform-interval LHS without space-filling optimization.
The pyDOE3 library (https://pypi.org/project/pyDOE3/) provides reference
implementations that handle larger k for BBD and a maximin-criterion LHS.
This adapter routes those two families through pyDOE3 when it is
installed, while keeping our stdlib path as the fallback.

Public API:

- :func:`is_available` → bool, returns True iff pyDOE3 imports cleanly
- :func:`supported_families` → tuple of family ids this adapter handles
- :func:`generate_box_behnken_extended` (factors, n_center=3) → rows
- :func:`generate_lhs_maximin` (factors, n_runs, seed) → rows

Each generator returns rows in the same shape as the stdlib generators
(``{factor_id: value, "center_point": bool}``); the calling code in
``doe_generators`` adds ``design_run_id`` and ``run_order`` afterward.

Output rows carry the same engineering-unit decoding as the stdlib path,
so downstream consumers (analysis, doe_power, plan-wave2) treat them
identically.
"""

from __future__ import annotations

from itertools import product
from typing import Any

import pyDOE3  # noqa: F401  fail at import time if pyDOE3 missing


def is_available() -> bool:
    return True


def supported_families() -> tuple[str, ...]:
    return ("box_behnken", "latin_hypercube")


def generate_box_behnken_extended(
    factors: list[dict[str, Any]], *, n_center_points: int = 3
) -> list[dict[str, Any]]:
    """Generate a Box-Behnken design via pyDOE3 for arbitrary k ≥ 3."""
    numeric_factors = [f for f in factors if f.get("type") in {"numeric", "ordinal"}]
    k = len(numeric_factors)
    if k < 3:
        raise ValueError(f"box_behnken_requires_k_at_least_3_got_{k}")
    coded = pyDOE3.bbdesign(k, center=n_center_points)

    rows: list[dict[str, Any]] = []
    for run in coded:
        row: dict[str, Any] = {}
        is_center = True
        for factor, coded_value in zip(numeric_factors, run):
            value = _decode_three_level(factor, float(coded_value))
            row[factor["factor_id"]] = value
            if abs(coded_value) > 1e-9:
                is_center = False
        row["center_point"] = is_center
        rows.append(row)
    return rows


def generate_lhs_maximin(
    factors: list[dict[str, Any]], *, n_runs: int, seed: int | None = None
) -> list[dict[str, Any]]:
    """Latin Hypercube with maximin space-filling criterion via pyDOE3."""
    numeric_factors = [f for f in factors if f.get("type") in {"numeric", "ordinal"}]
    k = len(numeric_factors)
    if k == 0:
        raise ValueError("latin_hypercube_requires_at_least_one_numeric_factor")
    samples = pyDOE3.lhs(k, samples=n_runs, criterion="maximin", random_state=seed)

    rows: list[dict[str, Any]] = []
    for run in samples:
        row: dict[str, Any] = {}
        for factor, fraction in zip(numeric_factors, run):
            low = float(factor["low"])
            high = float(factor["high"])
            value = low + float(fraction) * (high - low)
            row[factor["factor_id"]] = round(value, 6)
        row["center_point"] = False
        rows.append(row)
    return rows


def _decode_three_level(factor: dict[str, Any], coded: float) -> float:
    low = float(factor["low"])
    high = float(factor["high"])
    if coded > 0.5:
        return high
    if coded < -0.5:
        return low
    return round((low + high) / 2, 6)


__all__ = ["is_available", "supported_families", "generate_box_behnken_extended", "generate_lhs_maximin"]
