"""Deterministic DOE candidate generators and diagnostics.

The module owns the BioSymphony interface. Optional libraries can replace
individual generators later, but the local baseline remains dependency-free,
deterministic, and explicit about exact versus approximate metrics.
"""

from __future__ import annotations

import itertools
import importlib
import math
from pathlib import Path
from typing import Any

from .campaign_arms import active_arm_id, campaign_arms_enabled, namespace_design_set_for_arm, propose_per_arm_candidate_designs
from .compiler import compile_campaign_state
from .constraints import design_factors, validate_design_rows
from .io_utils import format_number, read_csv, resolve_path, slug, write_csv, write_json
from .model_matrix import diagnose_design, factor_values, matrix_rows_for_csv, min_scaled_distance
from .swarm import apply_factor_universe_to_factors, ensure_swarm_review, swarm_factor_universe_enabled, swarm_enabled
from .utilities.deps import dependency_status

CONTROL_ROW_HEADERS = ["run_role", "control_type", "control_source", "control_purpose"]
EXACTNESS_ORDER = {"heuristic": 0, "approximate": 1, "exact": 2, "adapter_backed": 3}


def propose_candidate_designs(
    manifest_path: Path | None = None,
    campaign_state: dict[str, Any] | None = None,
    out_dir: Path | None = None,
    run_budget: int | None = None,
) -> dict[str, Any]:
    if campaign_state is None:
        if manifest_path is None:
            raise ValueError("manifest_path or campaign_state is required")
        campaign_state = compile_campaign_state(manifest_path)
    if swarm_enabled(campaign_state):
        campaign_state = ensure_swarm_review(manifest_path, campaign_state)
    if campaign_arms_enabled(campaign_state):
        result = propose_per_arm_candidate_designs(manifest_path, campaign_state, out_dir, run_budget)
        result["campaign_arm_mode"] = "per_arm"
        result["campaign_arms"] = [
            {
                "arm_id": item.get("arm_id"),
                "candidate_count": item.get("candidate_count"),
                "run_budget": item.get("run_budget"),
                "factor_ids": item.get("factor_ids", []),
                "candidates": result.get("per_arm", {}).get(item.get("arm_id"), {}).get("candidates", []),
            }
            for item in result.get("arms", [])
        ]
        result["candidates"] = []
        return result
    raw_factors = campaign_state.get("factors", [])
    if swarm_factor_universe_enabled(campaign_state):
        review = campaign_state.get("swarm_review") if isinstance(campaign_state.get("swarm_review"), dict) else {}
        raw_factors = apply_factor_universe_to_factors(raw_factors, review.get("factor_universe"))
    factors = design_factors(raw_factors)
    if not factors:
        raise ValueError("campaign_state has no design factors")
    budget = run_budget or infer_run_budget(campaign_state)
    constraints = campaign_state.get("constraints", [])
    model_spec = campaign_state.get("model_terms") or {}
    policy = campaign_state.get("design_policy") if isinstance(campaign_state.get("design_policy"), dict) else {}
    intent = normalize_design_intent(policy.get("design_intent"))
    criterion = str(policy.get("custom_optimal_criterion") or "d").lower()
    backend_available = available_backends()
    lhs_rows, lhs_backend, lhs_exactness = adapter_latin_hypercube_design(factors, budget)
    sobol_rows, sobol_backend, sobol_exactness = adapter_sobol_design(factors, budget)
    pb_rows, pb_backend, pb_exactness, pb_backend_used = adapter_plackett_burman_design(factors, budget)
    ccd_rows, ccd_backend, ccd_exactness, ccd_backend_used = adapter_central_composite_design(factors, budget)
    bbd_rows, bbd_backend, bbd_exactness, bbd_backend_used = adapter_box_behnken_design(factors, budget)
    custom_rows, custom_trace = custom_optimal_design_with_trace(factors, budget, constraints, model_spec, criterion)
    user_rows, user_trace = user_supplied_design_rows(campaign_state, manifest_path)
    full_rows = full_factorial_design(factors, budget)
    full_complete = full_factorial_size(factors) <= budget

    candidates = [
        _candidate("classical_screening", "screening", screening_design(factors, budget), factors, constraints, model_spec, "main_effect_screening_stdlib", "screening", "approximate", "stdlib", backend_available),
        _candidate("full_factorial", "screening", full_rows, factors, constraints, model_spec, "exact_full_factorial_stdlib" if full_complete else "truncated_full_factorial_stdlib", "screening", "exact" if full_complete else "heuristic", "stdlib", backend_available),
        _candidate("fractional_factorial", "screening", fractional_factorial_design(factors, budget), factors, constraints, model_spec, "heuristic_regular_fraction_stdlib", "screening", "heuristic", "stdlib", backend_available),
        _candidate("plackett_burman", "screening", pb_rows, factors, constraints, model_spec, pb_backend, "screening", pb_exactness, pb_backend_used, backend_available),
        _candidate("definitive_screening_like", "screening", definitive_screening_design(factors, budget), factors, constraints, model_spec, "dsd_like_stdlib", "screening", "approximate", "stdlib", backend_available),
        _candidate("rsm_centered", "response_surface", rsm_design(factors, budget), factors, constraints, model_spec, "heuristic_rsm_local", "rsm", "heuristic", "stdlib", backend_available),
        _candidate("central_composite", "response_surface", ccd_rows, factors, constraints, model_spec, ccd_backend, "rsm", ccd_exactness, ccd_backend_used, backend_available),
        _candidate("box_behnken", "response_surface", bbd_rows, factors, constraints, model_spec, bbd_backend, "rsm", bbd_exactness, bbd_backend_used, backend_available),
        _candidate("space_filling", "space_filling", space_filling_design(factors, budget), factors, constraints, model_spec, "latin_hypercube_like_stdlib", "space_filling", "approximate", "stdlib", backend_available),
        _candidate("latin_hypercube", "space_filling", lhs_rows, factors, constraints, model_spec, lhs_backend, "space_filling", lhs_exactness, "scipy_qmc" if lhs_exactness == "adapter_backed" else "stdlib", backend_available),
        _candidate("halton_space_filling", "space_filling", halton_design(factors, budget), factors, constraints, model_spec, "halton_stdlib", "space_filling", "approximate", "stdlib", backend_available),
        _candidate("sobol_like_space_filling", "space_filling", sobol_rows, factors, constraints, model_spec, sobol_backend, "space_filling", sobol_exactness, "scipy_qmc" if sobol_exactness == "adapter_backed" else "stdlib", backend_available),
        _candidate("custom_optimal", "custom_optimal", custom_rows, factors, constraints, model_spec, f"criterion_{criterion}_optimal_proxy_stdlib", "custom_optimal", "approximate", "stdlib", backend_available, custom_trace),
        _candidate("low_cost_scouting", "scouting", low_cost_design(factors, budget), factors, constraints, model_spec, "heuristic_low_cost_local", "scouting", "heuristic", "stdlib", backend_available),
        _candidate("robustness_probe", "robustness", robustness_design(factors, budget), factors, constraints, model_spec, "heuristic_robustness_local", "robustness", "heuristic", "stdlib", backend_available),
    ]
    if user_rows or intent == "user_supplied_design":
        user_exactness = str(policy.get("user_supplied_exactness") or "heuristic").lower()
        if user_exactness not in EXACTNESS_ORDER:
            user_exactness = "heuristic"
        candidates.append(
            _candidate(
                "user_supplied_design",
                "user_supplied",
                user_rows,
                factors,
                constraints,
                model_spec,
                "user_supplied_csv_import" if user_rows else "user_supplied_design_missing",
                "user_supplied_design",
                user_exactness,
                "user_csv_import" if user_rows else "none",
                backend_available,
                user_trace,
            )
        )
    if any(factor.get("type") == "mixture" for factor in factors):
        candidates.append(_candidate("mixture_simplex", "mixture", mixture_simplex_design(factors, budget), factors, constraints, model_spec, "exact_simplex_lattice_local", "mixture", "exact", "stdlib", backend_available))
        candidates.append(_candidate("mixture_process", "mixture", mixture_design(factors, budget), factors, constraints, model_spec, "mixture_process_local", "mixture", "approximate", "stdlib", backend_available))
    if control_row_augmentation_enabled(campaign_state):
        candidates = [
            augment_candidate_with_control_rows(candidate, factors, constraints, model_spec, campaign_state, budget)
            for candidate in candidates
        ]
    candidates.append(skeptical_audit_candidate(campaign_state))

    result = {
        "schema_version": 1,
        "design_set_kind": "ferm_doe_candidate_designs",
        "campaign_id": campaign_state.get("campaign_id"),
        "run_budget": budget,
        "design_intent": intent,
        "candidate_count": len(candidates),
        "model_spec": model_spec,
        "candidates": candidates,
    }
    active_arm = active_arm_id(campaign_state)
    if active_arm and len(campaign_state.get("campaign_arms", []) or []) > 1:
        result = namespace_design_set_for_arm(result, active_arm)
    if out_dir is not None:
        write_design_artifacts(out_dir, result, factors, model_spec)
    return result


def write_design_artifacts(
    out_dir: Path,
    result: dict[str, Any],
    factors: list[dict[str, Any]],
    model_spec: dict[str, Any] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    factor_headers = [factor["factor_id"] for factor in factors]
    for candidate in result["candidates"]:
        rows = candidate.get("rows", [])
        if rows:
            row_headers = design_row_headers(rows, factor_headers)
            write_csv(out_dir / f"{candidate['design_id']}.csv", rows, row_headers)
            matrix_rows, matrix_headers = matrix_rows_for_csv(rows, factors, model_spec)
            write_csv(out_dir / f"{candidate['design_id']}.model_matrix.csv", matrix_rows, matrix_headers)
            for row in rows:
                all_rows.append({"design_id": candidate["design_id"], **row})
        write_json(out_dir / f"{candidate['design_id']}.scorecard.json", candidate)
        write_json(out_dir / f"{candidate['design_id']}.diagnostics.json", candidate.get("diagnostics", {}))
        diagnostics.append({"design_id": candidate["design_id"], "lane": candidate["lane"], **candidate.get("diagnostics", {})})
        if candidate["design_id"] == "custom_optimal":
            write_json(out_dir / "custom_design.scorecard.json", candidate)
    write_csv(out_dir / "candidate_set.csv", all_rows, ["design_id", "run_id"] + CONTROL_ROW_HEADERS + factor_headers)
    write_json(out_dir / "design_diagnostics.json", {"schema_version": 1, "items": diagnostics})
    write_json(out_dir / "candidate_designs.json", result)


def infer_run_budget(state: dict[str, Any]) -> int:
    if isinstance(state.get("design_policy"), dict):
        budget = state["design_policy"].get("run_budget")
        if isinstance(budget, int) and budget > 0:
            return budget
    factor_count = max(1, len(design_factors(state.get("factors", []))))
    text = " ".join(str(item) for item in [state.get("constraints", []), state.get("objective", {})]).lower()
    for token in text.replace(",", " ").replace("$", " ").split():
        if token.isdigit():
            value = int(token)
            if 4 <= value <= 200 and ("run" in text or "experiment" in text or "budget" in text):
                return value
    return max(8, min(24, 2 * factor_count + 5))


def normalize_design_intent(value: Any) -> str:
    raw = str(value or "space_filling_scout").strip().lower().replace("-", "_")
    aliases = {
        "space_filling": "space_filling_scout",
        "scout": "space_filling_scout",
        "rsm": "rsm_fit",
        "response_surface": "rsm_fit",
        "custom": "custom_constrained",
        "custom_optimal": "custom_constrained",
        "user_design": "user_supplied_design",
        "imported_design": "user_supplied_design",
    }
    raw = aliases.get(raw, raw)
    allowed = {
        "screening",
        "space_filling_scout",
        "rsm_fit",
        "mixture",
        "custom_constrained",
        "augmentation",
        "confirmatory",
        "user_supplied_design",
    }
    return raw if raw in allowed else "space_filling_scout"


def claim_level_for_exactness(exactness: str) -> str:
    return {
        "adapter_backed": "planned_adapter_backed_design",
        "exact": "planned_exact_design",
        "approximate": "planned_approximate_design",
        "heuristic": "planned_heuristic_design",
    }.get(exactness, "planned_heuristic_design")


def available_backends() -> list[str]:
    status = dependency_status()
    return sorted(name for name, item in status.get("backends", {}).items() if item.get("available"))


def full_factorial_size(factors: list[dict[str, Any]]) -> int:
    total = 1
    for factor in factors:
        total *= max(1, len(factor_level_values(factor)))
    return total


def adapter_latin_hypercube_design(factors: list[dict[str, Any]], run_budget: int) -> tuple[list[dict[str, Any]], str, str]:
    try:
        from scipy.stats import qmc  # type: ignore
    except Exception:
        return latin_hypercube_design(factors, run_budget), "latin_hypercube_like_stdlib", "approximate"
    sampler = qmc.LatinHypercube(d=len(factors), seed=0)
    sample = sampler.random(n=max(2, run_budget))
    return unit_sample_rows(factors, sample, "LHS"), "adapter_backed_scipy_qmc_latin_hypercube", "adapter_backed"


def adapter_sobol_design(factors: list[dict[str, Any]], run_budget: int) -> tuple[list[dict[str, Any]], str, str]:
    try:
        from scipy.stats import qmc  # type: ignore
    except Exception:
        return sobol_like_design(factors, run_budget), "sobol_like_stdlib", "approximate"
    sampler = qmc.Sobol(d=len(factors), scramble=False)
    sample = sampler.random(n=max(2, run_budget))
    return unit_sample_rows(factors, sample, "SOB"), "adapter_backed_scipy_qmc_sobol", "adapter_backed"


def adapter_plackett_burman_design(factors: list[dict[str, Any]], run_budget: int) -> tuple[list[dict[str, Any]], str, str, str]:
    function = import_pydoe_function("pbdesign")
    if function is None:
        return plackett_burman_design(factors, run_budget), "plackett_burman_like_stdlib", "approximate", "stdlib"
    try:
        matrix = function(len(factors))
    except Exception:
        return plackett_burman_design(factors, run_budget), "plackett_burman_like_stdlib", "approximate", "stdlib"
    rows, truncated = coded_matrix_rows(matrix, factors, "PB", run_budget)
    exactness = "adapter_backed" if not truncated else "approximate"
    status = "adapter_backed_pydoe_plackett_burman" if not truncated else "adapter_backed_pydoe_plackett_burman_truncated_nonparity"
    return rows, status, exactness, "pydoe"


def adapter_central_composite_design(factors: list[dict[str, Any]], run_budget: int) -> tuple[list[dict[str, Any]], str, str, str]:
    function = import_pydoe_function("ccdesign")
    if function is None:
        return central_composite_design(factors, run_budget), "ccd_like_stdlib", "approximate", "stdlib"
    try:
        matrix = function(len(factors), center=(1, 1))
    except Exception:
        return central_composite_design(factors, run_budget), "ccd_like_stdlib", "approximate", "stdlib"
    rows, truncated = coded_matrix_rows(matrix, factors, "CCD", run_budget)
    exactness = "adapter_backed" if not truncated else "approximate"
    status = "adapter_backed_pydoe_central_composite" if not truncated else "adapter_backed_pydoe_central_composite_truncated_nonparity"
    return rows, status, exactness, "pydoe"


def adapter_box_behnken_design(factors: list[dict[str, Any]], run_budget: int) -> tuple[list[dict[str, Any]], str, str, str]:
    function = import_pydoe_function("bbdesign")
    if function is None or len(factors) < 3:
        return box_behnken_design(factors, run_budget), "box_behnken_like_stdlib", "approximate", "stdlib"
    try:
        matrix = function(len(factors), center=1)
    except Exception:
        return box_behnken_design(factors, run_budget), "box_behnken_like_stdlib", "approximate", "stdlib"
    rows, truncated = coded_matrix_rows(matrix, factors, "BBD", run_budget)
    exactness = "adapter_backed" if not truncated else "approximate"
    status = "adapter_backed_pydoe_box_behnken" if not truncated else "adapter_backed_pydoe_box_behnken_truncated_nonparity"
    return rows, status, exactness, "pydoe"


def import_pydoe_function(name: str) -> Any | None:
    for module_name in ["pyDOE2", "pyDOE", "pydoe"]:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        function = getattr(module, name, None)
        if function is not None:
            return function
    return None


def coded_matrix_rows(matrix: Any, factors: list[dict[str, Any]], prefix: str, run_budget: int) -> tuple[list[dict[str, Any]], bool]:
    raw_rows = list(matrix)
    truncated = len(raw_rows) > run_budget
    rows = []
    for run_index, vector in enumerate(raw_rows[:run_budget], start=1):
        row = {"run_id": f"{prefix}-{run_index:03d}"}
        for dim, factor in enumerate(factors):
            value = float(vector[dim])
            row[factor["factor_id"]] = _value_from_coded(factor, value, run_index + dim)
        rows.append(row)
    return rows, truncated


def _value_from_coded(factor: dict[str, Any], value: float, index: int) -> Any:
    if value <= -0.5:
        unit = 0.0
    elif value >= 0.5:
        unit = 1.0
    else:
        unit = 0.5
    return _value_from_unit(factor, unit, index)


def unit_sample_rows(factors: list[dict[str, Any]], sample: Any, prefix: str) -> list[dict[str, Any]]:
    rows = []
    for run_index, vector in enumerate(sample):
        row = {"run_id": f"{prefix}-{run_index + 1:03d}"}
        for dim, factor in enumerate(factors):
            row[factor["factor_id"]] = _value_from_unit(factor, float(vector[dim]), run_index + dim)
        rows.append(row)
    return rows


def user_supplied_design_rows(
    state: dict[str, Any],
    manifest_path: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    path = user_supplied_design_path(state, policy, manifest_path)
    if path is None:
        return [], [{"event": "user_supplied_design_not_declared"}]
    trace: list[dict[str, Any]] = [{"event": "user_supplied_design_declared", "path": str(path)}]
    if not path.exists():
        trace.append({"event": "user_supplied_design_missing", "severity": "blocker"})
        return [], trace
    rows, headers = read_csv(path)
    normalized = normalize_user_design_rows(rows)
    trace.append(
        {
            "event": "user_supplied_design_imported",
            "rows": len(normalized),
            "headers": headers,
            "claim_boundary": "Rows were imported and validated by BioSymphony; generation provenance remains user-supplied.",
        }
    )
    return normalized, trace


def user_supplied_design_path(
    state: dict[str, Any],
    policy: dict[str, Any],
    manifest_path: Path | None,
) -> Path | None:
    raw = policy.get("user_supplied_design") or policy.get("import_design") or policy.get("design_table")
    if isinstance(raw, dict):
        raw = raw.get("path")
    if raw:
        return resolve_user_design_path(str(raw), manifest_path, state)
    for item in state.get("inputs", []):
        if not isinstance(item, dict):
            continue
        haystack = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower().replace("-", "_")
        if any(token in haystack for token in ["user_supplied_design", "imported_design", "selected_wave", "design_table", "run_matrix"]):
            raw_path = str(item.get("path") or "")
            if raw_path:
                return resolve_user_design_path(raw_path, manifest_path, state)
    return None


def resolve_user_design_path(raw_path: str, manifest_path: Path | None, state: dict[str, Any]) -> Path:
    if manifest_path is not None:
        return resolve_path(raw_path, manifest_path.parent) or Path(raw_path)
    source = str(state.get("source_manifest") or "")
    if source:
        return resolve_path(raw_path, Path(source).parent) or Path(raw_path)
    return Path(raw_path)


def normalize_user_design_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    normalized = []
    for index, row in enumerate(rows, start=1):
        item: dict[str, Any] = {}
        run_id = str(row.get("run_id") or row.get("design_run_id") or row.get("Run") or row.get("run") or "").strip()
        item["run_id"] = run_id or f"USR-{index:03d}"
        for key, value in row.items():
            if key in {"run_id", "design_run_id", "Run", "run"}:
                continue
            clean_key = str(key or "").strip()
            if clean_key:
                item[clean_key] = value
        normalized.append(item)
    return normalized


def _candidate(
    design_id: str,
    lane: str,
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]] | None,
    model_spec: dict[str, Any] | None,
    backend_status: str,
    method_family: str,
    exactness: str,
    backend_used: str,
    backend_available: list[str],
    selection_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    diagnostics = diagnose_design(rows, factors, constraints, model_spec)
    exactness = exactness if exactness in EXACTNESS_ORDER else "heuristic"
    return {
        "schema_version": 1,
        "design_id": design_id,
        "lane": lane,
        "backend": "biosymphony_stdlib",
        "backend_status": backend_status,
        "method_family": method_family,
        "exactness": exactness,
        "claim_level": claim_level_for_exactness(exactness),
        "backend_available": backend_available,
        "backend_used": backend_used,
        "selection_trace": selection_trace or [],
        "rows": rows,
        "diagnostics": diagnostics,
        "notes": design_notes(design_id, backend_status),
    }


def control_row_augmentation_enabled(state: dict[str, Any]) -> bool:
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    return swarm_enabled(state) and bool(policy.get("control_row_augmentation", True))


def augment_candidate_with_control_rows(
    candidate: dict[str, Any],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]] | None,
    model_spec: dict[str, Any] | None,
    state: dict[str, Any],
    run_budget: int,
) -> dict[str, Any]:
    rows = [dict(row) for row in candidate.get("rows", [])]
    if not rows:
        return candidate
    review = state.get("swarm_review") if isinstance(state.get("swarm_review"), dict) else {}
    controls = review.get("control_run_strategy") if isinstance(review.get("control_run_strategy"), dict) else {}
    control_rows = control_rows_for_strategy(factors, controls, state, run_budget)
    if not control_rows:
        return candidate
    exploratory_budget = max(0, run_budget - len(control_rows))
    exploratory_rows = [annotate_experimental_row(row) for row in rows[:exploratory_budget]]
    augmented_rows = control_rows + exploratory_rows
    updated = dict(candidate)
    updated["rows"] = augmented_rows
    updated["diagnostics"] = diagnose_design(augmented_rows, factors, constraints, model_spec)
    updated["diagnostics"]["control_row_count"] = len(control_rows)
    updated["diagnostics"]["control_types"] = [row["control_type"] for row in control_rows]
    updated["control_row_policy"] = {
        "source": "scientific_swarm_control_run_strategy",
        "budget": run_budget,
        "control_rows": len(control_rows),
        "exploratory_rows": len(exploratory_rows),
    }
    return updated


def control_rows_for_strategy(
    factors: list[dict[str, Any]],
    controls: dict[str, Any],
    state: dict[str, Any],
    run_budget: int,
) -> list[dict[str, Any]]:
    control_items = controls.get("controls", []) if isinstance(controls, dict) else []
    if not control_items or run_budget <= 0:
        return []
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    max_fraction = float(policy.get("control_row_max_fraction") or 0.35)
    max_controls = max(1, min(run_budget, int(math.floor(run_budget * max_fraction))))
    expanded: list[dict[str, Any]] = []
    for item in sorted(control_items, key=control_priority):
        control_type = str(item.get("control_type") or "")
        if control_type == "assay_control":
            continue
        count = max(1, int(item.get("count") or 1))
        for _ in range(count):
            expanded.append(item)
            if len(expanded) >= max_controls:
                break
        if len(expanded) >= max_controls:
            break
    rows = []
    for index, item in enumerate(expanded, start=1):
        control_type = str(item.get("control_type") or "control")
        row = center_row(factors, f"CTRL-{slug(control_type).upper()}-{index:02d}")
        row.update(
            {
                "run_role": "control",
                "control_type": control_type,
                "control_source": "scientific_swarm_control_run_strategy",
                "control_purpose": str(item.get("purpose") or item.get("placement") or ""),
            }
        )
        rows.append(row)
    return rows


def control_priority(item: dict[str, Any]) -> int:
    order = {
        "baseline": 0,
        "bridge": 1,
        "center": 2,
        "repeat": 3,
        "phase_switch_control": 4,
        "contradiction_resolution": 5,
        "evidence_fixed_control": 6,
        "assay_control": 99,
    }
    return order.get(str(item.get("control_type") or ""), 50)


def annotate_experimental_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated.setdefault("run_role", "experiment")
    updated.setdefault("control_type", "")
    updated.setdefault("control_source", "")
    updated.setdefault("control_purpose", "")
    return updated


def design_row_headers(rows: list[dict[str, Any]], factor_headers: list[str]) -> list[str]:
    has_controls = any(any(row.get(header) for header in CONTROL_ROW_HEADERS) for row in rows)
    headers = ["run_id"]
    if has_controls:
        headers.extend(CONTROL_ROW_HEADERS)
    headers.extend(factor_headers)
    return headers


def center_row(factors: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    row = {"run_id": run_id}
    for factor in factors:
        _, center, _ = factor_values(factor)
        row[factor["factor_id"]] = _format_value(center)
    return row


def factor_level_values(factor: dict[str, Any], three_level: bool = False) -> list[Any]:
    factor_type = str(factor.get("type") or "continuous").lower()
    if factor_type in {"categorical", "ordinal", "block", "hard_to_change"} and factor.get("levels"):
        return list(factor["levels"])
    low, center, high = factor_values(factor)
    if three_level:
        return [low, center, high]
    return [low, high]


def screening_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "SCR-000")]
    for index, factor in enumerate(factors):
        low, _, high = factor_values(factor)
        for level_name, value in [("L", low), ("H", high)]:
            row = center_row(factors, f"SCR-{index + 1:02d}{level_name}")
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    return rows


def full_factorial_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    levels = [factor_level_values(factor) for factor in factors]
    total = full_factorial_size(factors)
    if total > run_budget:
        combos = sampled_factorial_combinations(levels, run_budget, total)
    else:
        combos = list(itertools.product(*levels))
    rows = []
    for index, combo in enumerate(combos):
        row = {"run_id": f"FUL-{index + 1:03d}"}
        for factor, value in zip(factors, combo):
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
        rows.append(row)
    return rows


def sampled_factorial_combinations(levels: list[list[Any]], run_budget: int, total: int) -> list[tuple[Any, ...]]:
    if run_budget <= 0:
        return []
    if total <= run_budget:
        return list(itertools.product(*levels))
    indices = []
    for item in range(run_budget):
        if run_budget == 1:
            indices.append(0)
        else:
            indices.append(round(item * (total - 1) / (run_budget - 1)))
    seen: set[int] = set()
    combos = []
    for raw_index in indices:
        index = int(raw_index)
        if index in seen:
            continue
        seen.add(index)
        combos.append(factorial_combo_at_index(levels, index))
    return combos


def factorial_combo_at_index(levels: list[list[Any]], index: int) -> tuple[Any, ...]:
    values: list[Any] = []
    remainder = index
    divisors = [max(1, len(level)) for level in levels]
    for level_values, divisor in reversed(list(zip(levels, divisors))):
        position = remainder % divisor
        remainder //= divisor
        values.append(level_values[position])
    return tuple(reversed(values))


def fractional_factorial_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    if len(factors) <= 1:
        return full_factorial_design(factors, run_budget)
    base_count = max(1, len(factors) - 1)
    rows = []
    for index, combo in enumerate(itertools.product([0, 1], repeat=base_count)):
        if len(rows) >= run_budget:
            break
        row = {"run_id": f"FRF-{index + 1:03d}"}
        parity = sum(combo) % 2
        bits = list(combo) + [parity]
        for factor, bit in zip(factors, bits):
            low, _, high = factor_values(factor)
            row[factor["factor_id"]] = _format_value(high if bit else low)
        rows.append(row)
    return rows


def plackett_burman_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    run_count = max(4, min(run_budget, 4 * math.ceil((len(factors) + 1) / 4)))
    rows = []
    for run_index in range(run_count):
        row = {"run_id": f"PB-{run_index + 1:03d}"}
        for dim, factor in enumerate(factors):
            low, _, high = factor_values(factor)
            sign = 1 if ((run_index * (dim + 1) + dim) % run_count) < (run_count / 2) else -1
            row[factor["factor_id"]] = _format_value(high if sign > 0 else low)
        rows.append(row)
    return rows


def definitive_screening_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "DSD-C00")]
    for index, factor in enumerate(factors):
        low, _, high = factor_values(factor)
        for suffix, value in [("L", low), ("H", high)]:
            row = center_row(factors, f"DSD-{index + 1:02d}{suffix}")
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    return rows


def rsm_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "RSM-C00"), center_row(factors, "RSM-C01")]
    for index, factor in enumerate(factors):
        low, _, high = factor_values(factor)
        for level_name, value in [("L", low), ("H", high)]:
            row = center_row(factors, f"RSM-{index + 1:02d}{level_name}")
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    for combo_index, combo in enumerate(itertools.product([0, 1], repeat=min(4, len(factors)))):
        row = center_row(factors, f"RSM-K{combo_index:02d}")
        for factor, bit in zip(factors, combo):
            low, _, high = factor_values(factor)
            row[factor["factor_id"]] = _format_value(high if bit else low)
        rows.append(row)
        if len(rows) >= run_budget:
            return rows
    return rows


def central_composite_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "CCD-C00"), center_row(factors, "CCD-C01")]
    for index, factor in enumerate(factors):
        low, _, high = factor_values(factor)
        for suffix, value in [("A-", low), ("A+", high)]:
            row = center_row(factors, f"CCD-{index + 1:02d}{suffix}")
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    for index, row in enumerate(full_factorial_design(factors[: min(4, len(factors))], run_budget)):
        full = center_row(factors, f"CCD-F{index + 1:03d}")
        for factor in factors[: min(4, len(factors))]:
            full[factor["factor_id"]] = row[factor["factor_id"]]
        rows.append(full)
        if len(rows) >= run_budget:
            return rows
    return rows


def box_behnken_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "BBD-C00")]
    for pair_index, (left, right) in enumerate(itertools.combinations(factors, 2)):
        for low_high in itertools.product([0, 1], repeat=2):
            row = center_row(factors, f"BBD-{pair_index + 1:02d}{len(rows):03d}")
            for factor, bit in [(left, low_high[0]), (right, low_high[1])]:
                low, _, high = factor_values(factor)
                row[factor["factor_id"]] = _format_value(high if bit else low)
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    return rows


def space_filling_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    return latin_hypercube_design(factors, run_budget, prefix="SPF")


def latin_hypercube_design(factors: list[dict[str, Any]], run_budget: int, prefix: str = "LHS") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = max(2, run_budget)
    for run_index in range(n):
        row = {"run_id": f"{prefix}-{run_index + 1:03d}"}
        for dim, factor in enumerate(factors):
            low, center, high = factor_values(factor)
            if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                slot = ((run_index * (dim + 2)) + dim) % n
                value = float(low) + (float(high) - float(low)) * ((slot + 0.5) / n)
                row[factor["factor_id"]] = format_number(value)
            else:
                levels = factor.get("levels") or [low, center, high]
                row[factor["factor_id"]] = levels[(run_index + dim) % len(levels)]
        rows.append(row)
    return rows


def halton_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    bases = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
    rows = []
    for run_index in range(run_budget):
        row = {"run_id": f"HAL-{run_index + 1:03d}"}
        for dim, factor in enumerate(factors):
            row[factor["factor_id"]] = _value_from_unit(factor, radical_inverse(run_index + 1, bases[dim % len(bases)]), run_index + dim)
        rows.append(row)
    return rows


def sobol_like_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = []
    for run_index in range(run_budget):
        row = {"run_id": f"SOB-{run_index + 1:03d}"}
        for dim, factor in enumerate(factors):
            unit = ((run_index + 1) ^ ((dim + 1) * 17)) % max(2, run_budget)
            unit = (unit + 0.5) / max(2, run_budget)
            row[factor["factor_id"]] = _value_from_unit(factor, unit, run_index + dim)
        rows.append(row)
    return rows


def custom_optimal_design(
    factors: list[dict[str, Any]],
    run_budget: int,
    constraints: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows, _ = custom_optimal_design_with_trace(factors, run_budget, constraints, None, "d")
    return rows


def custom_optimal_design_with_trace(
    factors: list[dict[str, Any]],
    run_budget: int,
    constraints: list[dict[str, Any]] | None = None,
    model_spec: dict[str, Any] | None = None,
    criterion: str = "d",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_pool = []
    candidate_pool.extend(full_factorial_design(factors, min(128, max(run_budget, 2 ** min(len(factors), 7)))))
    candidate_pool.extend(latin_hypercube_design(factors, max(run_budget * 3, run_budget), prefix="COP"))
    candidate_pool = _dedupe_rows(candidate_pool, factors)
    valid_pool = [row for row in candidate_pool if not validate_design_rows([row], factors, constraints or [])]
    if not valid_pool:
        valid_pool = candidate_pool
    center = center_row(factors, "OPT-C00")
    selected: list[dict[str, Any]] = [center] if not validate_design_rows([center], factors, constraints or []) else []
    trace: list[dict[str, Any]] = []
    while len(selected) < run_budget and valid_pool:
        best = max(valid_pool, key=lambda row: custom_optimal_score(selected + [row], factors, constraints or [], model_spec or {}, criterion))
        valid_pool.remove(best)
        next_row = {"run_id": f"OPT-{len(selected) + 1:03d}"}
        for factor in factors:
            next_row[factor["factor_id"]] = best[factor["factor_id"]]
        selected.append(next_row)
        diagnostics = diagnose_design(selected, factors, constraints or [], model_spec or {})
        trace.append(
            {
                "step": len(selected),
                "criterion": criterion,
                "selected_run_id": next_row["run_id"],
                "rank": diagnostics.get("rank"),
                "model_term_count": diagnostics.get("model_term_count"),
                "d_efficiency": diagnostics.get("d_efficiency"),
                "i_efficiency": diagnostics.get("i_efficiency"),
                "a_efficiency": diagnostics.get("a_efficiency"),
                "g_efficiency": diagnostics.get("g_efficiency"),
            }
        )
    return selected[:run_budget], trace


def custom_optimal_score(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    model_spec: dict[str, Any],
    criterion: str,
) -> float:
    diagnostics = diagnose_design(rows, factors, constraints, model_spec)
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


def low_cost_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    target = max(5, min(run_budget, len(factors) + 4))
    rows = [center_row(factors, "LCS-C00")]
    for index, factor in enumerate(factors):
        low, _, _ = factor_values(factor)
        row = center_row(factors, f"LCS-{index + 1:02d}L")
        row[factor["factor_id"]] = format_number(low) if isinstance(low, float) else low
        rows.append(row)
        if len(rows) >= target:
            return rows
    while len(rows) < target:
        rows.append(center_row(factors, f"LCS-C{len(rows):02d}"))
    return rows


def robustness_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = [center_row(factors, "ROB-C00")]
    for factor in factors:
        low, center, high = factor_values(factor)
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            span = float(high) - float(low)
            values = [float(center) - 0.15 * span, float(center) + 0.15 * span]
        else:
            values = [low, high]
        for value in values:
            row = center_row(factors, f"ROB-{len(rows):03d}")
            row[factor["factor_id"]] = format_number(value) if isinstance(value, float) else value
            rows.append(row)
            if len(rows) >= run_budget:
                return rows
    return rows


def mixture_simplex_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    mixture_factors = [factor for factor in factors if factor.get("type") == "mixture"]
    if not mixture_factors:
        return []
    other_factors = [factor for factor in factors if factor.get("type") != "mixture"]
    rows = []
    for index, mixture_factor in enumerate(mixture_factors):
        row = center_row(factors, f"MSX-{index + 1:03d}")
        for factor in mixture_factors:
            row[factor["factor_id"]] = "0"
        row[mixture_factor["factor_id"]] = "1"
        for factor in other_factors:
            _, center, _ = factor_values(factor)
            row[factor["factor_id"]] = format_number(center) if isinstance(center, float) else center
        rows.append(row)
        if len(rows) >= run_budget:
            return rows
    if len(rows) < run_budget:
        row = center_row(factors, "MSX-C00")
        share = 1.0 / len(mixture_factors)
        for factor in mixture_factors:
            row[factor["factor_id"]] = f"{share:.12g}"
        rows.append(row)
    for index, (left, right) in enumerate(itertools.combinations(mixture_factors, 2)):
        if len(rows) >= run_budget:
            break
        row = center_row(factors, f"MSX-E{index + 1:03d}")
        for factor in mixture_factors:
            row[factor["factor_id"]] = "0"
        row[left["factor_id"]] = "0.5"
        row[right["factor_id"]] = "0.5"
        rows.append(row)
    return rows


def mixture_design(factors: list[dict[str, Any]], run_budget: int) -> list[dict[str, Any]]:
    rows = mixture_simplex_design(factors, run_budget)
    process_factors = [factor for factor in factors if factor.get("type") != "mixture"]
    if not rows or not process_factors:
        return rows
    expanded = []
    for row_index, row in enumerate(rows):
        expanded.append(row)
        if len(expanded) >= run_budget:
            break
        process = process_factors[row_index % len(process_factors)]
        low, _, high = factor_values(process)
        shifted = dict(row)
        shifted["run_id"] = f"MIX-P{row_index + 1:03d}"
        shifted[process["factor_id"]] = _format_value(high if row_index % 2 else low)
        expanded.append(shifted)
        if len(expanded) >= run_budget:
            break
    return expanded[:run_budget]


def skeptical_audit_candidate(state: dict[str, Any]) -> dict[str, Any]:
    warnings = []
    for item in state.get("missing_info", []):
        warnings.append(f"{item.get('field')}: {item.get('reason')}")
    return {
        "schema_version": 1,
        "design_id": "skeptical_audit",
        "lane": "skeptical_auditor",
        "backend": "biosymphony_reasoning",
        "backend_status": "non_executable_audit",
        "rows": [],
        "diagnostics": {
            "schema_version": 1,
            "diagnostics_kind": "ferm_doe_design_diagnostics",
            "run_count": 0,
            "factor_count": len(state.get("factors", [])),
            "model_term_count": 0,
            "rank": 0,
            "rank_estimate": 0,
            "statistical_quality": 0.0,
            "rejection_pressure": min(1.0, 0.1 * len(warnings)),
            "constraint_violations": [],
        },
        "notes": warnings or ["No major pre-design caveats detected by campaign compiler."],
    }


def radical_inverse(index: int, base: int) -> float:
    inverse = 0.0
    fraction = 1.0 / base
    while index > 0:
        inverse += fraction * (index % base)
        index //= base
        fraction /= base
    return inverse


def _value_from_unit(factor: dict[str, Any], unit: float, index: int) -> Any:
    low, center, high = factor_values(factor)
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return format_number(float(low) + (float(high) - float(low)) * max(0.0, min(1.0, unit)))
    levels = factor.get("levels") or [low, center, high]
    return levels[index % len(levels)]


def _dedupe_rows(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for row in rows:
        key = tuple(str(row.get(factor["factor_id"], "")) for factor in factors)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _format_value(value: Any) -> Any:
    return format_number(value) if isinstance(value, (int, float)) else value


def design_notes(design_id: str, backend_status: str | None = None) -> list[str]:
    notes = {
        "classical_screening": "Main-effect screening candidate with center anchor.",
        "full_factorial": "Full low/high factorial when budget allows; truncated deterministically when budgeted.",
        "fractional_factorial": "Regular-fraction-like low/high screening candidate.",
        "plackett_burman": "Plackett-Burman-like screening candidate from deterministic stdlib construction.",
        "definitive_screening_like": "Definitive-screening-like low/center/high candidate.",
        "rsm_centered": "Response-surface candidate with center points and axial/corner coverage.",
        "central_composite": "Central-composite-like response-surface candidate.",
        "box_behnken": "Box-Behnken-like pairwise edge candidate with center anchors.",
        "space_filling": "Latin-hypercube-like scouting candidate for weak prior models.",
        "latin_hypercube": "Deterministic Latin-hypercube-like design.",
        "halton_space_filling": "Halton sequence space-filling design.",
        "sobol_like_space_filling": "Sobol-like deterministic low-discrepancy design; labeled approximate.",
        "custom_optimal": "Greedy custom optimal design candidate over a validated candidate set.",
        "low_cost_scouting": "Reduced run-count candidate for cheap first-pass learning.",
        "robustness_probe": "Near-center perturbation candidate for robustness checks.",
        "mixture_simplex": "Simplex mixture candidate enforcing mixture sum logic.",
        "mixture_process": "Mixture-process candidate combining recipe and process factors.",
        "user_supplied_design": "Imported user-supplied run table; BioSymphony validates and labels the claim but does not claim generation provenance.",
    }
    suffix = f" Backend status: {backend_status}." if backend_status else ""
    return [notes.get(design_id, "Generated candidate design.") + suffix]
