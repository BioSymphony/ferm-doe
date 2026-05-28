"""Optional augment-design utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constraints import design_factors
from ..ingest import best_numeric, collect_negative_memory, recommend_action, result_ingestion_report
from ..io_utils import load_json, parse_number, read_csv, write_csv, write_json
from ..model_matrix import diagnose_design, matrix_rows_for_csv
from .common import utility_manifest
from .custom_optimal import build_candidate_set, select_optimal_rows


def run_augment_design_utility(
    campaign_state_path: Path,
    results_csv: Path,
    out_dir: Path,
    remaining_budget: int | None = None,
    criterion: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_json(campaign_state_path)
    rows, _ = read_csv(results_csv)
    quality_report = result_ingestion_report(rows)
    usable_rows = quality_report["usable_rows"]
    factors = design_factors(state.get("factors", []))
    constraints = state.get("constraints", [])
    model_spec = state.get("model_terms", {})
    response_id = state.get("objective", {}).get("response_id")
    numeric = [(parse_number(row.get(response_id)), row) for row in usable_rows] if response_id else []
    numeric = [(value, row) for value, row in numeric if value is not None]
    action, issues = recommend_action(state, numeric) if numeric else ("pause", [f"No numeric response values found for {response_id}."])
    issues.extend(quality_report["warnings"])
    best_value, best_row = best_numeric(state, numeric) if numeric else (None, {})
    negative_memory = collect_negative_memory(state, usable_rows, response_id, best_value)
    locked = locked_design_rows(usable_rows, factors)
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    budget = int(remaining_budget or policy.get("augment_remaining_budget") or max(1, min(8, len(factors) + 2)))
    selected_criterion = str(criterion or policy.get("custom_optimal_criterion") or "d").lower()

    candidate_set = build_candidate_set(factors, constraints, max(32, budget * 8))
    candidate_set = avoid_negative_memory(candidate_set, factors, negative_memory)
    candidate_set = prioritize_action_candidates(candidate_set, factors, action, best_row)
    selected, trace = select_optimal_rows(
        candidate_set=candidate_set,
        initial_rows=locked,
        factors=factors,
        constraints=constraints,
        model_spec=model_spec,
        run_budget=len(locked) + budget,
        criterion=selected_criterion,
    )
    locked_keys = {_key(row, factors) for row in locked}
    augment_rows = []
    arm_id = _single_observed_arm(usable_rows)
    for row in selected:
        if _key(row, factors) in locked_keys:
            continue
        augment = {"run_id": f"AUG-{len(augment_rows) + 1:03d}"}
        if arm_id:
            augment["arm_id"] = arm_id
        for factor in factors:
            augment[factor["factor_id"]] = row.get(factor["factor_id"], "")
        augment_rows.append(augment)
        if len(augment_rows) >= budget:
            break

    diagnostics = diagnose_design(locked + augment_rows, factors, constraints, model_spec)
    matrix_rows, matrix_headers = matrix_rows_for_csv(locked + augment_rows, factors, model_spec)
    recommendation = {
        "schema_version": 1,
        "utility_result_kind": "augment_design",
        "campaign_id": state.get("campaign_id"),
        "recommended_action": action,
        "issues": issues,
        "response_id": response_id,
        "best_run_id": best_row.get("run_id", ""),
        "best_response": best_value,
        "locked_run_ids": [row.get("run_id", "") for row in locked],
        "result_ingestion_report": {key: value for key, value in quality_report.items() if key != "usable_rows"},
        "remaining_run_budget": budget,
        "augment_run_count": len(augment_rows),
        "negative_result_memory": negative_memory,
        "diagnostics": diagnostics,
    }
    factor_headers = [factor["factor_id"] for factor in factors]
    augment_headers = ["run_id"] + (["arm_id"] if arm_id else []) + factor_headers
    locked_headers = ["run_id"] + (["arm_id"] if any(row.get("arm_id") for row in locked) else []) + factor_headers
    write_csv(out_dir / "locked_prior_runs.csv", locked, locked_headers)
    write_csv(out_dir / "augment_design.csv", augment_rows, augment_headers)
    write_csv(out_dir / "model_matrix.csv", matrix_rows, matrix_headers)
    write_json(out_dir / "augment_design_recommendation.json", recommendation)
    write_json(out_dir / "augment_trace.json", {"schema_version": 1, "criterion": selected_criterion, "items": trace})
    write_json(out_dir / "augment_design.diagnostics.json", diagnostics)
    utility_manifest(
        utility="augment-design",
        out_dir=out_dir,
        inputs={"campaign_state": str(campaign_state_path), "results": str(results_csv)},
        backend=backend or policy.get("utility_backend"),
        artifacts=["locked_prior_runs.csv", "augment_design.csv", "model_matrix.csv", "augment_design_recommendation.json", "augment_trace.json", "augment_design.diagnostics.json"],
        metric_labels=diagnostics.get("metric_labels", {}),
        caveats=["Augment rows avoid exact low-response snapshots and known explicit constraints; human review remains required."],
    )
    return recommendation


def locked_design_rows(rows: list[dict[str, str]], factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    locked = []
    for row in rows:
        status = str(row.get("inclusion_status", "")).lower()
        if status and status not in {"trusted", "included", "usable", "locked", "fixed"}:
            continue
        design_row = {"run_id": row.get("run_id", f"LOCK-{len(locked) + 1:03d}")}
        if not all(factor["factor_id"] in row for factor in factors):
            continue
        for factor in factors:
            design_row[factor["factor_id"]] = row.get(factor["factor_id"], "")
        if row.get("arm_id"):
            design_row["arm_id"] = row.get("arm_id", "")
        locked.append(design_row)
    return locked


def avoid_negative_memory(
    candidate_set: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    negative_memory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bad_keys = set()
    for item in negative_memory:
        snapshot = item.get("factor_snapshot", {})
        if isinstance(snapshot, dict):
            bad_keys.add(tuple(str(snapshot.get(factor["factor_id"], "")) for factor in factors))
    return [row for row in candidate_set if _key(row, factors) not in bad_keys]


def prioritize_action_candidates(
    candidate_set: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    action: str,
    best_row: dict[str, str],
) -> list[dict[str, Any]]:
    if action not in {"narrow", "confirm"} or not best_row:
        return candidate_set
    best_key = _key(best_row, factors)
    near = []
    far = []
    for row in candidate_set:
        distance = sum(0 if str(row.get(factor["factor_id"], "")) == best_key[index] else 1 for index, factor in enumerate(factors))
        if distance <= max(1, len(factors) // 3):
            near.append(row)
        else:
            far.append(row)
    return near + far


def _key(row: dict[str, Any], factors: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(row.get(factor["factor_id"], "")) for factor in factors)


def _single_observed_arm(rows: list[dict[str, str]]) -> str:
    arms = {str(row.get("arm_id") or "").strip() for row in rows if str(row.get("arm_id") or "").strip()}
    return next(iter(arms)) if len(arms) == 1 else ""
