"""Model matrix construction and reference DOE stdlib diagnostics."""

from __future__ import annotations

import itertools
import math
from typing import Any

from .constraints import design_factors, validate_design_rows
from .io_utils import format_number, parse_number


NUMERIC_TYPES = {"continuous", "discrete", "mixture"}
CATEGORICAL_TYPES = {"categorical", "ordinal", "block", "hard_to_change"}


def build_model_matrix(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    model_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an expanded numeric model matrix with deterministic coding."""
    active_factors = design_factors(factors)
    model_spec = model_spec or {}
    if not model_spec and len(active_factors) > 8:
        model_spec = {
            "interactions": False,
            "quadratics": False,
            "large_factor_fast_path": True,
        }
    include_interactions = bool(model_spec.get("interactions", True))
    include_quadratics = bool(model_spec.get("quadratics", True))
    max_interaction_order = int(model_spec.get("max_interaction_order", 2) or 2)

    columns = ["intercept"]
    encoded_by_row = [_encode_row(row, active_factors) for row in rows]
    main_columns = _main_columns(active_factors)
    columns.extend(main_columns)

    interaction_columns: list[tuple[str, str, str]] = []
    if include_interactions and max_interaction_order >= 2:
        for left, right in itertools.combinations(main_columns, 2):
            left_factor = left.split("=", 1)[0].split("^", 1)[0]
            right_factor = right.split("=", 1)[0].split("^", 1)[0]
            if left_factor == right_factor:
                continue
            name = f"{left}:{right}"
            interaction_columns.append((name, left, right))
            columns.append(name)

    quadratic_columns: list[tuple[str, str]] = []
    if include_quadratics:
        for factor in active_factors:
            if _is_numeric_factor(factor):
                factor_id = factor["factor_id"]
                name = f"{factor_id}^2"
                quadratic_columns.append((name, factor_id))
                columns.append(name)

    matrix: list[list[float]] = []
    matrix_rows: list[dict[str, Any]] = []
    for row, encoded in zip(rows, encoded_by_row):
        vector = [1.0]
        record: dict[str, Any] = {"run_id": row.get("run_id", "")}
        record["intercept"] = "1"
        for column in main_columns:
            value = encoded.get(column, 0.0)
            vector.append(value)
            record[column] = format_number(value)
        for name, left, right in interaction_columns:
            value = encoded.get(left, 0.0) * encoded.get(right, 0.0)
            vector.append(value)
            record[name] = format_number(value)
        for name, factor_id in quadratic_columns:
            value = encoded.get(factor_id, 0.0) ** 2
            vector.append(value)
            record[name] = format_number(value)
        matrix.append(vector)
        matrix_rows.append(record)

    return {
        "schema_version": 1,
        "matrix_kind": "ferm_doe_model_matrix",
        "columns": columns,
        "rows": matrix_rows,
        "matrix": matrix,
        "model_spec": {
            "intercept": True,
            "main_effects": True,
            "interactions": include_interactions,
            "quadratics": include_quadratics,
            "max_interaction_order": max_interaction_order,
        },
    }


def diagnose_design(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]] | None = None,
    model_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return design diagnostics with exact/approximate labels."""
    active_factors = design_factors(factors)
    matrix_bundle = build_model_matrix(rows, active_factors, model_spec)
    matrix = matrix_bundle["matrix"]
    columns = matrix_bundle["columns"]
    run_count = len(rows)
    term_count = len(columns)
    rank = matrix_rank(matrix)
    xtx = cross_product(matrix)
    determinant = determinant_symmetric(xtx) if run_count and term_count else 0.0
    inverse, inverse_status = inverse_or_ridge(xtx)
    prediction_variances = leverage_values(matrix, inverse) if inverse else []
    correlations = correlation_summary(matrix, columns)
    categorical_aliasing = categorical_aliasing_summary(rows, active_factors)
    variance_report = factor_variance_report(rows, active_factors)
    center_points = sum(1 for row in rows if is_center_row(row, active_factors))
    replicates = replicate_count(rows, active_factors)
    min_distance = min_scaled_distance(rows, active_factors)
    violations = validate_design_rows(rows, active_factors, constraints or [])
    d_eff = d_efficiency(determinant, run_count, term_count, rank)
    a_eff = a_efficiency(inverse, term_count, rank)
    i_eff = i_efficiency(prediction_variances, rank, term_count)
    g_eff = g_efficiency(prediction_variances, term_count, rank)
    fds = fds_summary(prediction_variances)
    underpowered = run_count < max(3, term_count)
    alias_pressure = 1.0 - min(1.0, rank / max(1, term_count))
    quality = statistical_quality(d_eff, i_eff, g_eff, alias_pressure, min_distance, violations)
    estimability = {
        "status": "full_rank" if rank == term_count else "aliased_or_underpowered",
        "estimable_terms": rank,
        "requested_terms": term_count,
        "deficient_terms": max(0, term_count - rank),
        "non_estimable_terms": non_estimable_term_names(columns, rank),
    }
    condition = condition_summary(xtx, rank, term_count)
    verdict = diagnostic_verdict(
        run_count=run_count,
        term_count=term_count,
        rank=rank,
        violations=violations,
        variance_report=variance_report,
        categorical_aliasing=categorical_aliasing,
        center_points=center_points,
        replicates=replicates,
    )
    return {
        "schema_version": 1,
        "diagnostics_kind": "ferm_doe_design_diagnostics",
        "run_count": run_count,
        "factor_count": len(active_factors),
        "model_term_count": term_count,
        "model_terms_quadratic_interaction": term_count,
        "rank": rank,
        "rank_estimate": rank,
        "estimability": estimability,
        "center_points": center_points,
        "replicate_count": replicates,
        "min_scaled_distance": round(min_distance, 4),
        "determinant_xtx": round(determinant, 6),
        "d_efficiency": round(d_eff, 4),
        "i_efficiency": round(i_eff, 4),
        "a_efficiency": round(a_eff, 4),
        "g_efficiency": round(g_eff, 4),
        "d_efficiency_proxy": round(d_eff, 4),
        "i_efficiency_proxy": round(i_eff, 4),
        "g_efficiency_proxy": round(g_eff, 4),
        "alias_pressure": round(alias_pressure, 4),
        "correlation_summary": correlations,
        "categorical_aliasing": categorical_aliasing,
        "factor_variance_report": variance_report,
        "condition": condition,
        "fds": fds,
        "prediction_variance": prediction_variance_summary(prediction_variances),
        "center_lack_of_fit": {
            "center_points": center_points,
            "replicate_count": replicates,
            "lack_of_fit_ready": center_points > 0 and replicates > 0,
            "label": "requires_center_points_and_replicates",
        },
        "simulation_assumptions": {
            "effect_size": "standardized unit effect",
            "noise_sd": 1.0,
            "power_status": "underpowered" if underpowered else "screening_power_only",
            "label": "heuristic",
        },
        "diagnostic_verdict": verdict,
        "metric_labels": {
            "rank": "exact_stdlib",
            "estimability": "exact_for_constructed_model_matrix",
            "non_estimable_terms": "approximate_rank_order_hint",
            "condition": "proxy_stdlib",
            "d_efficiency": "approximate_stdlib",
            "i_efficiency": "approximate_stdlib",
            "a_efficiency": "approximate_stdlib",
            "g_efficiency": "approximate_stdlib",
            "fds": "approximate_design_row_distribution",
            "categorical_aliasing": "cramers_v_contingency",
            "factor_variance_report": "exact_for_design_rows",
            "prediction_variance": "approximate_ridge_when_rank_deficient",
        },
        "constraint_violations": violations,
        "statistical_quality": round(quality, 4),
    }


def matrix_rows_for_csv(rows: list[dict[str, Any]], factors: list[dict[str, Any]], model_spec: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    bundle = build_model_matrix(rows, factors, model_spec)
    headers = ["run_id"] + [column for column in bundle["columns"] if column != "intercept"]
    headers.insert(1, "intercept")
    return bundle["rows"], headers


def _encode_row(row: dict[str, Any], factors: list[dict[str, Any]]) -> dict[str, float]:
    encoded: dict[str, float] = {}
    for factor in factors:
        factor_id = factor["factor_id"]
        factor_type = str(factor.get("type") or "continuous").lower()
        if factor_type in NUMERIC_TYPES:
            encoded[factor_id] = _scaled_numeric(row.get(factor_id), factor)
        elif factor_type in CATEGORICAL_TYPES:
            levels = [str(level) for level in factor.get("levels", [])]
            value = str(row.get(factor_id))
            if not levels:
                encoded[factor_id] = 0.0
            elif len(levels) <= 2:
                encoded[factor_id] = -1.0 if value == levels[0] else 1.0
            else:
                baseline = levels[0]
                for level in levels[1:]:
                    encoded[f"{factor_id}={level}"] = 1.0 if value == level else 0.0
                encoded[f"{factor_id}={baseline}"] = 0.0
        else:
            encoded[factor_id] = _scaled_numeric(row.get(factor_id), factor)
    return encoded


def _main_columns(factors: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for factor in factors:
        factor_id = factor["factor_id"]
        factor_type = str(factor.get("type") or "continuous").lower()
        levels = [str(level) for level in factor.get("levels", [])]
        if factor_type in CATEGORICAL_TYPES and len(levels) > 2:
            columns.extend(f"{factor_id}={level}" for level in levels[1:])
        else:
            columns.append(factor_id)
    return columns


def _scaled_numeric(value: Any, factor: dict[str, Any]) -> float:
    numeric = parse_number(value)
    if numeric is None:
        return 0.0
    low = factor.get("min")
    high = factor.get("max")
    if low is None or high is None:
        return numeric
    span = float(high) - float(low)
    if abs(span) < 1e-12:
        return 0.0
    return -1.0 + 2.0 * ((numeric - float(low)) / span)


def _is_numeric_factor(factor: dict[str, Any]) -> bool:
    return str(factor.get("type") or "continuous").lower() in NUMERIC_TYPES


def matrix_rank(matrix: list[list[float]], tolerance: float = 1e-9) -> int:
    if not matrix:
        return 0
    work = [row[:] for row in matrix]
    rows = len(work)
    cols = len(work[0]) if work[0] else 0
    rank = 0
    for col in range(cols):
        pivot = None
        for row in range(rank, rows):
            if abs(work[row][col]) > tolerance:
                pivot = row
                break
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][col]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row == rank:
                continue
            factor = work[row][col]
            if abs(factor) <= tolerance:
                continue
            work[row] = [value - factor * pivot_value for value, pivot_value in zip(work[row], work[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


def cross_product(matrix: list[list[float]]) -> list[list[float]]:
    if not matrix:
        return []
    cols = len(matrix[0])
    result = [[0.0 for _ in range(cols)] for _ in range(cols)]
    for row in matrix:
        for i in range(cols):
            for j in range(i, cols):
                result[i][j] += row[i] * row[j]
    for i in range(cols):
        for j in range(i):
            result[i][j] = result[j][i]
    return result


def determinant_symmetric(matrix: list[list[float]], tolerance: float = 1e-12) -> float:
    if not matrix:
        return 0.0
    work = [row[:] for row in matrix]
    n = len(work)
    det = 1.0
    sign = 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) < tolerance:
            return 0.0
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
            sign *= -1.0
        pivot_value = work[col][col]
        det *= pivot_value
        for row in range(col + 1, n):
            factor = work[row][col] / pivot_value
            for j in range(col, n):
                work[row][j] -= factor * work[col][j]
    return max(0.0, det * sign)


def inverse_or_ridge(matrix: list[list[float]], tolerance: float = 1e-9) -> tuple[list[list[float]] | None, str]:
    inverse = invert_matrix(matrix, tolerance)
    if inverse is not None:
        return inverse, "exact"
    if not matrix:
        return None, "unavailable"
    ridge = [row[:] for row in matrix]
    for i in range(len(ridge)):
        ridge[i][i] += 1e-6
    inverse = invert_matrix(ridge, tolerance)
    return inverse, "ridge_approximate" if inverse is not None else "unavailable"


def invert_matrix(matrix: list[list[float]], tolerance: float = 1e-12) -> list[list[float]] | None:
    if not matrix:
        return None
    n = len(matrix)
    work = [matrix[row][:] + [1.0 if row == col else 0.0 for col in range(n)] for row in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) < tolerance:
            return None
        work[col], work[pivot] = work[pivot], work[col]
        pivot_value = work[col][col]
        work[col] = [value / pivot_value for value in work[col]]
        for row in range(n):
            if row == col:
                continue
            factor = work[row][col]
            if abs(factor) <= tolerance:
                continue
            work[row] = [value - factor * pivot_value for value, pivot_value in zip(work[row], work[col])]
    return [row[n:] for row in work]


def leverage_values(matrix: list[list[float]], inverse: list[list[float]]) -> list[float]:
    values: list[float] = []
    for row in matrix:
        tmp = [sum(row[j] * inverse[j][k] for j in range(len(row))) for k in range(len(row))]
        values.append(max(0.0, sum(tmp[k] * row[k] for k in range(len(row)))))
    return values


def correlation_summary(matrix: list[list[float]], columns: list[str]) -> dict[str, Any]:
    if not matrix or len(columns) <= 2:
        return {"max_abs_correlation": 0.0, "top_pairs": []}
    vectors = list(zip(*matrix))
    pairs = []
    for i in range(1, len(columns)):
        for j in range(i + 1, len(columns)):
            corr = correlation(list(vectors[i]), list(vectors[j]))
            if corr is not None:
                pairs.append((abs(corr), columns[i], columns[j], corr))
    pairs.sort(reverse=True, key=lambda item: item[0])
    return {
        "max_abs_correlation": round(pairs[0][0], 4) if pairs else 0.0,
        "top_pairs": [
            {"left": left, "right": right, "correlation": round(value, 4)}
            for _, left, right, value in pairs[:8]
        ],
    }


def categorical_aliasing_summary(rows: list[dict[str, Any]], factors: list[dict[str, Any]], threshold: float = 0.8) -> dict[str, Any]:
    categorical = [factor for factor in factors if str(factor.get("type") or "").lower() in CATEGORICAL_TYPES]
    pairs = []
    for left, right in itertools.combinations(categorical, 2):
        left_id = left["factor_id"]
        right_id = right["factor_id"]
        left_values = [str(row.get(left_id, "")) for row in rows]
        right_values = [str(row.get(right_id, "")) for row in rows]
        value = cramers_v(left_values, right_values)
        pairs.append(
            {
                "left": left_id,
                "right": right_id,
                "cramers_v": round(value, 4),
                "flagged": value >= threshold,
            }
        )
    pairs.sort(key=lambda item: item["cramers_v"], reverse=True)
    return {
        "metric": "cramers_v",
        "threshold": threshold,
        "max_cramers_v": pairs[0]["cramers_v"] if pairs else 0.0,
        "flagged_pairs": [item for item in pairs if item["flagged"]],
        "top_pairs": pairs[:8],
    }


def cramers_v(left: list[str], right: list[str]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_levels = sorted(set(left))
    right_levels = sorted(set(right))
    if len(left_levels) <= 1 or len(right_levels) <= 1:
        return 0.0
    table = [[0 for _ in right_levels] for _ in left_levels]
    left_index = {value: index for index, value in enumerate(left_levels)}
    right_index = {value: index for index, value in enumerate(right_levels)}
    for lval, rval in zip(left, right):
        table[left_index[lval]][right_index[rval]] += 1
    total = float(len(left))
    row_sums = [sum(row) for row in table]
    col_sums = [sum(table[row][col] for row in range(len(left_levels))) for col in range(len(right_levels))]
    chi2 = 0.0
    for i, row_sum in enumerate(row_sums):
        for j, col_sum in enumerate(col_sums):
            expected = row_sum * col_sum / total
            if expected > 0:
                chi2 += (table[i][j] - expected) ** 2 / expected
    denom = total * max(1, min(len(left_levels) - 1, len(right_levels) - 1))
    if denom <= 0:
        return 0.0
    return min(1.0, math.sqrt(chi2 / denom))


def factor_variance_report(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    constant = []
    near_constant = []
    for factor in factors:
        factor_id = factor["factor_id"]
        values = [row.get(factor_id) for row in rows]
        unique = {str(value) for value in values}
        item: dict[str, Any] = {
            "factor_id": factor_id,
            "type": factor.get("type", ""),
            "unique_count": len(unique),
            "status": "varied",
        }
        if len(unique) <= 1:
            item["status"] = "constant"
            constant.append(factor_id)
        elif _is_numeric_factor(factor):
            scaled = [_scaled_numeric(value, factor) for value in values]
            mean = sum(scaled) / len(scaled) if scaled else 0.0
            variance = sum((value - mean) ** 2 for value in scaled) / len(scaled) if scaled else 0.0
            item["scaled_variance"] = round(variance, 6)
            if variance < 1e-4:
                item["status"] = "near_constant"
                near_constant.append(factor_id)
        items.append(item)
    return {
        "constant_factors": constant,
        "near_constant_factors": near_constant,
        "items": items,
    }


def condition_summary(xtx: list[list[float]], rank: int, term_count: int) -> dict[str, Any]:
    if not xtx or rank < term_count:
        return {"status": "rank_deficient", "condition_number_proxy": None}
    diagonal = [abs(xtx[i][i]) for i in range(min(len(xtx), len(xtx[0])))]
    positives = [value for value in diagonal if value > 1e-12]
    if not positives:
        return {"status": "unavailable", "condition_number_proxy": None}
    proxy = max(positives) / min(positives)
    return {"status": "estimated", "condition_number_proxy": round(proxy, 4)}


def non_estimable_term_names(columns: list[str], rank: int) -> list[str]:
    if rank >= len(columns):
        return []
    return columns[rank: min(len(columns), rank + 12)]


def diagnostic_verdict(
    *,
    run_count: int,
    term_count: int,
    rank: int,
    violations: list[dict[str, Any]],
    variance_report: dict[str, Any],
    categorical_aliasing: dict[str, Any],
    center_points: int,
    replicates: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if run_count < 3:
        blockers.append("Design has fewer than three rows.")
    if violations:
        blockers.append("Design has constraint violations.")
    if rank < term_count:
        warnings.append(f"Model matrix is rank deficient: {rank}/{term_count} terms estimable.")
    if variance_report.get("constant_factors"):
        warnings.append("One or more factors are constant across design rows.")
    if categorical_aliasing.get("flagged_pairs"):
        warnings.append("Categorical factors have high Cramer's V association.")
    if center_points == 0:
        warnings.append("No center points are present.")
    if replicates == 0:
        warnings.append("No replicated design points are present.")
    return {
        "status": "FAIL" if blockers else ("WARN" if warnings else "PASS"),
        "blockers": blockers,
        "warnings": warnings,
    }


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    denom = math.sqrt(sum(value * value for value in left_centered) * sum(value * value for value in right_centered))
    if denom <= 1e-12:
        return None
    return sum(a * b for a, b in zip(left_centered, right_centered)) / denom


def d_efficiency(determinant: float, run_count: int, term_count: int, rank: int) -> float:
    if run_count <= 0 or term_count <= 0 or rank < term_count or determinant <= 0:
        return min(0.6, rank / max(1, term_count))
    value = determinant ** (1.0 / term_count) / max(1.0, float(run_count))
    return min(1.0, max(0.0, value))


def a_efficiency(inverse: list[list[float]] | None, term_count: int, rank: int) -> float:
    if inverse is None or term_count <= 0:
        return min(0.5, rank / max(1, term_count))
    trace = sum(inverse[i][i] for i in range(min(len(inverse), len(inverse[0]))))
    if trace <= 0:
        return 0.0
    return min(1.0, max(0.0, term_count / trace))


def i_efficiency(prediction_variances: list[float], rank: int, term_count: int) -> float:
    if not prediction_variances:
        return min(0.5, rank / max(1, term_count))
    mean = sum(prediction_variances) / len(prediction_variances)
    return min(1.0, max(0.0, 1.0 / (1.0 + mean)))


def g_efficiency(prediction_variances: list[float], term_count: int, rank: int) -> float:
    if not prediction_variances or term_count <= 0:
        return min(0.5, rank / max(1, term_count))
    max_variance = max(prediction_variances)
    if max_variance <= 0:
        return 1.0
    return min(1.0, max(0.0, term_count / (max_variance * max(1, len(prediction_variances)))))


def fds_summary(prediction_variances: list[float]) -> dict[str, Any]:
    if not prediction_variances:
        return {"quantiles": {}, "label": "unavailable"}
    values = sorted(prediction_variances)
    return {
        "quantiles": {
            "p10": round(quantile(values, 0.1), 4),
            "p50": round(quantile(values, 0.5), 4),
            "p90": round(quantile(values, 0.9), 4),
        },
        "label": "approximate_design_row_distribution",
    }


def prediction_variance_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(min(values), 4),
        "mean": round(sum(values) / len(values), 4),
        "max": round(max(values), 4),
    }


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pos = q * (len(values) - 1)
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return values[low]
    return values[low] + (values[high] - values[low]) * (pos - low)


def replicate_count(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> int:
    seen: dict[tuple[str, ...], int] = {}
    for row in rows:
        key = tuple(str(row.get(factor["factor_id"], "")) for factor in factors)
        seen[key] = seen.get(key, 0) + 1
    return sum(count - 1 for count in seen.values() if count > 1)


def is_center_row(row: dict[str, Any], factors: list[dict[str, Any]]) -> bool:
    for factor in factors:
        _, center, _ = factor_values(factor)
        expected = format_number(center) if isinstance(center, float) else str(center)
        if str(row.get(factor["factor_id"])) != expected:
            return False
    return True


def factor_values(factor: dict[str, Any]) -> tuple[Any, Any, Any]:
    factor_type = str(factor.get("type") or "continuous").lower()
    if factor_type in CATEGORICAL_TYPES and factor.get("levels"):
        levels = factor["levels"]
        return levels[0], levels[len(levels) // 2], levels[-1]
    low = factor.get("min")
    high = factor.get("max")
    if low is None or high is None:
        levels = factor.get("levels") or ["low", "center", "high"]
        return levels[0], levels[len(levels) // 2], levels[-1]
    center = (float(low) + float(high)) / 2
    return float(low), center, float(high)


def scaled_vector(row: dict[str, Any], factors: list[dict[str, Any]]) -> list[float]:
    vector: list[float] = []
    for factor in factors:
        factor_id = factor["factor_id"]
        factor_type = str(factor.get("type") or "continuous").lower()
        if factor_type in NUMERIC_TYPES:
            vector.append((_scaled_numeric(row.get(factor_id), factor) + 1.0) / 2.0)
        else:
            levels = [str(level) for level in factor.get("levels", [])]
            value = str(row.get(factor_id))
            vector.append(levels.index(value) / max(1, len(levels) - 1) if value in levels else 0.5)
    return vector


def min_scaled_distance(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.0
    vectors = [scaled_vector(row, factors) for row in rows]
    best = 1e9
    for left, right in itertools.combinations(vectors, 2):
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
        best = min(best, distance)
    return 0.0 if best == 1e9 else min(1.0, best / math.sqrt(max(1, len(factors))))


def statistical_quality(
    d_eff: float,
    i_eff: float,
    g_eff: float,
    alias_pressure: float,
    min_distance: float,
    violations: list[dict[str, Any]],
) -> float:
    violation_penalty = min(0.5, 0.08 * len(violations))
    return max(
        0.0,
        min(
            1.0,
            0.28 * d_eff
            + 0.22 * i_eff
            + 0.18 * g_eff
            + 0.18 * (1.0 - alias_pressure)
            + 0.14 * min_distance
            - violation_penalty,
        ),
    )
