"""Optional custom-optimal design utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..compiler import compile_campaign_state
from ..constraints import design_factors, validate_design_rows
from ..doe import center_row, full_factorial_design, halton_design, latin_hypercube_design
from ..io_utils import write_csv, write_json
from ..model_matrix import diagnose_design, matrix_rows_for_csv, min_scaled_distance
from .common import load_optional_rows, selected_backend_status, utility_manifest


CRITERIA = {"d", "i", "a", "g", "space_filling"}


def run_custom_optimal_utility(
    manifest_path: Path,
    out_dir: Path,
    run_budget: int | None = None,
    criterion: str | None = None,
    backend: str | None = None,
    fixed_runs_path: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = compile_campaign_state(manifest_path)
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    factors = design_factors(state.get("factors", []))
    constraints = state.get("constraints", [])
    model_spec = state.get("model_terms", {})
    budget = int(run_budget or policy.get("run_budget") or max(8, min(24, 2 * len(factors) + 5)))
    selected_criterion = str(criterion or policy.get("custom_optimal_criterion") or "d").lower()
    if selected_criterion not in CRITERIA:
        selected_criterion = "d"

    fixed_rows = _fixed_rows(load_optional_rows(fixed_runs_path), factors, policy.get("fixed_run_ids", []))
    controls = _control_rows(factors, policy.get("control_run_policy"))
    initial_rows = []
    for row in fixed_rows + controls:
        if not validate_design_rows([row], factors, constraints):
            initial_rows.append(row)

    candidate_set = build_candidate_set(factors, constraints, max(budget * 8, budget + 12))
    selected_rows, trace = select_optimal_rows(
        candidate_set=candidate_set,
        initial_rows=initial_rows,
        factors=factors,
        constraints=constraints,
        model_spec=model_spec,
        run_budget=budget,
        criterion=selected_criterion,
    )

    diagnostics = diagnose_design(selected_rows, factors, constraints, model_spec)
    matrix_rows, matrix_headers = matrix_rows_for_csv(selected_rows, factors, model_spec)
    scorecard = {
        "schema_version": 1,
        "utility_result_kind": "custom_optimal_design",
        "campaign_id": state.get("campaign_id"),
        "criterion": selected_criterion,
        "backend": selected_backend_status(backend),
        "run_budget": budget,
        "fixed_run_count": len(fixed_rows),
        "control_run_count": len(controls),
        "rows": selected_rows,
        "diagnostics": diagnostics,
    }

    factor_headers = [factor["factor_id"] for factor in factors]
    write_csv(out_dir / "candidate_set.csv", candidate_set, ["run_id"] + factor_headers)
    write_csv(out_dir / "custom_optimal_design.csv", selected_rows, ["run_id"] + factor_headers)
    write_csv(out_dir / "model_matrix.csv", matrix_rows, matrix_headers)
    write_json(out_dir / "optimality_trace.json", {"schema_version": 1, "criterion": selected_criterion, "items": trace})
    write_json(out_dir / "custom_optimal.scorecard.json", scorecard)
    write_json(out_dir / "custom_optimal.diagnostics.json", diagnostics)
    utility_manifest(
        utility="custom-optimal",
        out_dir=out_dir,
        inputs={"manifest": str(manifest_path), "fixed_runs": str(fixed_runs_path) if fixed_runs_path else ""},
        backend=backend or policy.get("utility_backend"),
        artifacts=[
            "candidate_set.csv",
            "custom_optimal_design.csv",
            "model_matrix.csv",
            "optimality_trace.json",
            "custom_optimal.scorecard.json",
            "custom_optimal.diagnostics.json",
        ],
        metric_labels=diagnostics.get("metric_labels", {}),
        caveats=["Optional adapters are lazy; stdlib selection remains deterministic when adapters are unavailable."],
    )
    return scorecard


def build_candidate_set(
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    target_size: int,
) -> list[dict[str, Any]]:
    pool = []
    pool.extend(full_factorial_design(factors, min(max(target_size, 16), 256)))
    pool.extend(latin_hypercube_design(factors, max(target_size, 8), prefix="CUS-LHS"))
    pool.extend(halton_design(factors, max(target_size, 8)))
    pool.append(center_row(factors, "CUS-CENTER"))
    deduped = _dedupe(pool, factors)
    valid = [row for row in deduped if not validate_design_rows([row], factors, constraints)]
    return valid[: max(target_size, len(valid))]


def select_optimal_rows(
    *,
    candidate_set: list[dict[str, Any]],
    initial_rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    model_spec: dict[str, Any],
    run_budget: int,
    criterion: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = _dedupe(initial_rows, factors)[:run_budget]
    selected_keys = {_key(row, factors) for row in selected}
    available = [row for row in candidate_set if _key(row, factors) not in selected_keys]
    trace: list[dict[str, Any]] = []
    while len(selected) < run_budget and available:
        best_row = None
        best_score = -1e18
        best_diag: dict[str, Any] = {}
        for row in available:
            candidate_rows = selected + [row]
            if validate_design_rows(candidate_rows, factors, constraints):
                continue
            diagnostics = diagnose_design(candidate_rows, factors, constraints, model_spec)
            score = criterion_score(candidate_rows, diagnostics, criterion, factors)
            if score > best_score:
                best_score = score
                best_row = row
                best_diag = diagnostics
        if best_row is None:
            break
        available.remove(best_row)
        renamed = {"run_id": f"OPTU-{len(selected) + 1:03d}"}
        for factor in factors:
            renamed[factor["factor_id"]] = best_row.get(factor["factor_id"], "")
        selected.append(renamed)
        trace.append(
            {
                "step": len(selected),
                "selected_run_id": renamed["run_id"],
                "criterion": criterion,
                "score": round(best_score, 6),
                "rank": best_diag.get("rank"),
                "d_efficiency": best_diag.get("d_efficiency"),
                "i_efficiency": best_diag.get("i_efficiency"),
                "a_efficiency": best_diag.get("a_efficiency"),
                "g_efficiency": best_diag.get("g_efficiency"),
            }
        )
    return selected, trace


def criterion_score(rows: list[dict[str, Any]], diagnostics: dict[str, Any], criterion: str, factors: list[dict[str, Any]]) -> float:
    if criterion == "i":
        return float(diagnostics.get("i_efficiency", 0.0))
    if criterion == "a":
        return float(diagnostics.get("a_efficiency", 0.0))
    if criterion == "g":
        return float(diagnostics.get("g_efficiency", 0.0))
    if criterion == "space_filling":
        return min_scaled_distance(rows, factors)
    rank_bonus = float(diagnostics.get("rank", 0.0)) / max(1.0, float(diagnostics.get("model_term_count", 1.0)))
    return float(diagnostics.get("d_efficiency", 0.0)) + 0.1 * rank_bonus


def _fixed_rows(rows: list[dict[str, str]], factors: list[dict[str, Any]], fixed_ids: Any) -> list[dict[str, Any]]:
    fixed_id_set = {str(item) for item in fixed_ids} if isinstance(fixed_ids, list) else set()
    output = []
    for index, row in enumerate(rows):
        run_id = str(row.get("run_id") or f"FIX-{index + 1:03d}")
        if fixed_id_set and run_id not in fixed_id_set:
            continue
        fixed = {"run_id": run_id}
        for factor in factors:
            fixed[factor["factor_id"]] = row.get(factor["factor_id"], "")
        output.append(fixed)
    return output


def _control_rows(factors: list[dict[str, Any]], policy: Any) -> list[dict[str, Any]]:
    if str(policy or "center").lower() in {"none", "false", "0"}:
        return []
    return [center_row(factors, "CTRL-CENTER")]


def _dedupe(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in rows:
        key = _key(row, factors)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _key(row: dict[str, Any], factors: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(row.get(factor["factor_id"], "")) for factor in factors)
