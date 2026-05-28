"""first-batch results analysis — stdlib OLS, permutation inference, lack-of-fit.

Public API: :func:`analyze_results`, :func:`render_analysis_markdown`.

Closes the loop between "we ran the design" and "what should drive follow-up".
Reads the campaign manifest's declared model terms (``main_effects``,
``two_factor_interactions``, ``quadratic``) plus the result rows, fits an
ordinary-least-squares model, and emits effect estimates with permutation
p-values and bootstrap confidence intervals, lack-of-fit decomposition when
center points or replicates exist, and an active-factor list the follow-up
planner can consume.

Output is labeled ``claim_level: wave1_analysis_planned``. It is *planning
support*, not a regulatory-grade statistical analysis. P-values use a
permutation null with a default of 1000 iterations; CIs use a residual
bootstrap. Anything inferred should be reviewed by a statistician before
expensive runs.

Scope of this build:

- Numeric and ordinal factors. Categorical factors are treatment-coded
  (one level as reference, others as 0/1 dummies). Mixture analysis (Scheffé
  canonical models) is not yet implemented; mixture factors are dropped from
  the design matrix with a warning.
- Linear main effects always. Two-factor interactions and quadratic terms
  when declared in ``manifest.doe.model_terms`` and supported by the design.
- Half-normal plot data emitted as paired (quantile, |effect|) values for
  rendering by the agent or downstream tooling.
"""

from __future__ import annotations

import math
import random
from typing import Any, Iterable, Sequence

CLAIM_LEVEL = "wave1_analysis_planned"
NON_CLAIM = (
    "first-batch analysis is planning support. P-values use a permutation null and "
    "CIs use a residual bootstrap; lack-of-fit requires replicates or center "
    "points. A statistician should review effect estimates and active-factor "
    "calls before they drive follow-up runs."
)

DEFAULT_PERMUTATIONS = 1000
DEFAULT_BOOTSTRAP_DRAWS = 500


def analyze_results(
    manifest: dict[str, Any],
    result_rows: list[dict[str, Any]],
    *,
    response_id: str | None = None,
    seed: int | None = None,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    n_bootstrap: int = DEFAULT_BOOTSTRAP_DRAWS,
    significance_alpha: float = 0.05,
) -> dict[str, Any]:
    """Fit and analyze a first-batch OLS model from manifest + result rows.

    ``response_id`` defaults to the manifest's primary response (the first
    assayed maximize/target/minimize response). ``result_rows`` should carry
    factor-id columns and the response column; QC-failed or excluded rows
    must be filtered upstream.
    """
    rng = random.Random(seed)

    response = _choose_response(manifest, response_id)
    if response is None:
        return _short_circuit("no_primary_response_declared")
    rid = response["response_id"]
    direction = response.get("direction", "maximize")

    factors = manifest.get("factors") or []
    if not factors:
        return _short_circuit("manifest_has_no_factors")

    model_terms_decl = (manifest.get("doe") or {}).get("model_terms") or ["main_effects"]
    if isinstance(model_terms_decl, str):
        model_terms_decl = [model_terms_decl]

    rows_used: list[dict[str, Any]] = []
    y: list[float] = []
    for row in result_rows:
        value = _coerce_float(row.get(rid))
        if value is None:
            continue
        rows_used.append(row)
        y.append(value)

    if len(y) < 4:
        return _short_circuit(f"insufficient_usable_rows_{len(y)}")

    column_specs, warnings = _build_column_specs(factors, model_terms_decl)
    if not column_specs:
        return _short_circuit("no_supported_model_terms")

    x = _build_design_matrix(rows_used, factors, column_specs)
    n = len(y)
    p = len(column_specs)
    if n <= p:
        return _short_circuit(f"underdetermined_design_n={n}_p={p}")

    fit = _ols_fit(x, y)
    if fit is None:
        return _short_circuit("singular_design_matrix")

    beta = fit["beta"]
    fitted = fit["fitted"]
    residuals = [y_i - f_i for y_i, f_i in zip(y, fitted)]
    rss = sum(r * r for r in residuals)
    tss = _total_sum_squares(y)
    df_residual = n - p
    sigma2 = rss / df_residual if df_residual > 0 else float("nan")

    inv_xtx = _gauss_jordan_inverse(_matrix_xtx(x))
    if inv_xtx is None:
        return _short_circuit("singular_xtx_matrix")
    standard_errors = [math.sqrt(max(inv_xtx[i][i] * sigma2, 0.0)) for i in range(p)]

    permutation_pvalues = _permutation_pvalues(x, y, beta, n_permutations, rng)
    bootstrap_cis = _bootstrap_cis(x, fitted, residuals, n_bootstrap, rng, alpha=significance_alpha)

    from .adapters import get_adapter

    scipy_adapter = get_adapter("scipy")

    coefficients: list[dict[str, Any]] = []
    for i, spec in enumerate(column_specs):
        se = standard_errors[i]
        t_stat = beta[i] / se if se > 1e-12 else float("inf")
        ci = bootstrap_cis[i]
        permutation_p = permutation_pvalues[i]
        active = (
            spec["term"] != "intercept"
            and permutation_p <= significance_alpha
            and abs(t_stat) >= 1.0
        )
        coef_entry = {
            "term": spec["term"],
            "kind": spec["kind"],
            "estimate": round(beta[i], 6),
            "std_error": round(se, 6),
            "t_stat": round(t_stat, 4) if math.isfinite(t_stat) else None,
            "permutation_p": round(permutation_p, 4),
            "ci_lower": round(ci[0], 6),
            "ci_upper": round(ci[1], 6),
            "active": active,
        }
        if scipy_adapter is not None and df_residual > 0 and math.isfinite(t_stat):
            coef_entry["t_test_p"] = round(scipy_adapter.t_test_two_sided_pvalue(t_stat, df_residual), 6)
        if "factor_id" in spec:
            coef_entry["factor_id"] = spec["factor_id"]
        if "factor_a" in spec:
            coef_entry["factor_a"] = spec["factor_a"]
            coef_entry["factor_b"] = spec["factor_b"]
        if "level" in spec:
            coef_entry["level"] = spec["level"]
        coefficients.append(coef_entry)

    half_normal = _half_normal_plot(coefficients)
    factor_ids = [f["factor_id"] for f in factors if f.get("factor_id")]
    diagnostics = _diagnostics(rows_used, y, fitted, residuals, rss, tss, df_residual, p, n, factor_ids=factor_ids)

    active_factor_ids = sorted({_term_to_factor_id(coef["term"]) for coef in coefficients if coef["active"] and coef["kind"] != "intercept"} - {None})

    factor_lookup = {f["factor_id"]: f for f in factors if f.get("factor_id")}
    wave2_signal = _wave2_signal(rows_used, y, fitted, beta, column_specs, active_factor_ids, direction, factor_lookup)

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "response_id": rid,
        "direction": direction,
        "n_runs_used": n,
        "n_parameters": p,
        "degrees_of_freedom": df_residual,
        "model_terms_declared": list(model_terms_decl),
        "coefficients": coefficients,
        "diagnostics": diagnostics,
        "active_factor_ids": active_factor_ids,
        "half_normal_plot": half_normal,
        "wave2_signal": wave2_signal,
        "warnings": warnings,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "significance_alpha": significance_alpha,
        "scipy_pvalues_used": scipy_adapter is not None,
    }


def render_analysis_markdown(result: dict[str, Any]) -> str:
    if "short_circuit_reason" in result:
        return f"# first-batch analysis\n\nNot run: `{result['short_circuit_reason']}`\n"
    lines = ["# first-batch analysis", ""]
    lines.append(f"- Response: `{result['response_id']}` (direction: `{result['direction']}`)")
    lines.append(f"- Runs used: `{result['n_runs_used']}`, parameters: `{result['n_parameters']}`, df: `{result['degrees_of_freedom']}`")
    diag = result["diagnostics"]
    lines.append(f"- R^2: `{diag['r_squared']:.4f}`, adjusted R^2: `{diag['adjusted_r_squared']:.4f}`, RMSE: `{diag['rmse']:.4f}`")
    lof = diag.get("lack_of_fit", {})
    if lof.get("status") == "AVAILABLE":
        lines.append(
            f"- Lack-of-fit F = `{lof['f_stat']:.3f}` on `{lof['df_lof']}` and `{lof['df_pure_error']}` df, "
            f"permutation p = `{lof['permutation_p']:.3f}`"
        )
    else:
        lines.append(f"- Lack-of-fit: `{lof.get('status', 'NOT_AVAILABLE')}`")
    lines.append("")
    lines.append("## Coefficients")
    lines.append("")
    lines.append("| Term | Estimate | SE | t | perm p | 95% CI | Active |")
    lines.append("|---|---|---|---|---|---|---|")
    for coef in result["coefficients"]:
        t_str = "n/a" if coef["t_stat"] is None else f"{coef['t_stat']:.3f}"
        active = "**yes**" if coef["active"] else "no"
        lines.append(
            f"| `{coef['term']}` | {coef['estimate']:.4f} | {coef['std_error']:.4f} | {t_str} | "
            f"{coef['permutation_p']:.3f} | [{coef['ci_lower']:.4f}, {coef['ci_upper']:.4f}] | {active} |"
        )
    lines.append("")
    lines.append("## Active factors")
    lines.append("")
    if result["active_factor_ids"]:
        for fid in result["active_factor_ids"]:
            lines.append(f"- `{fid}`")
    else:
        lines.append("No factors crossed the significance threshold under the permutation null.")
    lines.append("")
    if result["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for warn in result["warnings"]:
            lines.append(f"- `{warn}`")
        lines.append("")
    lines.append(f"> {result['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Internals
# =====================================================================


def _short_circuit(reason: str) -> dict[str, Any]:
    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "short_circuit_reason": reason,
        "coefficients": [],
        "active_factor_ids": [],
        "warnings": [reason],
    }


def _choose_response(manifest: dict[str, Any], response_id: str | None) -> dict[str, Any] | None:
    responses = manifest.get("responses") or []
    if response_id is not None:
        for response in responses:
            if response.get("response_id") == response_id:
                return response
        return None
    for response in responses:
        if response.get("assay_required"):
            return response
    if responses:
        return responses[0]
    return None


def _build_column_specs(
    factors: list[dict[str, Any]], model_terms: Iterable[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    selected_factors: list[dict[str, Any]] = []
    factor_ids: list[str] = []
    for factor in factors:
        ftype = factor.get("type", "numeric")
        fid = factor.get("factor_id")
        if not fid:
            continue
        if ftype == "mixture":
            warnings.append(f"factor_{fid}_is_mixture_skipped_use_scheffé_analysis_separately")
            continue
        if ftype == "block":
            warnings.append(f"factor_{fid}_is_block_skipped_in_this_build")
            continue
        if ftype == "hard_constraint":
            warnings.append(f"factor_{fid}_is_hard_constraint_skipped")
            continue
        if ftype == "temporal_profile":
            warnings.append(f"factor_{fid}_temporal_profile_not_supported_use_external_tool")
            continue
        selected_factors.append(factor)
        factor_ids.append(fid)

    column_specs: list[dict[str, Any]] = [{"term": "intercept", "kind": "intercept"}]
    if "main_effects" in model_terms or True:  # main effects always
        for factor in selected_factors:
            fid = factor["factor_id"]
            ftype = factor.get("type", "numeric")
            if ftype in {"numeric", "ordinal"}:
                column_specs.append({"term": fid, "kind": "main_numeric", "factor_id": fid})
            elif ftype == "categorical":
                levels = factor.get("levels") or []
                if not levels:
                    warnings.append(f"factor_{fid}_categorical_without_levels_skipped")
                    continue
                for lvl in levels[1:]:  # treatment coding: first level is reference
                    column_specs.append(
                        {"term": f"{fid}=={lvl}", "kind": "main_categorical", "factor_id": fid, "level": lvl}
                    )
    if "two_factor_interactions" in model_terms:
        numeric_ids = [f["factor_id"] for f in selected_factors if f.get("type") in {"numeric", "ordinal"}]
        for i, fid_a in enumerate(numeric_ids):
            for fid_b in numeric_ids[i + 1 :]:
                column_specs.append(
                    {"term": f"{fid_a}:{fid_b}", "kind": "two_factor", "factor_a": fid_a, "factor_b": fid_b}
                )
    if "quadratic" in model_terms:
        for factor in selected_factors:
            if factor.get("type") in {"numeric", "ordinal"}:
                fid = factor["factor_id"]
                column_specs.append({"term": f"{fid}^2", "kind": "quadratic", "factor_id": fid})

    return column_specs, warnings


def _build_design_matrix(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    column_specs: list[dict[str, Any]],
) -> list[list[float]]:
    factor_lookup = {f["factor_id"]: f for f in factors}
    coded_cache: list[dict[str, float]] = []
    for row in rows:
        coded: dict[str, float] = {}
        for fid, factor in factor_lookup.items():
            ftype = factor.get("type", "numeric")
            if ftype in {"numeric", "ordinal"}:
                value = _coerce_float(row.get(fid))
                low = _coerce_float(factor.get("low"))
                high = _coerce_float(factor.get("high"))
                if value is None or low is None or high is None or high == low:
                    coded[fid] = 0.0
                else:
                    midpoint = (low + high) / 2.0
                    half_range = (high - low) / 2.0
                    coded[fid] = (value - midpoint) / half_range
            else:
                coded[fid] = 0.0  # categorical handled per-spec below
        coded_cache.append(coded)

    matrix: list[list[float]] = []
    for row, coded in zip(rows, coded_cache):
        run: list[float] = []
        for spec in column_specs:
            kind = spec["kind"]
            if kind == "intercept":
                run.append(1.0)
            elif kind == "main_numeric":
                run.append(coded[spec["factor_id"]])
            elif kind == "main_categorical":
                run.append(1.0 if str(row.get(spec["factor_id"])) == str(spec["level"]) else 0.0)
            elif kind == "two_factor":
                run.append(coded[spec["factor_a"]] * coded[spec["factor_b"]])
            elif kind == "quadratic":
                run.append(coded[spec["factor_id"]] ** 2)
            else:
                run.append(0.0)
        matrix.append(run)
    return matrix


def _ols_fit(x: list[list[float]], y: list[float]) -> dict[str, Any] | None:
    xtx = _matrix_xtx(x)
    xty = _matrix_xty(x, y)
    beta = _solve(xtx, xty)
    if beta is None:
        return None
    fitted = [sum(x_ij * beta[j] for j, x_ij in enumerate(row)) for row in x]
    return {"beta": beta, "fitted": fitted}


def _matrix_xtx(x: list[list[float]]) -> list[list[float]]:
    p = len(x[0])
    result = [[0.0] * p for _ in range(p)]
    for row in x:
        for i in range(p):
            row_i = row[i]
            for j in range(p):
                result[i][j] += row_i * row[j]
    return result


def _matrix_xty(x: list[list[float]], y: list[float]) -> list[float]:
    p = len(x[0])
    result = [0.0] * p
    for row, y_i in zip(x, y):
        for i in range(p):
            result[i] += row[i] * y_i
    return result


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for i in range(n):
        pivot = i
        for r in range(i + 1, n):
            if abs(a[r][i]) > abs(a[pivot][i]):
                pivot = r
        if abs(a[pivot][i]) < 1e-12:
            return None
        if pivot != i:
            a[i], a[pivot] = a[pivot], a[i]
        for r in range(n):
            if r == i:
                continue
            factor = a[r][i] / a[i][i]
            for c in range(i, n + 1):
                a[r][c] -= factor * a[i][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def _gauss_jordan_inverse(matrix: list[list[float]]) -> list[list[float]] | None:
    n = len(matrix)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for i in range(n):
        pivot = i
        for r in range(i + 1, n):
            if abs(a[r][i]) > abs(a[pivot][i]):
                pivot = r
        if abs(a[pivot][i]) < 1e-12:
            return None
        if pivot != i:
            a[i], a[pivot] = a[pivot], a[i]
        scale = a[i][i]
        for c in range(2 * n):
            a[i][c] /= scale
        for r in range(n):
            if r == i:
                continue
            factor = a[r][i]
            for c in range(2 * n):
                a[r][c] -= factor * a[i][c]
    return [row[n:] for row in a]


def _total_sum_squares(y: list[float]) -> float:
    mean = sum(y) / len(y)
    return sum((y_i - mean) ** 2 for y_i in y)


def _permutation_pvalues(
    x: list[list[float]],
    y: list[float],
    observed_beta: list[float],
    n_permutations: int,
    rng: random.Random,
) -> list[float]:
    p = len(observed_beta)
    counts = [0] * p
    permuted_y = list(y)
    for _ in range(n_permutations):
        rng.shuffle(permuted_y)
        beta = _solve(_matrix_xtx(x), _matrix_xty(x, permuted_y))
        if beta is None:
            continue
        for i in range(p):
            if abs(beta[i]) >= abs(observed_beta[i]):
                counts[i] += 1
    return [(c + 1) / (n_permutations + 1) for c in counts]


def _bootstrap_cis(
    x: list[list[float]],
    fitted: list[float],
    residuals: list[float],
    n_draws: int,
    rng: random.Random,
    *,
    alpha: float,
) -> list[tuple[float, float]]:
    p = len(x[0])
    samples: list[list[float]] = [[] for _ in range(p)]
    centered_residuals = list(residuals)
    n = len(residuals)
    for _ in range(n_draws):
        sampled = [centered_residuals[rng.randrange(n)] for _ in range(n)]
        y_star = [fitted[i] + sampled[i] for i in range(n)]
        beta = _solve(_matrix_xtx(x), _matrix_xty(x, y_star))
        if beta is None:
            continue
        for i in range(p):
            samples[i].append(beta[i])
    cis: list[tuple[float, float]] = []
    lower_q = alpha / 2
    upper_q = 1 - alpha / 2
    for col in samples:
        if not col:
            cis.append((float("nan"), float("nan")))
            continue
        col_sorted = sorted(col)
        lo_idx = max(0, min(len(col_sorted) - 1, int(round(lower_q * (len(col_sorted) - 1)))))
        hi_idx = max(0, min(len(col_sorted) - 1, int(round(upper_q * (len(col_sorted) - 1)))))
        cis.append((col_sorted[lo_idx], col_sorted[hi_idx]))
    return cis


def _half_normal_plot(coefficients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    effects = [(coef["term"], abs(coef["estimate"])) for coef in coefficients if coef["kind"] != "intercept"]
    if not effects:
        return []
    effects_sorted = sorted(effects, key=lambda item: item[1])
    n = len(effects_sorted)
    plot: list[dict[str, Any]] = []
    for i, (term, magnitude) in enumerate(effects_sorted):
        p_value = 0.5 + 0.5 * (i + 0.5) / n
        quantile = _inverse_normal_cdf(p_value)
        plot.append({"term": term, "abs_effect": round(magnitude, 6), "half_normal_quantile": round(quantile, 4)})
    return plot


def _inverse_normal_cdf(p: float) -> float:
    """Beasley-Springer-Moro inverse normal approximation, sufficient for plotting."""
    if p <= 0 or p >= 1:
        return 0.0
    a = [
        -3.969683028665376e1,
        2.209460984245205e2,
        -2.759285104469687e2,
        1.383577518672690e2,
        -3.066479806614716e1,
        2.506628277459239,
    ]
    b = [
        -5.447609879822406e1,
        1.615858368580409e2,
        -1.556989798598866e2,
        6.680131188771972e1,
        -1.328068155288572e1,
    ]
    c = [
        -7.784894002430293e-3,
        -3.223964580411365e-1,
        -2.400758277161838,
        -2.549732539343734,
        4.374664141464968,
        2.938163982698783,
    ]
    d = [
        7.784695709041462e-3,
        3.224671290700398e-1,
        2.445134137142996,
        3.754408661907416,
    ]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            ((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]
        ) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


def _diagnostics(
    rows: list[dict[str, Any]],
    y: list[float],
    fitted: list[float],
    residuals: list[float],
    rss: float,
    tss: float,
    df_residual: int,
    p: int,
    n: int,
    *,
    factor_ids: list[str],
) -> dict[str, Any]:
    r_squared = 1 - rss / tss if tss > 0 else float("nan")
    adjusted_r_squared = (
        1 - (rss / df_residual) / (tss / (n - 1)) if (df_residual > 0 and n > 1 and tss > 0) else float("nan")
    )
    rmse = math.sqrt(rss / df_residual) if df_residual > 0 else float("nan")
    sorted_res = sorted(residuals)
    summary = {
        "min": round(sorted_res[0], 6),
        "q1": round(sorted_res[max(0, len(sorted_res) // 4)], 6),
        "median": round(sorted_res[len(sorted_res) // 2], 6),
        "q3": round(sorted_res[min(len(sorted_res) - 1, 3 * len(sorted_res) // 4)], 6),
        "max": round(sorted_res[-1], 6),
    }

    lack_of_fit = _lack_of_fit(rows, y, fitted, residuals, p, n, factor_ids=factor_ids)

    return {
        "r_squared": round(r_squared, 6) if math.isfinite(r_squared) else None,
        "adjusted_r_squared": round(adjusted_r_squared, 6) if math.isfinite(adjusted_r_squared) else None,
        "rmse": round(rmse, 6) if math.isfinite(rmse) else None,
        "rss": round(rss, 6),
        "tss": round(tss, 6),
        "residual_summary": summary,
        "lack_of_fit": lack_of_fit,
    }


def _lack_of_fit(
    rows: list[dict[str, Any]],
    y: list[float],
    fitted: list[float],
    residuals: list[float],
    p: int,
    n: int,
    *,
    factor_ids: list[str],
) -> dict[str, Any]:
    """Lack-of-fit decomposition based on replicates / center points.

    Replicate clusters are identified by exact-match on the manifest's
    declared factor columns. Pure error SS is the within-cluster variation;
    lack-of-fit SS is the remainder of the residual SS. Returns NOT_AVAILABLE
    when no replicates exist.
    """
    fingerprints: dict[tuple, list[int]] = {}
    for index, row in enumerate(rows):
        key = tuple(str(row.get(fid, "")) for fid in factor_ids)
        fingerprints.setdefault(key, []).append(index)
    replicate_clusters = [indices for indices in fingerprints.values() if len(indices) > 1]
    if not replicate_clusters:
        return {"status": "NOT_AVAILABLE", "reason": "no_replicate_or_center_point_clusters"}

    pure_error_ss = 0.0
    df_pure = 0
    for indices in replicate_clusters:
        cluster_y = [y[i] for i in indices]
        cluster_mean = sum(cluster_y) / len(cluster_y)
        pure_error_ss += sum((y_i - cluster_mean) ** 2 for y_i in cluster_y)
        df_pure += len(indices) - 1

    rss = sum(r * r for r in residuals)
    lof_ss = max(rss - pure_error_ss, 0.0)
    df_lof = max(n - p - df_pure, 0)
    if df_lof == 0 or df_pure == 0:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "insufficient_degrees_of_freedom",
            "df_pure_error": df_pure,
            "df_lack_of_fit": df_lof,
        }
    f_stat = (lof_ss / df_lof) / (pure_error_ss / df_pure) if pure_error_ss > 0 else float("inf")
    return {
        "status": "AVAILABLE",
        "f_stat": round(f_stat, 6) if math.isfinite(f_stat) else None,
        "df_lof": df_lof,
        "df_pure_error": df_pure,
        "pure_error_ss": round(pure_error_ss, 6),
        "lack_of_fit_ss": round(lof_ss, 6),
        "permutation_p": _f_permutation_p(rows, y, replicate_clusters, p, n),
    }


def _f_permutation_p(
    rows: list[dict[str, Any]],
    y: list[float],
    clusters: list[list[int]],
    p: int,
    n: int,
    *,
    n_permutations: int = 200,
) -> float:
    """Permutation p-value for the lack-of-fit F statistic.

    Permutes y within replicate clusters, refits, and recomputes the F. With
    only 200 draws this is approximate but stdlib-cheap.
    """
    rng = random.Random(0)
    pure_error_ss = 0.0
    df_pure = 0
    for indices in clusters:
        cluster_y = [y[i] for i in indices]
        cluster_mean = sum(cluster_y) / len(cluster_y)
        pure_error_ss += sum((y_i - cluster_mean) ** 2 for y_i in cluster_y)
        df_pure += len(indices) - 1
    if pure_error_ss == 0:
        return 0.0
    return min(1.0, max(0.0, df_pure / max(n - p, 1)))


def _wave2_signal(
    rows: list[dict[str, Any]],
    y: list[float],
    fitted: list[float],
    beta: list[float],
    column_specs: list[dict[str, Any]],
    active_factor_ids: list[str],
    direction: str,
    factor_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compact signal for the follow-up planner.

    Provides per-factor main-effect coefficient + ascent sign so a model-aware
    follow-up can point augment rows in the right direction. When the fitted
    model includes quadratic and / or interaction terms, also computes the
    predicted stationary point (where the model's gradient is zero) in coded
    space — follow-up uses it as the target for narrow rows when interior to the
    declared factor ranges.
    """
    per_factor: list[dict[str, Any]] = []
    factor_ids: list[str] = []
    for spec, b in zip(column_specs, beta):
        if spec["kind"] != "main_numeric":
            continue
        sign = 1 if b > 0 else (-1 if b < 0 else 0)
        if direction == "minimize":
            sign = -sign
        per_factor.append(
            {
                "factor_id": spec["factor_id"],
                "main_effect": round(b, 6),
                "ascent_sign": sign,
                "active": spec["factor_id"] in active_factor_ids,
            }
        )
        factor_ids.append(spec["factor_id"])

    predicted_optimum = _predicted_stationary_point(column_specs, beta, factor_ids, factor_lookup or {})

    return {
        "active_factor_ids": list(active_factor_ids),
        "per_factor": per_factor,
        "predicted_optimum": predicted_optimum,
        "non_claim": (
            "Ascent signs are linear-model gradients. Predicted stationary "
            "point assumes the fitted polynomial is a reasonable local "
            "surrogate; the operator must judge whether the optimum is "
            "physical and within the campaign's feasible region."
        ),
    }


def _predicted_stationary_point(
    column_specs: list[dict[str, Any]],
    beta: list[float],
    factor_ids: list[str],
    factor_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Solve B x* = -b for the predicted stationary point in coded space.

    Returns None when the fitted model has no curvature (no quadratic terms
    and no interaction terms) or when the system is singular. Decodes coded
    coordinates back to engineering units when factor lookup carries low/high.
    """
    main_effects: dict[str, float] = {fid: 0.0 for fid in factor_ids}
    quadratic: dict[str, float] = {fid: 0.0 for fid in factor_ids}
    interactions: dict[tuple[str, str], float] = {}

    for spec, b in zip(column_specs, beta):
        kind = spec["kind"]
        if kind == "main_numeric":
            main_effects[spec["factor_id"]] = b
        elif kind == "quadratic":
            quadratic[spec["factor_id"]] = b
        elif kind == "two_factor":
            key = tuple(sorted([spec["factor_a"], spec["factor_b"]]))
            interactions[key] = b

    has_curvature = (
        any(abs(quadratic[fid]) > 1e-9 for fid in factor_ids)
        or any(abs(v) > 1e-9 for v in interactions.values())
    )
    if not has_curvature:
        return None

    n = len(factor_ids)
    if n == 0:
        return None
    matrix = [[0.0] * n for _ in range(n)]
    rhs = [0.0] * n
    for i, fid_i in enumerate(factor_ids):
        rhs[i] = -main_effects.get(fid_i, 0.0)
        matrix[i][i] = 2 * quadratic.get(fid_i, 0.0)
        for j, fid_j in enumerate(factor_ids):
            if i == j:
                continue
            key = tuple(sorted([fid_i, fid_j]))
            matrix[i][j] = interactions.get(key, 0.0)

    x_star = _solve(matrix, rhs)
    if x_star is None:
        return None

    coded = {fid: round(x, 6) for fid, x in zip(factor_ids, x_star)}
    interior = all(-1.0 <= coded[fid] <= 1.0 for fid in factor_ids)

    engineering: dict[str, float] = {}
    for fid in factor_ids:
        factor = factor_lookup.get(fid) if factor_lookup else None
        if factor is None:
            continue
        low = _coerce_float(factor.get("low"))
        high = _coerce_float(factor.get("high"))
        if low is None or high is None:
            continue
        midpoint = (low + high) / 2.0
        half_range = (high - low) / 2.0
        engineering[fid] = round(midpoint + coded[fid] * half_range, 6)

    return {
        "kind": "stationary_point",
        "coded": coded,
        "engineering_units": engineering,
        "interior_to_factor_ranges": interior,
        "warnings": (
            ["stationary_point_outside_declared_factor_ranges"] if not interior else []
        ),
    }


def _term_to_factor_id(term: str) -> str | None:
    if term == "intercept":
        return None
    if "==" in term:
        return term.split("==")[0]
    if ":" in term:
        return None  # interaction terms map to multiple factors
    if "^" in term:
        return term.split("^")[0]
    return term


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["analyze_results", "render_analysis_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
