"""Response-level assay power checks for adaptive Ferm DoE planning."""

from __future__ import annotations

import math
import statistics
from typing import Any

from .io_utils import parse_number
from .workflow_modes import response_requires_assay


PASSING_STATUSES = {"PASS", "NOT_APPLICABLE"}


def evaluate_assay_power(
    state: dict[str, Any],
    result_rows: list[dict[str, Any]] | None = None,
    *,
    strict: bool | None = None,
) -> dict[str, Any]:
    """Evaluate assay power policies without pretending to be a full stats package."""

    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    strict_mode = bool(policy.get("require_assay_power")) if strict is None else bool(strict)
    result_rows = result_rows or []
    responses = state.get("responses", []) if isinstance(state.get("responses"), list) else []
    items = [_evaluate_response_power(state, response, result_rows, strict_mode) for response in responses if isinstance(response, dict)]
    assay_items = [item for item in items if item["status"] != "NOT_APPLICABLE"]
    if not assay_items:
        status = "PASS"
        score = 1.0
    elif any(item["status"] == "FAIL" for item in assay_items):
        status = "FAIL"
        score = min(item["score"] for item in assay_items)
    elif any(item["status"] == "WARN" for item in assay_items):
        status = "WARN"
        score = sum(item["score"] for item in assay_items) / len(assay_items)
    else:
        status = "PASS"
        score = sum(item["score"] for item in assay_items) / len(assay_items)
    primary_id = str(state.get("objective", {}).get("response_id") or "")
    primary = next((item for item in items if item.get("response_id") == primary_id), None)
    return {
        "schema_version": 1,
        "assessment_kind": "ferm_doe_assay_power",
        "campaign_id": state.get("campaign_id"),
        "status": status,
        "score": round(max(0.0, min(1.0, score)), 3),
        "strict": strict_mode,
        "primary_response_id": primary_id,
        "primary_status": (primary or {}).get("status", "missing"),
        "primary_score": (primary or {}).get("score", 0.0),
        "items": items,
        "summary": {
            "response_count": len(items),
            "assayed_response_count": len(assay_items),
            "pass_count": sum(1 for item in assay_items if item["status"] == "PASS"),
            "warn_count": sum(1 for item in assay_items if item["status"] == "WARN"),
            "fail_count": sum(1 for item in assay_items if item["status"] == "FAIL"),
            "not_applicable_count": sum(1 for item in items if item["status"] == "NOT_APPLICABLE"),
        },
    }


def _evaluate_response_power(
    state: dict[str, Any],
    response: dict[str, Any],
    result_rows: list[dict[str, Any]],
    strict: bool,
) -> dict[str, Any]:
    response_id = str(response.get("response_id") or "")
    if not response_requires_assay(response):
        return {
            "response_id": response_id,
            "status": "NOT_APPLICABLE",
            "score": 1.0,
            "requires_assay": False,
            "issues": ["Response is calculated, clock-based, or derived; lab-assay power requirements are not applied."],
            "metrics": {},
        }

    policy = _merged_policy(response)
    issues: list[dict[str, str]] = []
    if not policy:
        severity = "FAIL" if strict else "WARN"
        return {
            "response_id": response_id,
            "status": severity,
            "score": 0.35 if strict else 0.45,
            "requires_assay": True,
            "issues": [{"severity": "warning", "field": f"response:{response_id}:assay_power_policy", "message": "Assay-power policy is not declared."}],
            "metrics": {},
        }

    historical = _historical_metrics(state, response_id, result_rows)
    minimum_effect = _number(policy, ["minimum_detectable_effect", "minimum_detectable_effect_abs", "mde"])
    expected_effect = _number(policy, ["expected_effect_size", "expected_effect", "expected_delta"])
    noise_sd = _number(policy, ["noise_sd", "sigma", "assay_sd", "expected_noise_sd"])
    cv_percent = _number(policy, ["cv_percent", "cv", "expected_cv_percent"])
    if noise_sd is None and expected_effect is not None and cv_percent is not None:
        noise_sd = abs(expected_effect) * cv_percent / 100.0
    if noise_sd is None:
        noise_sd = historical.get("historical_noise_sd")
    replicate_count = _int(policy, ["replicate_count", "replicates", "n_replicates"])
    if replicate_count is None:
        replicate_count = historical.get("max_replicate_count")
    target_power = _number(policy, ["target_power", "minimum_power"]) or 0.8
    lod = _number(policy, ["lod", "limit_of_detection"])
    loq = _number(policy, ["loq", "limit_of_quantitation"])
    recovery = _number(policy, ["matrix_recovery_min", "matrix_recovery_percent", "matrix_recovery"])
    dynamic_low, dynamic_high = _dynamic_range(policy)
    turnaround_h = _number(policy, ["turnaround_h", "turnaround_time_h", "assay_turnaround_h"])

    if minimum_effect is None:
        issues.append(_issue("warning", "minimum_detectable_effect", "Minimum detectable effect is not declared."))
    if expected_effect is None:
        issues.append(_issue("warning", "expected_effect_size", "Expected effect size is not declared."))
    if noise_sd is None:
        issues.append(_issue("warning", "noise_sd", "Noise SD or CV is not declared and could not be inferred from repeated results."))
    if replicate_count is None:
        issues.append(_issue("warning", "replicate_count", "Replicate count is not declared."))
    elif replicate_count < 2:
        issues.append(_issue("warning", "replicate_count", "Replicate count is below 2."))
    if loq is None:
        issues.append(_issue("warning", "loq", "LOQ is not declared."))
    if lod is None:
        issues.append(_issue("warning", "lod", "LOD is not declared."))
    if dynamic_low is None or dynamic_high is None or dynamic_high <= dynamic_low:
        issues.append(_issue("warning", "dynamic_range", "Assay dynamic range is incomplete."))
    if recovery is not None and recovery < 70:
        issues.append(_issue("blocker", "matrix_recovery_min", "Matrix recovery is below 70%."))
    elif recovery is not None and recovery < 80:
        issues.append(_issue("warning", "matrix_recovery_min", "Matrix recovery is below 80%."))
    if cv_percent is not None and cv_percent > 30:
        issues.append(_issue("blocker", "cv_percent", "Assay CV is above 30%."))
    elif cv_percent is not None and cv_percent > 20:
        issues.append(_issue("warning", "cv_percent", "Assay CV is above 20%."))
    if turnaround_h is None:
        issues.append(_issue("warning", "turnaround_h", "Assay turnaround is not declared."))

    power_proxy = _power_proxy(expected_effect, minimum_effect, noise_sd, replicate_count)
    if power_proxy is None:
        issues.append(_issue("warning", "power_proxy", "Power proxy could not be calculated."))
    elif power_proxy < target_power:
        issues.append(_issue("blocker", "target_power", f"Calculated power proxy {power_proxy:.3g} is below target {target_power:.3g}."))

    blocker_count = sum(1 for item in issues if item["severity"] == "blocker")
    warning_count = sum(1 for item in issues if item["severity"] == "warning")
    if blocker_count:
        status = "FAIL"
    elif warning_count:
        status = "WARN"
    else:
        status = "PASS"
    if strict and status == "WARN" and any(item["field"] in {"minimum_detectable_effect", "expected_effect_size", "noise_sd", "replicate_count"} for item in issues):
        status = "FAIL"
    issue_penalty = 0.16 * blocker_count + 0.065 * warning_count
    if power_proxy is not None:
        power_score = min(1.0, power_proxy / max(target_power, 1e-9))
    else:
        power_score = 0.45
    score = max(0.0, min(1.0, 0.72 * power_score + 0.28 * max(0.0, 1.0 - issue_penalty)))
    if status == "FAIL":
        score = min(score, 0.44)
    elif status == "WARN":
        score = min(score, 0.68)

    return {
        "response_id": response_id,
        "status": status,
        "score": round(score, 3),
        "requires_assay": True,
        "issues": issues,
        "metrics": {
            "minimum_detectable_effect": minimum_effect,
            "expected_effect_size": expected_effect,
            "noise_sd": noise_sd,
            "cv_percent": cv_percent,
            "replicate_count": replicate_count,
            "target_power": target_power,
            "power_proxy": power_proxy,
            "lod": lod,
            "loq": loq,
            "dynamic_range_min": dynamic_low,
            "dynamic_range_max": dynamic_high,
            "matrix_recovery_min": recovery,
            "turnaround_h": turnaround_h,
            **historical,
        },
    }


def _merged_policy(response: dict[str, Any]) -> dict[str, Any]:
    policy = response.get("assay_power_policy") if isinstance(response.get("assay_power_policy"), dict) else {}
    merged = dict(policy)
    for key in [
        "minimum_detectable_effect",
        "expected_effect_size",
        "noise_sd",
        "cv_percent",
        "replicate_count",
        "target_power",
        "lod",
        "loq",
        "dynamic_range",
        "matrix_recovery_min",
        "turnaround_h",
    ]:
        if key in response and key not in merged:
            merged[key] = response[key]
    return merged


def _historical_metrics(state: dict[str, Any], response_id: str, result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [parse_number(row.get(response_id)) for row in result_rows]
    numeric = [value for value in values if value is not None]
    noise_sd = statistics.stdev(numeric) if len(numeric) >= 2 else None
    factors = state.get("factors", []) if isinstance(state.get("factors"), list) else []
    factor_ids = [str(factor.get("factor_id") or "") for factor in factors if factor.get("factor_id")]
    counts: dict[tuple[str, ...], int] = {}
    for row in result_rows:
        key = tuple(str(row.get(factor_id, "")) for factor_id in factor_ids)
        counts[key] = counts.get(key, 0) + 1
    return {
        "historical_numeric_count": len(numeric),
        "historical_noise_sd": noise_sd,
        "max_replicate_count": max(counts.values()) if counts else None,
    }


def _power_proxy(
    expected_effect: float | None,
    minimum_effect: float | None,
    noise_sd: float | None,
    replicate_count: int | None,
) -> float | None:
    effect = expected_effect if expected_effect is not None else minimum_effect
    if effect is None or noise_sd is None or noise_sd <= 0 or replicate_count is None or replicate_count <= 0:
        return None
    standardized = abs(effect) / noise_sd
    return round(max(0.0, min(0.99, (standardized * math.sqrt(replicate_count)) / 4.0)), 3)


def _issue(severity: str, field: str, message: str) -> dict[str, str]:
    return {"severity": severity, "field": field, "message": message}


def _number(policy: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = parse_number(policy.get(key))
        if value is not None:
            return value
    return None


def _int(policy: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = parse_number(policy.get(key))
        if value is not None:
            return int(value)
    return None


def _dynamic_range(policy: dict[str, Any]) -> tuple[float | None, float | None]:
    raw = policy.get("dynamic_range")
    if isinstance(raw, list) and len(raw) >= 2:
        return parse_number(raw[0]), parse_number(raw[1])
    if isinstance(raw, dict):
        return parse_number(raw.get("min") or raw.get("low")), parse_number(raw.get("max") or raw.get("high"))
    return _number(policy, ["dynamic_range_min", "range_min"]), _number(policy, ["dynamic_range_max", "range_max"])
