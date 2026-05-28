"""Batch result ingestion and next-round recommendation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .campaign_arms import campaign_arms_enabled, evaluate_bridge_policy, multi_arm_factor_ids
from .io_utils import load_json, parse_number, read_csv, write_json


ACTIONS = {"confirm", "narrow", "expand", "pause", "stop", "scale_or_downscale"}
EXCLUDED_INCLUSION_STATUSES = {"exclude", "excluded", "failed", "fail", "rejected", "invalid", "omit"}
FAILED_QC_STATUSES = {"fail", "failed", "invalid", "rejected", "contaminated", "assay_failed"}
LOW_TRUST_THRESHOLD = 0.6


def ingest_wave_results(
    campaign_state_path: Path,
    results_csv: Path,
    out_dir: Path,
    selected_design_path: Path | None = None,
) -> dict[str, Any]:
    state = load_json(campaign_state_path)
    rows, _ = read_csv(results_csv)
    quality_report = result_ingestion_report(rows)
    usable_rows = quality_report["usable_rows"]
    execution_join = validate_result_join(rows, selected_design_path, state) if selected_design_path else {
        "schema_version": 1,
        "join_check_kind": "ferm_doe_result_join",
        "status": "NOT_RUN",
        "errors": [],
        "warnings": ["No selected design path supplied; run_id join was not checked."],
    }
    arm_scope = validate_result_arm_scope(rows, state)
    response_id = state.get("objective", {}).get("response_id")
    values = [(parse_number(row.get(response_id)), row) for row in usable_rows] if response_id else []
    numeric = [(value, row) for value, row in values if value is not None]
    issues = []
    if not rows:
        action = "pause"
        issues.append("No result rows were supplied.")
    elif not usable_rows:
        action = "pause"
        issues.append("No usable result rows remain after inclusion, QC, and trust filtering.")
    elif not numeric:
        action = "pause"
        issues.append(f"No numeric response values found for {response_id}.")
    else:
        action, issues = recommend_action(state, numeric)
    issues.extend(quality_report["warnings"])
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    requested_action = str(policy.get("requested_next_action") or "").strip()
    if requested_action in ACTIONS:
        action = requested_action
    if execution_join["errors"]:
        action = "pause"
        issues.extend(execution_join["errors"])
    if arm_scope["errors"]:
        action = "pause"
        issues.extend(arm_scope["errors"])
    if action == "narrow" and campaign_arms_enabled(state) and len(_observed_arms(usable_rows)) > 1:
        action = "confirm"
        issues.append("Multi-arm results span more than one arm; use per-arm follow-up planning before narrowing any factor space.")
    bridge_report = evaluate_bridge_policy(state, usable_rows)
    if action == "scale_or_downscale" and not bridge_report.get("scale_or_downscale_allowed"):
        action = "pause"
        issues.extend(bridge_report.get("issues", []) or ["Bridge eligibility does not permit scale_or_downscale."])

    best_value, best_row = best_numeric(state, numeric) if numeric else (None, {})
    negative_memory = collect_negative_memory(state, usable_rows, response_id, best_value)
    augmentation = augmentation_recommendation(state, usable_rows, action)
    result = {
        "schema_version": 1,
        "result_ingestion_kind": "ferm_doe_wave_results",
        "campaign_id": state.get("campaign_id"),
        "result_rows": len(rows),
        "usable_result_rows": len(usable_rows),
        "response_id": response_id,
        "best_response": best_value,
        "best_run_id": best_row.get("run_id", ""),
        "recommended_action": action,
        "issues": issues,
        "result_ingestion_report": {key: value for key, value in quality_report.items() if key != "usable_rows"},
        "execution_join_report": execution_join,
        "arm_scope_report": arm_scope,
        "bridge_eligibility_report": bridge_report,
        "negative_result_memory": negative_memory,
        "augment_design_recommendation": augmentation,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "wave2_recommendation.json", result)
    write_json(out_dir / "result_ingestion_report.json", {key: value for key, value in quality_report.items() if key != "usable_rows"})
    write_json(out_dir / "execution_join_report.json", execution_join)
    write_json(out_dir / "negative_result_memory.json", {"schema_version": 1, "items": negative_memory})
    write_json(out_dir / "augment_design_recommendation.json", augmentation)
    (out_dir / "wave2_recommendation.md").write_text(render_recommendation(result))
    return result


def result_ingestion_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    usable: list[dict[str, str]] = []
    excluded: list[dict[str, Any]] = []
    low_trust: list[dict[str, Any]] = []
    qc_failed: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        run_id = str(row.get("run_id") or "<missing-run-id>")
        inclusion = str(row.get("inclusion_status") or "").strip().lower()
        qc_status = str(row.get("qc_status") or row.get("assay_qc_status") or "").strip().lower()
        trust_score = parse_number(row.get("trust_score"))
        reasons = []
        if inclusion in EXCLUDED_INCLUSION_STATUSES:
            reasons.append(f"inclusion_status={inclusion}")
            excluded.append({"run_id": run_id, "reason": reasons[-1]})
        if qc_status in FAILED_QC_STATUSES:
            reasons.append(f"qc_status={qc_status}")
            qc_failed.append({"run_id": run_id, "reason": reasons[-1]})
        if trust_score is not None and trust_score < LOW_TRUST_THRESHOLD:
            reasons.append(f"trust_score={trust_score:g}")
            low_trust.append({"run_id": run_id, "trust_score": trust_score})
        if not reasons:
            usable.append(row)
    if excluded:
        warnings.append(f"{len(excluded)} rows were excluded by inclusion_status.")
    if qc_failed:
        warnings.append(f"{len(qc_failed)} rows were excluded by QC status.")
    if low_trust:
        warnings.append(f"{len(low_trust)} low-trust rows were excluded from recommendation logic.")
    return {
        "schema_version": 1,
        "report_kind": "ferm_doe_result_ingestion_report",
        "input_row_count": len(rows),
        "usable_row_count": len(usable),
        "excluded_row_count": len(excluded),
        "qc_failed_row_count": len(qc_failed),
        "low_trust_row_count": len(low_trust),
        "excluded_rows": excluded,
        "qc_failed_rows": qc_failed,
        "low_trust_rows": low_trust,
        "warnings": warnings,
        "usable_rows": usable,
    }


def validate_result_join(rows: list[dict[str, str]], selected_design_path: Path | None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    if selected_design_path is None:
        return {
            "schema_version": 1,
            "join_check_kind": "ferm_doe_result_join",
            "status": "NOT_RUN",
            "errors": [],
            "warnings": ["No selected design path supplied; run_id join was not checked."],
        }
    selected_rows, selected_headers = read_csv(selected_design_path)
    errors: list[str] = []
    warnings: list[str] = []
    arm_aware = _arm_aware_join_required(state, selected_headers, rows)
    if "run_id" not in selected_headers:
        errors.append("selected design lacks run_id column.")
    if arm_aware and "arm_id" not in selected_headers:
        errors.append("selected design lacks arm_id column for multi-arm result join.")
    if arm_aware:
        missing_result_arm = [str(row.get("run_id") or "<missing-run-id>") for row in rows if not str(row.get("arm_id") or "").strip()]
        if missing_result_arm:
            errors.append("multi-arm result rows lack arm_id: " + ", ".join(missing_result_arm[:10]))
        selected_ids = {
            _arm_run_key(row)
            for row in selected_rows
            if str(row.get("run_id") or "").strip() and str(row.get("arm_id") or "").strip()
        }
        result_ids = {
            _arm_run_key(row)
            for row in rows
            if str(row.get("run_id") or "").strip() and str(row.get("arm_id") or "").strip()
        }
    else:
        selected_ids = {str(row.get("run_id") or "").strip() for row in selected_rows if str(row.get("run_id") or "").strip()}
        result_ids = {str(row.get("run_id") or "").strip() for row in rows if str(row.get("run_id") or "").strip()}
    if not selected_ids:
        errors.append("selected design has no planned run IDs.")
    unknown = sorted(result_ids - selected_ids)
    missing = sorted(selected_ids - result_ids)
    if unknown:
        errors.append("results contain run IDs not in selected design: " + ", ".join(_format_join_key(item) for item in unknown[:10]))
    if missing:
        warnings.append("selected design run IDs not present in result ledger yet: " + ", ".join(_format_join_key(item) for item in missing[:10]))
    return {
        "schema_version": 1,
        "join_check_kind": "ferm_doe_result_join",
        "status": "FAIL" if errors else "PASS",
        "selected_run_count": len(selected_ids),
        "result_run_count": len(result_ids),
        "joined_run_count": len(result_ids & selected_ids),
        "arm_aware": arm_aware,
        "errors": errors,
        "warnings": warnings,
    }


def validate_result_arm_scope(rows: list[dict[str, str]], state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not campaign_arms_enabled(state):
        return {"schema_version": 1, "scope_check_kind": "ferm_doe_result_arm_scope", "status": "NOT_RUN", "errors": errors, "warnings": warnings}
    factor_ids = multi_arm_factor_ids(state)
    all_arm_factors = set().union(*factor_ids.values()) if factor_ids else set()
    for row in rows:
        row_arm = str(row.get("arm_id") or "").strip()
        run_id = str(row.get("run_id") or "<missing-run-id>")
        if not row_arm:
            continue
        if row_arm not in factor_ids:
            errors.append(f"result row {run_id} uses unknown arm_id {row_arm}.")
            continue
        forbidden = sorted(all_arm_factors - factor_ids[row_arm])
        leaked = [factor_id for factor_id in forbidden if row.get(factor_id) not in {None, ""}]
        if leaked:
            errors.append(f"result row {row_arm}/{run_id} contains factors outside its arm: " + ", ".join(leaked[:10]))
    return {
        "schema_version": 1,
        "scope_check_kind": "ferm_doe_result_arm_scope",
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
    }


def recommend_action(state: dict[str, Any], numeric: list[tuple[float, dict[str, str]]]) -> tuple[str, list[str]]:
    issues: list[str] = []
    if len(numeric) < 3:
        return "expand", ["Fewer than three numeric runs; collect more information before narrowing."]
    values = [value for value, _ in numeric]
    best_value, best_row = best_numeric(state, numeric)
    median = sorted(values)[len(values) // 2]
    direction = objective_direction(state)
    if direction == "maximize" and best_value <= 0:
        return "pause", ["Best response is non-positive; check assay or process failure."]
    if direction == "minimize":
        improvement = (median - best_value) / max(abs(median), 1e-9)
    else:
        improvement = (best_value - median) / max(abs(median), 1e-9)
    if improvement < 0.05:
        return "stop", ["Best response is not materially above the median; current space appears flat."]
    if _best_at_boundary(state, best_row):
        return "expand", ["Best run is at a factor boundary; consider expanding or shifting the range."]
    if improvement > 0.3:
        return "narrow", ["Best response is materially above median and not on a boundary; narrow around winner."]
    return "confirm", ["Best response is plausible but modest; confirm before expanding."]


def best_numeric(state: dict[str, Any], numeric: list[tuple[float, dict[str, str]]]) -> tuple[float, dict[str, str]]:
    if objective_direction(state) == "minimize":
        return min(numeric, key=lambda item: item[0])
    return max(numeric, key=lambda item: item[0])


def objective_direction(state: dict[str, Any]) -> str:
    direction = str(state.get("objective", {}).get("direction") or "").strip().lower()
    if direction in {"minimize", "min"}:
        return "minimize"
    return "maximize"


def _best_at_boundary(state: dict[str, Any], row: dict[str, str]) -> bool:
    for factor in state.get("factors", []):
        value = parse_number(row.get(factor["factor_id"]))
        low = factor.get("min")
        high = factor.get("max")
        if value is None or low is None or high is None:
            continue
        span = float(high) - float(low)
        if span <= 0:
            continue
        if abs(value - float(low)) <= 0.03 * span or abs(value - float(high)) <= 0.03 * span:
            return True
    return False


def collect_negative_memory(
    state: dict[str, Any], rows: list[dict[str, str]], response_id: str | None, best_value: float | None
) -> list[dict[str, Any]]:
    if response_id is None or best_value is None:
        return []
    direction = objective_direction(state)
    cutoff = best_value * 0.5 if direction == "maximize" else best_value * 1.5
    memory = []
    for row in rows:
        value = parse_number(row.get(response_id))
        if value is None:
            continue
        if direction == "maximize" and value >= cutoff:
            continue
        if direction == "minimize" and value <= cutoff:
            continue
        memory.append(
            {
                "run_id": row.get("run_id", ""),
                "arm_id": row.get("arm_id", ""),
                "reason": "low_response_region",
                "response_id": response_id,
                "response_value": value,
                "factor_snapshot": {factor["factor_id"]: row.get(factor["factor_id"], "") for factor in state.get("factors", [])},
                "process_flags": process_flags(row),
            }
        )
    return memory


def _observed_arms(rows: list[dict[str, str]]) -> set[str]:
    return {str(row.get("arm_id") or "").strip() for row in rows if str(row.get("arm_id") or "").strip()}


def _arm_aware_join_required(state: dict[str, Any] | None, selected_headers: list[str], rows: list[dict[str, str]]) -> bool:
    if state and campaign_arms_enabled(state):
        return True
    if "arm_id" in selected_headers:
        return True
    return any(str(row.get("arm_id") or "").strip() for row in rows)


def _arm_run_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("arm_id") or "").strip(), str(row.get("run_id") or "").strip())


def _format_join_key(value: Any) -> str:
    if isinstance(value, tuple) and len(value) == 2:
        return f"{value[0]}/{value[1]}"
    return str(value)


def process_flags(row: dict[str, str]) -> list[str]:
    text = " ".join(str(value).lower() for value in row.values())
    flags = []
    for token in ["oxygen", "do", "feed", "ph", "base", "foam", "assay", "cost", "contamination", "sampling"]:
        if token in text:
            flags.append(token)
    return sorted(set(flags))


def augmentation_recommendation(state: dict[str, Any], rows: list[dict[str, str]], action: str) -> dict[str, Any]:
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    budget = policy.get("run_budget")
    if not isinstance(budget, int):
        budget = max(8, min(24, 2 * max(1, len(state.get("factors", []))) + 5))
    locked_rows = [
        row.get("run_id", "")
        for row in rows
        if str(row.get("inclusion_status", "")).lower() in {"trusted", "included", "usable", "locked", "fixed"}
    ]
    if not locked_rows:
        locked_rows = [row.get("run_id", "") for row in rows if row.get("run_id")]
    remaining = max(0, budget - len(locked_rows))
    if action == "pause":
        strategy = "repair_assay_or_process_before_augmenting"
    elif action == "expand":
        strategy = "augment_boundary_region_after_feasibility_review"
    elif action == "narrow":
        strategy = "augment_near_winner_with_center_and_confirmatory_runs"
    elif action == "confirm":
        strategy = "add_confirmatory_replicates_and_local_perturbations"
    elif action == "stop":
        strategy = "do_not_augment_until_objective_or_factor_space_changes"
    else:
        strategy = "scale_or_downscale_after_transfer_gate"
    return {
        "schema_version": 1,
        "augmentation_kind": "ferm_doe_local_augment_recommendation",
        "locked_run_ids": locked_rows,
        "remaining_run_budget": remaining,
        "strategy": strategy,
        "adapter_status": "stdlib_fallback; optional BoFire/BoTorch adapter not required",
    }


def render_recommendation(result: dict[str, Any]) -> str:
    return (
        "# follow-up Recommendation\n\n"
        f"- Campaign: {result.get('campaign_id')}\n"
        f"- Recommended action: {result.get('recommended_action')}\n"
        f"- Best run: {result.get('best_run_id')}\n"
        f"- Best response: {result.get('best_response')}\n\n"
        f"- Augmentation strategy: {result.get('augment_design_recommendation', {}).get('strategy')}\n\n"
        "## Issues\n\n"
        + "\n".join(f"- {item}" for item in result.get("issues", []))
        + "\n"
    )
