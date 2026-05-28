"""Design-level power analysis: per-coefficient MDE from the design matrix.

Public API: :func:`compute_doe_power`, :func:`render_doe_power_markdown`.

Closes the second power-analysis gap. ``ferm-doe assay-power`` covers
*response* readiness (assay LOD/LOQ, replicates, target power). This module
covers *design* readiness: given the chosen design matrix and an operator-
supplied residual standard deviation, what is the minimum detectable effect
(MDE) per coefficient at target power and significance? The answer depends
only on the design matrix — observed data is not required.

Math:

For OLS, the variance of an estimated coefficient ``β_i`` is::

    Var(β_i) = σ² · (XᵀX)⁻¹ᵢᵢ

So ``SE(β_i) = σ · sqrt((XᵀX)⁻¹ᵢᵢ)``. The minimum detectable effect at
significance ``α`` (two-sided) and power ``1 - β`` is::

    MDE_i = (z_{α/2} + z_β) · SE(β_i)

For α=0.05 two-sided, ``z_{α/2} ≈ 1.96``; for power 0.80, ``z_β ≈ 0.84``;
so ``MDE_i ≈ 2.802 · σ · sqrt((XᵀX)⁻¹ᵢᵢ)``.

This module does *not* claim DoE-grade regulatory power — the normal
approximation ignores df penalty for small designs. The result is a
planning hint: which coefficients are well-determined by the chosen
design, and which would be drowned by realistic noise. A statistician
should review before locking the plan.

Input options:

- Compute the design from ``manifest.doe.family`` via ``generate_design``
  (default) — supports any of the nine in-repo families.
- Pass ``design_rows`` directly when the operator has already produced a
  design CSV (e.g., from a harness adapter).

The expected-effect-size check compares ``MDE_i`` against the response's
``assay_power_policy.expected_effect_size`` (when declared). Coefficients
whose MDE exceeds the expected effect get ``expected_passes_mde: false`` —
the design will not reliably catch effects that small.
"""

from __future__ import annotations

import math
from typing import Any

from .analysis import _build_column_specs, _build_design_matrix, _gauss_jordan_inverse, _matrix_xtx
from .doe_generators import generate_design

CLAIM_LEVEL = "doe_power_planning"
NON_CLAIM = (
    "Design-level power is a normal-approximation MDE per coefficient. It "
    "does not include the t-distribution df correction or interaction-aware "
    "alias structure. A statistician should review before locking expensive "
    "designs."
)


def compute_doe_power(
    manifest: dict[str, Any],
    *,
    sigma: float,
    alpha: float = 0.05,
    target_power: float = 0.8,
    design_rows: list[dict[str, Any]] | None = None,
    seed: int | None = 0,
) -> dict[str, Any]:
    """Compute per-coefficient MDE for the design implied by ``manifest``.

    ``sigma`` is the residual standard deviation in the response's units.
    Defaults to 1.0 if the caller wants per-sigma SE; pass a real value to
    get an MDE in engineering units.
    """
    if sigma <= 0:
        raise ValueError("sigma_must_be_positive")
    if not (0 < alpha < 1):
        raise ValueError("alpha_must_be_in_open_unit_interval")
    if not (0 < target_power < 1):
        raise ValueError("target_power_must_be_in_open_unit_interval")

    factors = manifest.get("factors") or []
    if not factors:
        return {"claim_level": CLAIM_LEVEL, "non_claim": NON_CLAIM, "short_circuit_reason": "manifest_has_no_factors"}

    if design_rows is None:
        try:
            design = generate_design(manifest, seed=seed)
        except ValueError as exc:
            return {
                "claim_level": CLAIM_LEVEL,
                "non_claim": NON_CLAIM,
                "short_circuit_reason": str(exc),
            }
        design_rows = design["rows"]

    model_terms = (manifest.get("doe") or {}).get("model_terms") or ["main_effects"]
    if isinstance(model_terms, str):
        model_terms = [model_terms]
    column_specs, warnings = _build_column_specs(factors, model_terms)
    if not column_specs:
        return {"claim_level": CLAIM_LEVEL, "non_claim": NON_CLAIM, "short_circuit_reason": "no_supported_model_terms"}

    x = _build_design_matrix(design_rows, factors, column_specs)
    n = len(design_rows)
    p = len(column_specs)
    if n < p:
        return {
            "claim_level": CLAIM_LEVEL,
            "non_claim": NON_CLAIM,
            "short_circuit_reason": f"underdetermined_design_n={n}_p={p}",
        }

    inv = _gauss_jordan_inverse(_matrix_xtx(x))
    if inv is None:
        return {
            "claim_level": CLAIM_LEVEL,
            "non_claim": NON_CLAIM,
            "short_circuit_reason": "singular_xtx",
        }

    df_residual = n - p

    from .adapters import get_adapter

    scipy_adapter = get_adapter("scipy")
    if scipy_adapter is not None and df_residual > 0:
        critical = scipy_adapter.t_critical(alpha, df_residual)
        z_power = scipy_adapter.normal_quantile(target_power)
        critical_basis = "student_t"
    else:
        critical = _inverse_normal_cdf(1 - alpha / 2)
        z_power = _inverse_normal_cdf(target_power)
        critical_basis = "normal_approximation"
    z_alpha_half = critical
    mde_factor = critical + z_power

    expected_effects = _expected_effects_by_factor(manifest)

    coefficients: list[dict[str, Any]] = []
    for i, spec in enumerate(column_specs):
        variance_factor = max(inv[i][i], 0.0)
        se_per_sigma = math.sqrt(variance_factor)
        se = sigma * se_per_sigma
        mde = mde_factor * se
        entry: dict[str, Any] = {
            "term": spec["term"],
            "kind": spec["kind"],
            "variance_factor": round(variance_factor, 6),
            "se_per_sigma": round(se_per_sigma, 6),
            "se": round(se, 6),
            "mde_at_target_power": round(mde, 6),
        }
        if "factor_id" in spec:
            entry["factor_id"] = spec["factor_id"]
            expected = expected_effects.get(spec["factor_id"])
            if expected is not None:
                entry["expected_effect_size"] = expected
                entry["expected_passes_mde"] = expected >= mde
        coefficients.append(entry)

    n_passing = sum(1 for entry in coefficients if entry.get("expected_passes_mde"))
    n_with_target = sum(1 for entry in coefficients if "expected_passes_mde" in entry)

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "n_runs": n,
        "n_parameters": p,
        "df_residual": df_residual,
        "alpha": alpha,
        "target_power": target_power,
        "z_alpha_half": round(z_alpha_half, 4),
        "z_power": round(z_power, 4),
        "mde_multiplier": round(mde_factor, 4),
        "critical_basis": critical_basis,
        "sigma": sigma,
        "coefficients": coefficients,
        "n_terms_passing_expected_effect": n_passing,
        "n_terms_with_expected_effect_target": n_with_target,
        "warnings": warnings,
    }


def render_doe_power_markdown(result: dict[str, Any]) -> str:
    if "short_circuit_reason" in result:
        return f"# DoE-level power\n\nNot run: `{result['short_circuit_reason']}`\n"
    lines = ["# DoE-level power", ""]
    lines.append(f"- Runs: `{result['n_runs']}`, parameters: `{result['n_parameters']}`, df_residual: `{result['df_residual']}`")
    lines.append(f"- α = `{result['alpha']}`, target power = `{result['target_power']}`, MDE multiplier = `{result['mde_multiplier']}`")
    lines.append(f"- σ assumed: `{result['sigma']}`")
    if result["n_terms_with_expected_effect_target"]:
        lines.append(
            f"- Coefficients meeting expected_effect_size: `{result['n_terms_passing_expected_effect']}` "
            f"of `{result['n_terms_with_expected_effect_target']}`"
        )
    lines.append("")
    lines.append("| Term | kind | variance_factor | SE (σ=given) | MDE | expected | passes? |")
    lines.append("|---|---|---|---|---|---|---|")
    for coef in result["coefficients"]:
        expected = coef.get("expected_effect_size", "-")
        passes = "**yes**" if coef.get("expected_passes_mde") else ("no" if "expected_passes_mde" in coef else "-")
        lines.append(
            f"| `{coef['term']}` | {coef['kind']} | {coef['variance_factor']:.4f} | {coef['se']:.4f} | "
            f"{coef['mde_at_target_power']:.4f} | {expected} | {passes} |"
        )
    if result.get("warnings"):
        lines.append("")
        lines.append("Warnings:")
        lines.append("")
        for warn in result["warnings"]:
            lines.append(f"- `{warn}`")
    lines.append("")
    lines.append(f"> {result['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Helpers
# =====================================================================


def _expected_effects_by_factor(manifest: dict[str, Any]) -> dict[str, float]:
    """Pull per-factor expected effect size from the primary response's policy."""
    out: dict[str, float] = {}
    primary_response = None
    for response in manifest.get("responses") or []:
        if isinstance(response, dict) and response.get("assay_required"):
            primary_response = response
            break
    if primary_response is None:
        return out
    policy = primary_response.get("assay_power_policy") if isinstance(primary_response.get("assay_power_policy"), dict) else {}
    expected = policy.get("expected_effect_size")
    if expected is None:
        return out
    try:
        expected_value = float(expected)
    except (TypeError, ValueError):
        return out
    for factor in manifest.get("factors") or []:
        if isinstance(factor, dict) and factor.get("factor_id"):
            out[factor["factor_id"]] = expected_value
    return out


def _inverse_normal_cdf(p: float) -> float:
    """Beasley-Springer-Moro inverse normal approximation."""
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


__all__ = ["compute_doe_power", "render_doe_power_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
