"""Constraint normalization and row validation for DOE candidates."""

from __future__ import annotations

from typing import Any

from .io_utils import parse_number


def design_factors(factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return factors that should appear in generated design rows."""
    excluded_roles = {"excluded", "response", "metadata", "block_only"}
    return [factor for factor in factors if str(factor.get("role", "candidate")).lower() not in excluded_roles]


def validate_design_rows(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Validate row-level factor and campaign constraints.

    The engine supports a pragmatic subset of reference DOE-style restrictions in stdlib:
    numeric bounds, categorical levels, mixture sum constraints, fixed controls,
    linear inequalities, forbidden combinations, and run exclusions.
    """
    constraints = constraints or []
    violations: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        run_id = str(row.get("run_id") or f"row_{row_index + 1}")
        for factor in design_factors(factors):
            factor_id = factor["factor_id"]
            value = row.get(factor_id)
            violations.extend(_factor_violations(run_id, factor, value))
        violations.extend(_mixture_violations(run_id, row, factors))
        for constraint in constraints:
            violations.extend(_constraint_violations(run_id, row, constraint))
    return violations


def _factor_violations(run_id: str, factor: dict[str, Any], value: Any) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    factor_id = factor["factor_id"]
    factor_type = str(factor.get("type") or "continuous").lower()
    if value in {None, ""}:
        return [_violation(run_id, "missing_factor_value", factor_id, "Factor value is missing.")]

    fixed_value = factor.get("fixed_value")
    if fixed_value not in {None, ""} and str(value) != str(fixed_value):
        issues.append(_violation(run_id, "fixed_value", factor_id, f"Expected fixed value {fixed_value}."))

    levels = [str(level) for level in factor.get("levels", [])]
    if factor_type in {"categorical", "ordinal", "block", "hard_to_change"} and levels:
        if str(value) not in levels:
            issues.append(_violation(run_id, "invalid_level", factor_id, f"Value {value} is not in allowed levels."))
        return issues

    numeric = parse_number(value)
    low = factor.get("min")
    high = factor.get("max")
    if low is not None or high is not None:
        if numeric is None:
            issues.append(_violation(run_id, "non_numeric_value", factor_id, "Numeric factor has non-numeric value."))
            return issues
        if low is not None and numeric < float(low) - 1e-9:
            issues.append(_violation(run_id, "below_min", factor_id, f"Value {numeric} is below {low}."))
        if high is not None and numeric > float(high) + 1e-9:
            issues.append(_violation(run_id, "above_max", factor_id, f"Value {numeric} is above {high}."))
    return issues


def _mixture_violations(run_id: str, row: dict[str, Any], factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for factor in factors:
        if str(factor.get("type") or "").lower() == "mixture":
            group = str(factor.get("mixture_group") or "default")
            groups.setdefault(group, []).append(factor)
    issues: list[dict[str, Any]] = []
    for group, group_factors in groups.items():
        values = [parse_number(row.get(factor["factor_id"])) for factor in group_factors]
        if any(value is None for value in values):
            issues.append(_violation(run_id, "mixture_non_numeric", group, "Mixture components must be numeric."))
            continue
        total = sum(float(value) for value in values if value is not None)
        target = parse_number(group_factors[0].get("mixture_sum")) or 1.0
        if abs(total - target) > 1e-6:
            issues.append(_violation(run_id, "mixture_sum", group, f"Mixture sum {total:.6g} does not equal {target:.6g}."))
    return issues


def _constraint_violations(run_id: str, row: dict[str, Any], constraint: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(constraint.get("type") or constraint.get("constraint_type") or "").lower()
    if kind in {"linear", "linear_constraint"}:
        return _linear_violations(run_id, row, constraint)
    if kind in {"forbidden", "forbidden_combination"}:
        return _forbidden_violations(run_id, row, constraint)
    if kind in {"fixed", "fixed_control"}:
        return _fixed_control_violations(run_id, row, constraint)
    if kind in {"exclude_run", "run_exclusion"}:
        return _run_exclusion_violations(run_id, row, constraint)
    return []


def _linear_violations(run_id: str, row: dict[str, Any], constraint: dict[str, Any]) -> list[dict[str, Any]]:
    coefficients = constraint.get("coefficients")
    if not isinstance(coefficients, dict):
        return []
    total = 0.0
    for factor_id, coefficient in coefficients.items():
        value = parse_number(row.get(factor_id))
        coeff = parse_number(coefficient)
        if value is None or coeff is None:
            return [_violation(run_id, "linear_non_numeric", str(constraint.get("constraint_id") or "linear"), "Linear constraint contains non-numeric value.")]
        total += value * coeff
    rhs = parse_number(constraint.get("rhs"))
    if rhs is None:
        return []
    op = str(constraint.get("operator") or constraint.get("op") or "<=").strip()
    ok = {
        "<=": total <= rhs + 1e-9,
        "<": total < rhs + 1e-9,
        ">=": total >= rhs - 1e-9,
        ">": total > rhs - 1e-9,
        "==": abs(total - rhs) <= 1e-6,
        "=": abs(total - rhs) <= 1e-6,
    }.get(op, True)
    if ok:
        return []
    return [_violation(run_id, "linear_constraint", str(constraint.get("constraint_id") or "linear"), f"{total:.6g} does not satisfy {op} {rhs:.6g}.")]


def _forbidden_violations(run_id: str, row: dict[str, Any], constraint: dict[str, Any]) -> list[dict[str, Any]]:
    when = constraint.get("when") or constraint.get("levels")
    if not isinstance(when, dict):
        return []
    matches = True
    for factor_id, expected in when.items():
        value = row.get(factor_id)
        if isinstance(expected, list):
            matches = matches and str(value) in {str(item) for item in expected}
        elif isinstance(expected, dict):
            low = parse_number(expected.get("min"))
            high = parse_number(expected.get("max"))
            numeric = parse_number(value)
            if numeric is None:
                matches = False
            if low is not None and numeric is not None:
                matches = matches and numeric >= low
            if high is not None and numeric is not None:
                matches = matches and numeric <= high
        else:
            matches = matches and str(value) == str(expected)
    if matches:
        return [_violation(run_id, "forbidden_combination", str(constraint.get("constraint_id") or "forbidden"), "Forbidden factor combination matched.")]
    return []


def _fixed_control_violations(run_id: str, row: dict[str, Any], constraint: dict[str, Any]) -> list[dict[str, Any]]:
    values = constraint.get("values")
    if not isinstance(values, dict):
        return []
    issues = []
    for factor_id, expected in values.items():
        if str(row.get(factor_id)) != str(expected):
            issues.append(_violation(run_id, "fixed_control", str(factor_id), f"Expected fixed control value {expected}."))
    return issues


def _run_exclusion_violations(run_id: str, row: dict[str, Any], constraint: dict[str, Any]) -> list[dict[str, Any]]:
    excluded = {str(item) for item in constraint.get("run_ids", []) if item is not None}
    if run_id in excluded:
        return [_violation(run_id, "run_exclusion", run_id, "Run id is explicitly excluded.")]
    return _forbidden_violations(run_id, row, constraint)


def _violation(run_id: str, kind: str, target: str, message: str) -> dict[str, Any]:
    return {"run_id": run_id, "kind": kind, "target": target, "message": message}
