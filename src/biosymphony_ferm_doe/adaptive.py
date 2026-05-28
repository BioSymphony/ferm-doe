"""Public adaptive follow-up and assay-power helpers.

This module is intentionally stdlib-only and conservative. It writes planning
artifacts that help a long-running agent decide what to do after first-batch
results, but it does not claim statistical optimization, validated transfer, or
physical-execution readiness.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


ADAPTIVE_ACTIONS = {
    "confirm",
    "narrow",
    "expand",
    "pause",
    "stop",
    "scale_or_downscale",
}
PLANNED_WAVE2_CLAIM = "planned_wave2_design"
LOW_TRUST_THRESHOLD = 0.6
EXCLUDED_STATUSES = {"exclude", "excluded", "false", "no", "0"}
QC_FAILED_STATUSES = {"fail", "failed", "invalid", "rejected", "outlier_excluded"}
NON_ASSAY_MEASUREMENT_TYPES = {"clock", "derived", "human_observation"}
NON_ASSAY_CLASSES = {"cost", "duration", "time", "run_duration", "schedule", "calculated_productivity"}
ASSAY_POLICY_FIELDS = (
    "minimum_detectable_effect",
    "expected_effect_size",
    "replicate_count",
    "target_power",
    "lod",
    "loq",
    "dynamic_range",
    "matrix_recovery_min",
    "turnaround_h",
)


def load_manifest(campaign_dir: Path) -> dict[str, Any]:
    """Load a campaign manifest from a campaign directory."""

    path = campaign_dir / "campaign_manifest.json"
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("campaign_manifest.json must contain a JSON object")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _public_path_label(path: Path) -> str:
    """Return a path label that is safe to persist in public artifacts."""

    if path.is_absolute():
        return path.name or "<absolute_path_redacted>"
    return path.as_posix()


def _stable_id(row: dict[str, Any], index: int) -> str:
    return str(row.get("design_run_id") or row.get("run_id") or f"row_{index + 1}")


def response_requires_assay(response: dict[str, Any]) -> bool:
    """Return whether a response should be treated as a lab-assay response."""

    if response.get("assay_required") is True:
        return True
    if response.get("assay_required") is False:
        return False
    measurement_type = str(response.get("measurement_type", "")).lower()
    response_class = str(response.get("class", "")).lower()
    if measurement_type in NON_ASSAY_MEASUREMENT_TYPES:
        return False
    if measurement_type == "assayed":
        return True
    return response_class not in NON_ASSAY_CLASSES and measurement_type not in {"instrument"}


def _iter_responses(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    responses = manifest.get("responses", [])
    out = [r for r in responses if isinstance(r, dict)] if isinstance(responses, list) else []
    seen = {response.get("response_id") for response in out}
    arms = manifest.get("arms", [])
    if isinstance(arms, list):
        for arm in arms:
            arm_responses = arm.get("responses", []) if isinstance(arm, dict) else []
            if not isinstance(arm_responses, list):
                continue
            for response in arm_responses:
                if isinstance(response, dict) and response.get("response_id") not in seen:
                    out.append(response)
                    seen.add(response.get("response_id"))
    return out


def _primary_response(manifest: dict[str, Any]) -> dict[str, Any] | None:
    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    requested = adaptive.get("primary_response_id")
    responses = _iter_responses(manifest)
    if isinstance(requested, str):
        for response in responses:
            if response.get("response_id") == requested:
                return response
    for response in responses:
        if response.get("direction") in {"maximize", "minimize", "target"}:
            return response
    return responses[0] if responses else None


def _status_rank(status: str) -> int:
    return {"FAIL": 3, "WARN": 2, "PASS": 1, "NOT_APPLICABLE": 0}.get(status, 0)


def _merge_status(statuses: list[str]) -> str:
    applicable = [status for status in statuses if status != "NOT_APPLICABLE"]
    if not applicable:
        return "NOT_APPLICABLE"
    return max(applicable, key=_status_rank)


def _dynamic_range_ok(value: Any) -> bool:
    if isinstance(value, dict):
        low = _as_float(value.get("low") or value.get("min"))
        high = _as_float(value.get("high") or value.get("max"))
        return low is not None and high is not None and low < high
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        low = _as_float(value[0])
        high = _as_float(value[1])
        return low is not None and high is not None and low < high
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def evaluate_assay_power(manifest: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    """Evaluate response-level assay power policies.

    The power value is a deterministic screening proxy, not a substitute for a
    statistician's final power calculation. It is useful for catching missing
    assay assumptions before an agent recommends another wave.
    """

    response_results: list[dict[str, Any]] = []
    for response in _iter_responses(manifest):
        rid = str(response.get("response_id", "<missing>"))
        policy = response.get("assay_power_policy")
        needs_assay = response_requires_assay(response)
        if not needs_assay:
            warnings = []
            if isinstance(policy, dict) and policy:
                warnings.append("non_assay_response_has_assay_power_policy")
            response_results.append(
                {
                    "response_id": rid,
                    "status": "NOT_APPLICABLE",
                    "assay_required": False,
                    "warnings": warnings,
                    "non_claim": "No lab-assay power gate was applied to this response.",
                }
            )
            continue

        if not isinstance(policy, dict) or not policy:
            response_results.append(
                {
                    "response_id": rid,
                    "status": "FAIL" if strict else "WARN",
                    "assay_required": True,
                    "missing_fields": list(ASSAY_POLICY_FIELDS) + ["noise_sd_or_cv_percent"],
                    "warnings": ["missing_assay_power_policy"],
                    "non_claim": "Assay power could not be evaluated without response-level policy fields.",
                }
            )
            continue

        missing = [field for field in ASSAY_POLICY_FIELDS if policy.get(field) in (None, "")]
        if policy.get("noise_sd") in (None, "") and policy.get("cv_percent") in (None, ""):
            missing.append("noise_sd_or_cv_percent")

        warnings: list[str] = []
        failures: list[str] = []
        expected = _as_float(policy.get("expected_effect_size"))
        mde = _as_float(policy.get("minimum_detectable_effect"))
        effect = expected if expected is not None else mde
        noise_sd = _as_float(policy.get("noise_sd"))
        cv_percent = _as_float(policy.get("cv_percent"))
        if noise_sd is None and cv_percent is not None and effect is not None:
            noise_sd = abs(effect) * (cv_percent / 100.0)
        replicate_count = _as_int(policy.get("replicate_count"))
        target_power = _as_float(policy.get("target_power")) or 0.8

        power_proxy: float | None = None
        if effect not in (None, 0) and noise_sd not in (None, 0) and replicate_count is not None and replicate_count > 0:
            power_proxy = min(0.99, abs(effect / noise_sd) * math.sqrt(replicate_count) / 4.0)
            if power_proxy < target_power:
                failures.append("power_proxy_below_target")
        if replicate_count is not None and replicate_count < 2:
            failures.append("replicate_count_below_2")
        if cv_percent is not None and cv_percent > 30:
            failures.append("cv_percent_above_30")
        matrix_recovery = _as_float(policy.get("matrix_recovery_min"))
        if matrix_recovery is not None and matrix_recovery < 70:
            failures.append("matrix_recovery_below_70")
        lod = _as_float(policy.get("lod"))
        loq = _as_float(policy.get("loq"))
        if lod is not None and loq is not None and loq <= lod:
            warnings.append("loq_not_above_lod")
        if policy.get("dynamic_range") not in (None, "") and not _dynamic_range_ok(policy.get("dynamic_range")):
            warnings.append("dynamic_range_not_interpretable")
        if target_power <= 0 or target_power > 0.99:
            warnings.append("target_power_outside_public_proxy_range")

        if missing:
            status = "FAIL" if strict else "WARN"
        elif failures:
            status = "FAIL"
        elif warnings:
            status = "WARN"
        else:
            status = "PASS"

        response_results.append(
            {
                "response_id": rid,
                "status": status,
                "assay_required": True,
                "missing_fields": missing,
                "failures": failures,
                "warnings": warnings,
                "replicate_count": replicate_count,
                "target_power": target_power,
                "power_proxy": round(power_proxy, 4) if power_proxy is not None else None,
                "non_claim": "Power proxy is a public planning check, not a validated statistical power calculation.",
            }
        )

    overall = _merge_status([item["status"] for item in response_results])
    return {
        "status": overall,
        "strict": strict,
        "response_results": response_results,
        "non_claim": "Assay-power output is advisory pre-experiment planning support.",
    }


def result_ingestion_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Classify first-batch result rows by joinability, QC status, and trust."""

    row_reports: list[dict[str, Any]] = []
    usable: list[dict[str, str]] = []
    usable_run_ids: list[str] = []
    excluded_run_ids: list[str] = []
    low_trust_run_ids: list[str] = []
    for index, row in enumerate(rows):
        run_id = _stable_id(row, index)
        inclusion = str(row.get("inclusion_status", "")).strip().lower()
        qc_status = str(row.get("qc_status", "")).strip().lower()
        trust = _as_float(row.get("trust_score"))
        issues: list[str] = []
        if not run_id:
            issues.append("missing_run_id")
        if inclusion in EXCLUDED_STATUSES:
            issues.append("excluded_by_inclusion_status")
        if qc_status in QC_FAILED_STATUSES:
            issues.append("qc_failed")
        if trust is not None and trust < LOW_TRUST_THRESHOLD:
            issues.append("low_trust")
            low_trust_run_ids.append(run_id)

        usable_status = not issues or issues == ["low_trust"]
        if "low_trust" in issues:
            usable_status = False
        if usable_status:
            usable.append(row)
            usable_run_ids.append(run_id)
        else:
            excluded_run_ids.append(run_id)
        row_reports.append(
            {
                "design_run_id": run_id,
                "arm_id": row.get("arm_id", ""),
                "usable_for_recommendation": usable_status,
                "trust_score": trust,
                "qc_status": row.get("qc_status", ""),
                "inclusion_status": row.get("inclusion_status", ""),
                "issues": issues,
            }
        )

    return {
        "status": "PASS" if usable else "WARN",
        "input_row_count": len(rows),
        "usable_row_count": len(usable),
        "excluded_row_count": len(rows) - len(usable),
        "usable_run_ids": usable_run_ids,
        "excluded_run_ids": excluded_run_ids,
        "low_trust_run_ids": low_trust_run_ids,
        "rows": row_reports,
        "non_claim": "Ingestion validates public planning joins and QC flags; it does not validate raw lab data.",
    }


def _factor_list(manifest: dict[str, Any], active_arm_id: str | None = None) -> list[dict[str, Any]]:
    if active_arm_id:
        arms = manifest.get("arms", [])
        if isinstance(arms, list):
            for arm in arms:
                if isinstance(arm, dict) and arm.get("arm_id") == active_arm_id:
                    factors = arm.get("factors", [])
                    return [f for f in factors if isinstance(f, dict)] if isinstance(factors, list) else []
    factors = manifest.get("factors", [])
    return [f for f in factors if isinstance(f, dict)] if isinstance(factors, list) else []


def _all_factor_ids(manifest: dict[str, Any]) -> set[str]:
    ids = {factor.get("factor_id") for factor in _factor_list(manifest) if isinstance(factor.get("factor_id"), str)}
    arms = manifest.get("arms", [])
    if isinstance(arms, list):
        for arm in arms:
            factors = arm.get("factors", []) if isinstance(arm, dict) else []
            if isinstance(factors, list):
                ids.update(factor.get("factor_id") for factor in factors if isinstance(factor, dict) and isinstance(factor.get("factor_id"), str))
    return {fid for fid in ids if isinstance(fid, str)}


def _score_response(value: float, direction: str, target: float | None) -> float:
    if direction == "minimize":
        return -value
    if direction == "target" and target is not None:
        return -abs(value - target)
    return value


def _boundary_factor_ids(best_row: dict[str, str], factors: list[dict[str, Any]]) -> list[str]:
    boundary: list[str] = []
    for factor in factors:
        fid = factor.get("factor_id")
        if not isinstance(fid, str) or factor.get("type") != "numeric" or fid not in best_row:
            continue
        value = _as_float(best_row.get(fid))
        low = _as_float(factor.get("low"))
        high = _as_float(factor.get("high"))
        if value is None or low is None or high is None or high <= low:
            continue
        tolerance = (high - low) * 0.05
        if value <= low + tolerance or value >= high - tolerance:
            boundary.append(fid)
    return boundary


def _bridge_eligibility(manifest: dict[str, Any]) -> dict[str, Any]:
    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    policy = adaptive.get("bridge_policy") if isinstance(adaptive.get("bridge_policy"), dict) else None
    if policy is None and isinstance(manifest.get("arm_bridge_policy"), dict):
        policy = manifest.get("arm_bridge_policy")
    if policy is None:
        return {
            "status": "FAIL",
            "reasons": ["bridge_policy_missing"],
            "non_claim": "No scale or downscale branch can be planned without an explicit bridge policy.",
        }

    reasons: list[str] = []
    for field in ("source_arm", "target_arm"):
        if not policy.get(field):
            reasons.append(f"{field}_missing")
    comparability = str(policy.get("assay_comparability", "")).lower()
    if comparability not in {"pass", "passed", "comparable", "qualified", "qualified_with_caveats"}:
        reasons.append("assay_comparability_not_passing")
    minimum_evidence = policy.get("minimum_evidence")
    if minimum_evidence in (None, "", [], {}):
        reasons.append("minimum_evidence_missing")
    forbidden = policy.get("forbidden_transfer")
    if forbidden not in (None, "", [], {}):
        reasons.append("forbidden_transfer_declared")
    status = "PASS" if not reasons else "FAIL"
    return {
        "status": status,
        "source_arm": policy.get("source_arm"),
        "target_arm": policy.get("target_arm"),
        "reasons": reasons,
        "non_claim": "Bridge eligibility allows planning next-arm candidates only, not validated scale transfer.",
    }


def recommend_wave2(
    manifest: dict[str, Any],
    usable_rows: list[dict[str, str]],
    *,
    goals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a conservative follow-up recommendation from usable result rows.

    When ``goals`` is provided (typically from :func:`goals.formulate_goals`),
    best-run selection uses composite desirability across all declared
    objectives instead of single-response scoring. Otherwise the legacy
    primary-response score path is used.

    Recommendations are post-filtered against ``adaptive_wave2.allowed_actions``
    when declared. A natural recommendation outside the allowed list is
    downgraded to ``pause`` so the operator can review.
    """

    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    natural = _recommend_wave2_inner(manifest, usable_rows, goals=goals)
    return _enforce_allowed_actions(natural, adaptive)


def _enforce_allowed_actions(recommendation: dict[str, Any], adaptive: dict[str, Any]) -> dict[str, Any]:
    """Downgrade a recommendation to pause when its action is not allowed.

    ``pause`` is always allowed because it is the conservative non-action.
    """

    allowed = adaptive.get("allowed_actions")
    if not isinstance(allowed, list) or not allowed:
        return recommendation
    action = recommendation.get("recommended_action")
    if action == "pause" or action in allowed:
        return recommendation
    return {
        **recommendation,
        "original_recommended_action": action,
        "recommended_action": "pause",
        "reason": f"original_action_{action}_not_in_allowed_actions",
        "allowed_actions": list(allowed),
        "claim_level": PLANNED_WAVE2_CLAIM,
    }


def _recommend_wave2_inner(
    manifest: dict[str, Any],
    usable_rows: list[dict[str, str]],
    *,
    goals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Internal recommendation logic prior to allowed-actions enforcement."""

    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    active_arm_id = adaptive.get("active_arm_id") if isinstance(adaptive.get("active_arm_id"), str) else None
    arm_ids = sorted({row.get("arm_id", "") for row in usable_rows if row.get("arm_id")})
    if len(arm_ids) > 1 and not active_arm_id:
        return {
            "recommended_action": "pause",
            "reason": "multiple_arms_require_active_arm_or_per_arm_review",
            "arm_ids": arm_ids,
            "claim_level": PLANNED_WAVE2_CLAIM,
            "non_claim": "No pooled cross-arm narrowing was performed.",
        }
    if active_arm_id:
        usable_rows = [row for row in usable_rows if row.get("arm_id") in {"", active_arm_id}]

    response = _primary_response(manifest)
    if not response:
        return {
            "recommended_action": "pause",
            "reason": "no_primary_response_declared",
            "claim_level": PLANNED_WAVE2_CLAIM,
        }
    rid = str(response.get("response_id"))
    direction = str(response.get("direction", "maximize"))
    target = _as_float(response.get("target") or response.get("target_value"))

    scoring_mode = "desirability" if goals and goals.get("objectives") else "single_response"

    scored: list[tuple[float, float, dict[str, str]]] = []
    for row in usable_rows:
        value = _as_float(row.get(rid))
        if value is None:
            continue
        if scoring_mode == "desirability":
            from .goals import evaluate_desirability

            evaluation = evaluate_desirability(goals, row)
            composite = evaluation.get("composite")
            if composite is None:
                continue
            scored.append((value, float(composite), row))
        else:
            scored.append((value, _score_response(value, direction, target), row))
    if len(scored) < 2:
        return {
            "recommended_action": "pause",
            "primary_response_id": rid,
            "reason": "insufficient_numeric_usable_results",
            "usable_numeric_count": len(scored),
            "scoring_mode": scoring_mode,
            "claim_level": PLANNED_WAVE2_CLAIM,
        }

    scores = [score for _, score, _ in scored]
    best_value, best_score, best_row = max(scored, key=lambda item: (item[1], _stable_id(item[2], 0)))
    median = statistics.median(scores)
    score_range = max(scores) - min(scores)
    denominator = max(abs(median), 1.0)
    relative_range = score_range / denominator
    improvement_vs_median = (best_score - median) / denominator
    boundary_ids = _boundary_factor_ids(best_row, _factor_list(manifest, active_arm_id))

    requested = adaptive.get("requested_action") or adaptive.get("target_action")
    if requested == "scale_or_downscale":
        bridge = _bridge_eligibility(manifest)
        if bridge["status"] != "PASS":
            return {
                "recommended_action": "pause",
                "primary_response_id": rid,
                "reason": "scale_or_downscale_blocked_by_bridge_eligibility",
                "bridge_eligibility": bridge,
                "claim_level": PLANNED_WAVE2_CLAIM,
            }
        return {
            "recommended_action": "scale_or_downscale",
            "primary_response_id": rid,
            "best_run_id": _stable_id(best_row, 0),
            "best_value": best_value,
            "bridge_eligibility": bridge,
            "scoring_mode": scoring_mode,
            "claim_level": PLANNED_WAVE2_CLAIM,
            "non_claim": "Recommendation plans next-arm candidates only.",
        }

    if relative_range < 0.05:
        action = "stop"
        reason = "flat_response"
    elif boundary_ids:
        action = "expand"
        reason = "best_run_on_factor_boundary"
    elif improvement_vs_median >= 0.25:
        action = "narrow"
        reason = "strong_non_boundary_winner"
    else:
        action = "confirm"
        reason = "modest_winner"

    output = {
        "recommended_action": action,
        "primary_response_id": rid,
        "response_direction": direction,
        "best_run_id": _stable_id(best_row, 0),
        "best_value": best_value,
        "best_arm_id": best_row.get("arm_id", active_arm_id or ""),
        "relative_range": round(relative_range, 4),
        "improvement_vs_median": round(improvement_vs_median, 4),
        "boundary_factor_ids": boundary_ids,
        "reason": reason,
        "scoring_mode": scoring_mode,
        "claim_level": PLANNED_WAVE2_CLAIM,
        "non_claim": "Recommendation is a planned follow-up decision, not validated optimization.",
    }
    if scoring_mode == "desirability":
        output["best_desirability"] = round(best_score, 6)
    return output


def _negative_memory(manifest: dict[str, Any], usable_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    response = _primary_response(manifest)
    if not response:
        return []
    rid = str(response.get("response_id"))
    direction = str(response.get("direction", "maximize"))
    target = _as_float(response.get("target") or response.get("target_value"))
    scored = []
    for index, row in enumerate(usable_rows):
        value = _as_float(row.get(rid))
        if value is None:
            continue
        scored.append((_score_response(value, direction, target), value, index, row))
    if len(scored) < 3:
        return []
    scores = sorted(score for score, _, _, _ in scored)
    cutoff = scores[max(0, math.floor(len(scores) * 0.25) - 1)]
    factors = _all_factor_ids(manifest)
    memory: list[dict[str, Any]] = []
    for score, value, index, row in scored:
        if score > cutoff:
            continue
        memory.append(
            {
                "memory_id": f"NEG-{len(memory) + 1:03d}",
                "arm_id": row.get("arm_id", ""),
                "design_run_id": _stable_id(row, index),
                "primary_response_id": rid,
                "observed_value": value,
                "reason": "low_scoring_region_for_declared_direction",
                "factor_snapshot": {fid: row.get(fid, "") for fid in sorted(factors) if fid in row},
                "scope": "arm_scoped_by_default",
            }
        )
    return memory


def _result_rows_from_report(rows: list[dict[str, str]], report: dict[str, Any]) -> list[dict[str, str]]:
    usable_ids = set(report.get("usable_run_ids", []))
    out: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        if _stable_id(row, index) in usable_ids:
            out.append(row)
    return out


def _best_row_for_recommendation(manifest: dict[str, Any], usable_rows: list[dict[str, str]]) -> dict[str, str] | None:
    response = _primary_response(manifest)
    if not response:
        return None
    rid = str(response.get("response_id"))
    direction = str(response.get("direction", "maximize"))
    target = _as_float(response.get("target") or response.get("target_value"))
    scored = []
    for index, row in enumerate(usable_rows):
        value = _as_float(row.get(rid))
        if value is not None:
            scored.append((_score_response(value, direction, target), index, row))
    if not scored:
        return None
    return max(scored, key=lambda item: (item[0], -item[1]))[2]


def _generate_augment_rows(
    manifest: dict[str, Any],
    recommendation: dict[str, Any],
    usable_rows: list[dict[str, str]],
    remaining_budget: int,
    *,
    wave2_signal: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate follow-up augment-candidate rows.

    When ``wave2_signal`` is provided (from :func:`analysis.analyze_results`),
    narrow rows are biased along the ascent direction on active factors and
    hold inactive factors at their best-row value. Expand rows extend past
    the boundary in the ascent direction on active factors, holding inactive
    factors at center. Without a signal, fall back to legacy symmetric
    narrowing.
    """
    action = recommendation.get("recommended_action")
    if action in {"pause", "stop"}:
        return []
    best_row = _best_row_for_recommendation(manifest, usable_rows)
    if best_row is None:
        return []
    active_arm_id = best_row.get("arm_id") or recommendation.get("best_arm_id") or None
    factors = _factor_list(manifest, str(active_arm_id) if active_arm_id else None)
    count = max(0, min(remaining_budget, 3))

    signal_index = _build_signal_index(wave2_signal) if wave2_signal else {}
    predicted_optimum = (
        wave2_signal.get("predicted_optimum") if isinstance(wave2_signal, dict) else None
    )
    optimum_engineering: dict[str, float] = {}
    use_predicted_optimum = False
    if isinstance(predicted_optimum, dict):
        engineering = predicted_optimum.get("engineering_units") or {}
        if predicted_optimum.get("interior_to_factor_ranges") and engineering:
            optimum_engineering = engineering
            use_predicted_optimum = True
    legacy_narrow_multipliers = (-1, 1, -2)
    informed_narrow_multipliers = (1, 2, 3)  # all in ascent direction, increasing tightness
    informed_expand_multipliers = (1, 2, 3)
    informed_step_scale = 0.05  # tighter step when we have signal
    legacy_step_scale = 0.1
    optimum_fractions = (0.25, 0.5, 0.75)  # interpolation toward predicted optimum

    rows: list[dict[str, Any]] = []
    for offset in range(count):
        row: dict[str, Any] = {
            "design_run_id": f"AUG-{offset + 1:03d}",
            "arm_id": active_arm_id or "",
            "planned_status": "planned_candidate",
            "source_action": action,
            "source_best_run_id": recommendation.get("best_run_id", ""),
            "claim_level": PLANNED_WAVE2_CLAIM,
        }
        if action == "expand":
            row["planned_status"] = "factor_space_expansion_required"
        if signal_index:
            row["scoring_mode"] = "model_informed_optimum" if use_predicted_optimum else "model_informed"
        for factor in factors:
            fid = factor.get("factor_id")
            if not isinstance(fid, str):
                continue
            ftype = factor.get("type")
            if ftype == "numeric":
                best_value = _as_float(best_row.get(fid))
                low = _as_float(factor.get("low"))
                high = _as_float(factor.get("high"))
                if best_value is None and low is not None and high is not None:
                    best_value = (low + high) / 2.0
                if action not in {"narrow", "expand"} or low is None or high is None or best_value is None:
                    row[fid] = best_value if best_value is not None else ""
                    continue
                signal = signal_index.get(fid)
                if signal is not None and signal.get("active"):
                    if action == "narrow" and use_predicted_optimum and fid in optimum_engineering:
                        target = optimum_engineering[fid]
                        fraction = optimum_fractions[offset] if offset < len(optimum_fractions) else 0.75
                        value = best_value + fraction * (target - best_value)
                        row[fid] = round(min(max(value, low), high), 6)
                        continue
                    sign = int(signal.get("ascent_sign", 0))
                    if sign == 0:
                        row[fid] = round(best_value, 6)
                        continue
                    if action == "narrow":
                        step = (high - low) * informed_step_scale
                        multiplier = informed_narrow_multipliers[offset] if offset < len(informed_narrow_multipliers) else 1
                        value = best_value + sign * multiplier * step
                        row[fid] = round(min(max(value, low), high), 6)
                    else:  # expand: push past the boundary in the ascent direction
                        boundary = high if sign > 0 else low
                        step = (high - low) * 0.1
                        multiplier = informed_expand_multipliers[offset] if offset < len(informed_expand_multipliers) else 1
                        value = boundary + sign * multiplier * step
                        row[fid] = round(value, 6)
                elif signal is not None and not signal.get("active"):
                    if action == "narrow":
                        row[fid] = round(best_value, 6)
                    else:
                        row[fid] = round((low + high) / 2.0, 6)
                else:
                    if action == "narrow":
                        step = (high - low) * legacy_step_scale
                        multiplier = legacy_narrow_multipliers[offset] if offset < len(legacy_narrow_multipliers) else 0
                        value = best_value + multiplier * step
                        row[fid] = round(min(max(value, low), high), 6)
                    else:
                        row[fid] = best_value
            elif ftype in {"categorical", "ordinal", "block"}:
                levels = factor.get("levels") if isinstance(factor.get("levels"), list) else []
                row[fid] = best_row.get(fid) or (levels[0] if levels else "")
        rows.append(row)
    return rows


def _build_signal_index(wave2_signal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in wave2_signal.get("per_factor", []) or []:
        fid = entry.get("factor_id")
        if isinstance(fid, str):
            index[fid] = entry
    return index


def _locked_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    locked = []
    for index, row in enumerate(rows):
        locked.append(
            {
                "design_run_id": _stable_id(row, index),
                "arm_id": row.get("arm_id", ""),
                "locked_reason": "observed_wave1_result",
                "qc_status": row.get("qc_status", ""),
                "inclusion_status": row.get("inclusion_status", ""),
                "trust_score": row.get("trust_score", ""),
            }
        )
    return locked


def _learning_ledger(
    ingestion: dict[str, Any],
    assay_power: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if ingestion.get("excluded_row_count", 0):
        rows.append(
            {
                "learning_id": "LEARN-001",
                "scope": "results",
                "event_type": "hiccup",
                "trigger": "qc_or_trust_exclusion",
                "observation": f"{ingestion['excluded_row_count']} row(s) excluded before follow-up recommendation.",
                "action_taken": "Use only trusted and QC-passing rows for recommendation.",
                "status": "open",
                "owner_role": "agent_or_scientist",
                "follow_up_ref": "result_ingestion_report.json",
            }
        )
    if assay_power.get("status") in {"WARN", "FAIL"}:
        rows.append(
            {
                "learning_id": f"LEARN-{len(rows) + 1:03d}",
                "scope": "responses",
                "event_type": "assay_power",
                "trigger": str(assay_power.get("status")),
                "observation": "One or more response assay-power policies need review.",
                "action_taken": "Review assay_power_results.json before committing follow-up rows.",
                "status": "open",
                "owner_role": "assay_owner",
                "follow_up_ref": "assay_power_results.json",
            }
        )
    if recommendation.get("recommended_action") in {"pause", "stop"}:
        rows.append(
            {
                "learning_id": f"LEARN-{len(rows) + 1:03d}",
                "scope": "wave2",
                "event_type": "decision",
                "trigger": str(recommendation.get("reason", recommendation.get("recommended_action"))),
                "observation": f"Recommendation is {recommendation.get('recommended_action')}.",
                "action_taken": "Record rationale and require human review before changing direction.",
                "status": "open",
                "owner_role": "campaign_owner",
                "follow_up_ref": "wave2_recommendation.json",
            }
        )
    if not rows:
        rows.append(
            {
                "learning_id": "LEARN-001",
                "scope": "campaign",
                "event_type": "monitor",
                "trigger": "no_hiccup_flagged",
                "observation": "No QC, trust, assay-power, or follow-up decision hiccup was flagged.",
                "action_taken": "Carry learning ledger forward to the next experiment round.",
                "status": "monitoring",
                "owner_role": "agent_or_scientist",
                "follow_up_ref": "adaptive_trace.json",
            }
        )
    return rows


def _recommendation_md(recommendation: dict[str, Any]) -> str:
    lines = [
        "# Follow-Up Recommendation",
        "",
        f"- Recommended action: `{recommendation.get('recommended_action', 'pause')}`",
        f"- Claim level: `{recommendation.get('claim_level', PLANNED_WAVE2_CLAIM)}`",
        f"- Primary response: `{recommendation.get('primary_response_id', '<not selected>')}`",
        f"- Reason: `{recommendation.get('reason', '<none>')}`",
        "",
        "This is a planned follow-up recommendation. It is not a validated optimization,",
        "scale-transfer claim, GxP execution record, or substitute for statistical review.",
        "",
    ]
    return "\n".join(lines)


def _hiccup_md(learning_rows: list[dict[str, str]]) -> str:
    lines = [
        "# DOE Learning And Hiccup Review",
        "",
        "Use this file as the human-readable companion to `learning_ledger.csv`.",
        "Each entry should either be closed with evidence or carried into the next experiment round.",
        "",
    ]
    for row in learning_rows:
        lines.extend(
            [
                f"## {row['learning_id']} - {row['event_type']}",
                "",
                f"- Scope: `{row['scope']}`",
                f"- Trigger: `{row['trigger']}`",
                f"- Observation: {row['observation']}",
                f"- Action: {row['action_taken']}",
                f"- Status: `{row['status']}`",
                "",
            ]
        )
    return "\n".join(lines)


def plan_wave2(
    campaign_dir: Path,
    results_path: Path,
    out_dir: Path,
    *,
    selected_design_path: Path | None = None,
    remaining_budget: int | None = None,
) -> dict[str, Any]:
    """Write public-safe adaptive follow-up planning artifacts."""

    manifest = load_manifest(campaign_dir)
    rows = _read_csv(results_path)
    ingestion = result_ingestion_report(rows)
    usable_rows = _result_rows_from_report(rows, ingestion)
    assay_power = evaluate_assay_power(manifest, strict=False)
    from .goals import formulate_goals

    goals = formulate_goals(manifest)
    recommendation = recommend_wave2(manifest, usable_rows, goals=goals)

    analysis: dict[str, Any] | None = None
    wave2_signal: dict[str, Any] | None = None
    if len(usable_rows) >= 4:
        from .analysis import analyze_results

        try:
            analysis = analyze_results(manifest, list(usable_rows), seed=0, n_permutations=200, n_bootstrap=200)
            if not analysis.get("short_circuit_reason"):
                wave2_signal = analysis.get("wave2_signal")
        except Exception:  # noqa: BLE001  defensive — analysis must never break planning
            analysis = None
            wave2_signal = None
    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    budget = remaining_budget if remaining_budget is not None else _as_int(adaptive.get("remaining_budget"))
    if budget is None:
        budget = 3
    augment_rows = _generate_augment_rows(manifest, recommendation, usable_rows, budget, wave2_signal=wave2_signal)
    negative_memory = _negative_memory(manifest, usable_rows)
    learning_rows = _learning_ledger(ingestion, assay_power, recommendation)

    selected_design_check: dict[str, Any] = {"status": "NOT_PROVIDED"}
    if selected_design_path is not None:
        selected_design_check = {
            "status": "PASS" if selected_design_path.is_file() else "FAIL",
            "path": _public_path_label(selected_design_path),
            "non_claim": "Join check only verifies file presence in the public scaffold.",
        }

    artifact_list = [
        "result_ingestion_report.json",
        "assay_power_results.json",
        "wave2_recommendation.json",
        "wave2_recommendation.md",
        "locked_prior_runs.csv",
        "augment_design.csv",
        "adaptive_trace.json",
        "negative_result_memory.json",
        "learning_ledger.csv",
        "hiccup_review.md",
        "wave2_manifest.patch.json",
    ]
    if goals is not None:
        artifact_list.append("optimization_goals.json")
    if analysis is not None and not analysis.get("short_circuit_reason"):
        artifact_list.append("wave1_analysis.json")

    plan = {
        "campaign_id": manifest.get("campaign_id"),
        "claim_level": PLANNED_WAVE2_CLAIM,
        "recommended_action": recommendation.get("recommended_action"),
        "primary_response_id": recommendation.get("primary_response_id"),
        "scoring_mode": recommendation.get("scoring_mode", "single_response"),
        "artifacts": artifact_list,
        "non_claim": "Adaptive follow-up artifacts are planning support only.",
    }

    manifest_patch = {
        "claim_level": PLANNED_WAVE2_CLAIM,
        "adaptive_wave2": {
            "primary_response_id": recommendation.get("primary_response_id"),
            "recommended_action": recommendation.get("recommended_action"),
            "claim_level": PLANNED_WAVE2_CLAIM,
            "negative_memory_ref": "negative_result_memory.json",
            "learning_ledger_ref": "learning_ledger.csv",
            "non_claim": "Patch is a suggested manifest update, not an automatic physical-execution approval.",
        },
    }
    adaptive_trace = {
        "campaign_id": manifest.get("campaign_id"),
        "inputs": {
            "campaign_dir": _public_path_label(campaign_dir),
            "results_path": _public_path_label(results_path),
            "selected_design_check": selected_design_check,
        },
        "ingestion_status": ingestion.get("status"),
        "assay_power_status": assay_power.get("status"),
        "recommendation": recommendation,
        "augment_row_count": len(augment_rows),
        "negative_memory_count": len(negative_memory),
        "claim_level": PLANNED_WAVE2_CLAIM,
        "non_claim": "Trace is deterministic public planning metadata.",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "adaptive_wave2_plan.json", plan)
    _write_json(out_dir / "result_ingestion_report.json", ingestion)
    _write_json(out_dir / "assay_power_results.json", assay_power)
    _write_json(out_dir / "wave2_recommendation.json", recommendation)
    (out_dir / "wave2_recommendation.md").write_text(_recommendation_md(recommendation), encoding="utf-8")
    _write_csv(
        out_dir / "locked_prior_runs.csv",
        _locked_rows(rows),
        ["design_run_id", "arm_id", "locked_reason", "qc_status", "inclusion_status", "trust_score"],
    )
    augment_fields = ["design_run_id", "arm_id", "planned_status", "source_action", "source_best_run_id", "claim_level"]
    for row in augment_rows:
        for key in row:
            if key not in augment_fields:
                augment_fields.append(key)
    _write_csv(out_dir / "augment_design.csv", augment_rows, augment_fields)
    _write_json(out_dir / "adaptive_trace.json", adaptive_trace)
    _write_json(out_dir / "negative_result_memory.json", {"items": negative_memory, "scope": "arm_scoped_by_default"})
    _write_csv(
        out_dir / "learning_ledger.csv",
        learning_rows,
        ["learning_id", "scope", "event_type", "trigger", "observation", "action_taken", "status", "owner_role", "follow_up_ref"],
    )
    (out_dir / "hiccup_review.md").write_text(_hiccup_md(learning_rows), encoding="utf-8")
    _write_json(out_dir / "wave2_manifest.patch.json", manifest_patch)
    if goals is not None:
        _write_json(out_dir / "optimization_goals.json", goals)
    if analysis is not None and not analysis.get("short_circuit_reason"):
        _write_json(out_dir / "wave1_analysis.json", analysis)
    return plan
