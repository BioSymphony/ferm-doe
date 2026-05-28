"""Optimization goal formulation and desirability scoring.

Builds a Derringer-Suich desirability formulation from a campaign manifest
and provides a stdlib scorer that the follow-up planner can consume to pick
augment-candidate winners across multiple responses.

Public API: :func:`formulate_goals`, :func:`evaluate_desirability`.

The formulation reads three layers of intent in order:

1. Explicit objective fields on ``responses[i]``: ``objective_lower``,
   ``objective_upper``, ``objective_target``, ``objective_shape``
   (``linear`` | ``quadratic`` | ``step``), ``objective_weight``.
2. Comparator-based thresholds in ``decision_rules[]`` whose ``scope``
   is ``response:<id>`` and whose ``threshold`` is numeric. ``ge`` /
   ``gt`` thresholds become the lower bound; ``le`` / ``lt`` thresholds
   become the upper bound.
3. The response's ``direction`` (``maximize`` | ``minimize`` | ``target``).

A response is included in the goals object only when at least one bound
can be sourced; otherwise it is skipped (and the planner falls back to
legacy single-response scoring). Composite desirability is the weighted
geometric mean: ``D = (prod d_i^w_i) ^ (1 / sum w_i)``.

Output is labeled ``claim_level: optimization_goal_formulated``. It is
*intent*, not validated optimization — a statistician should review the
bounds and shapes before driving expensive runs.
"""

from __future__ import annotations

from typing import Any, Iterable

CLAIM_LEVEL = "optimization_goal_formulated"
NON_CLAIM = (
    "Goals capture optimization intent, not validated optimization. "
    "Bounds, shapes, and weights should be reviewed by a statistician "
    "before they drive augment-candidate selection or expensive runs."
)

_VALID_SHAPES = frozenset({"linear", "quadratic", "step"})
_VALID_DIRECTIONS = frozenset({"maximize", "minimize", "target"})


def formulate_goals(manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Build a goals object from the manifest. Returns None when no response
    has sourceable bounds.
    """
    responses = manifest.get("responses") or []
    decision_rules = manifest.get("decision_rules") or []

    objectives: list[dict[str, Any]] = []
    for response in responses:
        rid = response.get("response_id")
        direction = response.get("direction", "maximize")
        if rid is None or direction not in _VALID_DIRECTIONS:
            continue
        bounds = _source_bounds(response, decision_rules, rid, direction)
        if bounds is None:
            continue
        lower, upper, target, source = bounds
        shape = response.get("objective_shape", "linear")
        if shape not in _VALID_SHAPES:
            shape = "linear"
        try:
            weight = float(response.get("objective_weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        if weight <= 0:
            weight = 1.0
        objectives.append(
            {
                "response_id": rid,
                "direction": direction,
                "lower": lower,
                "upper": upper,
                "target": target,
                "shape": shape,
                "weight": weight,
                "source": source,
            }
        )
    if not objectives:
        return None
    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "objectives": objectives,
        "constraints": _source_constraints(manifest),
        "composite": {
            "form": "weighted_geometric_mean",
            "n_objectives": len(objectives),
        },
    }


def evaluate_desirability(
    goals: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Score an observation row against the goals.

    ``observation`` may have float-typed values or strings that parse as floats.
    Returns ``{per_response, composite}``. ``composite`` is the weighted
    geometric mean of per-response desirabilities; missing values yield
    ``None`` for that response and are excluded from the composite.
    """
    per_response: list[dict[str, Any]] = []
    log_sum = 0.0
    weight_sum = 0.0
    saw_zero = False
    saw_value = False
    for objective in goals.get("objectives") or []:
        rid = objective["response_id"]
        value = _coerce_float(observation.get(rid))
        if value is None:
            per_response.append(
                {"response_id": rid, "value": None, "desirability": None, "reason": "missing_value"}
            )
            continue
        d = _desirability(value, objective)
        per_response.append({"response_id": rid, "value": value, "desirability": round(d, 6)})
        saw_value = True
        weight = float(objective.get("weight", 1.0))
        if d == 0:
            saw_zero = True
        else:
            import math

            log_sum += weight * math.log(d)
        weight_sum += weight
    if not saw_value or weight_sum == 0:
        composite: float | None = None
    elif saw_zero:
        composite = 0.0
    else:
        import math

        composite = round(math.exp(log_sum / weight_sum), 6)
    return {"per_response": per_response, "composite": composite}


# =====================================================================
# Internals
# =====================================================================


def _source_bounds(
    response: dict[str, Any],
    decision_rules: Iterable[dict[str, Any]],
    rid: str,
    direction: str,
) -> tuple[float, float, float | None, str] | None:
    explicit_lower = _coerce_float(response.get("objective_lower"))
    explicit_upper = _coerce_float(response.get("objective_upper"))
    explicit_target = _coerce_float(response.get("objective_target"))
    if explicit_lower is not None or explicit_upper is not None or explicit_target is not None:
        lower = explicit_lower
        upper = explicit_upper
        target = explicit_target
        if direction == "target" and target is None:
            return None
        if direction == "maximize":
            if upper is None and target is not None:
                upper = target
            if lower is None:
                return None
        elif direction == "minimize":
            if lower is None and target is not None:
                lower = target
            if upper is None:
                return None
        else:  # target
            if lower is None or upper is None or target is None:
                return None
        return float(lower), float(upper), target if target is None else float(target), "responses_objective_fields"

    rule_lower = None
    rule_upper = None
    for rule in decision_rules:
        scope = str(rule.get("scope", ""))
        if scope != f"response:{rid}":
            continue
        comparator = str(rule.get("comparator", "")).lower()
        threshold = _coerce_float(rule.get("threshold"))
        if threshold is None:
            continue
        if comparator in {"ge", ">=", "gt", ">"}:
            rule_lower = threshold if rule_lower is None else max(rule_lower, threshold)
        elif comparator in {"le", "<=", "lt", "<"}:
            rule_upper = threshold if rule_upper is None else min(rule_upper, threshold)
    if rule_lower is None and rule_upper is None:
        return None
    if direction == "maximize":
        if rule_lower is None:
            return None
        return float(rule_lower), float(rule_upper if rule_upper is not None else rule_lower * 10), None, "decision_rules"
    if direction == "minimize":
        if rule_upper is None:
            return None
        return float(rule_lower if rule_lower is not None else 0.0), float(rule_upper), None, "decision_rules"
    return None  # target direction needs explicit fields


def _source_constraints(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    for constraint in manifest.get("constraints") or []:
        kind = constraint.get("kind", "")
        if kind in {"data_policy"}:
            continue
        constraints.append(
            {
                "constraint_id": constraint.get("constraint_id"),
                "kind": kind,
                "description": constraint.get("description", ""),
            }
        )
    return constraints


def _desirability(value: float, objective: dict[str, Any]) -> float:
    direction = objective["direction"]
    lower = float(objective["lower"])
    upper = float(objective["upper"])
    target = objective.get("target")
    shape = objective.get("shape", "linear")
    s = _shape_exponent(shape)

    if direction == "maximize":
        if upper <= lower:
            return 1.0 if value >= upper else 0.0
        if value <= lower:
            return 0.0
        if value >= upper:
            return 1.0
        return ((value - lower) / (upper - lower)) ** s
    if direction == "minimize":
        if upper <= lower:
            return 1.0 if value <= lower else 0.0
        if value <= lower:
            return 1.0
        if value >= upper:
            return 0.0
        return ((upper - value) / (upper - lower)) ** s
    # target
    if target is None:
        return 0.0
    t = float(target)
    if value <= lower or value >= upper:
        return 0.0
    if value == t:
        return 1.0
    if value < t:
        if t <= lower:
            return 0.0
        return ((value - lower) / (t - lower)) ** s
    if upper <= t:
        return 0.0
    return ((upper - value) / (upper - t)) ** s


def _shape_exponent(shape: str) -> float:
    if shape == "linear":
        return 1.0
    if shape == "quadratic":
        return 2.0
    if shape == "step":
        return 0.0001  # near-step — values just past the bound saturate to ~1
    return 1.0


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["formulate_goals", "evaluate_desirability", "CLAIM_LEVEL", "NON_CLAIM"]
