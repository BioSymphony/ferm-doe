"""Readiness scoring gates for Ferm DoE campaigns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assay_power import evaluate_assay_power
from .compiler import compile_campaign_state
from .io_utils import parse_number, read_csv, resolve_path, write_json
from .workflow_modes import evaluate_workflow_modes, response_has_lab_assay_method, response_requires_assay, response_semantics_warnings


def _find_input(state: dict[str, Any], tokens: list[str]) -> dict[str, Any] | None:
    for item in state.get("inputs", []):
        haystack = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower()
        if any(token in haystack for token in tokens):
            return item
    return None


def _load_ledger(state: dict[str, Any], base: Path) -> list[dict[str, str]]:
    item = _find_input(state, ["ledger", "run"])
    path = resolve_path(str(item.get("path")) if item else None, base)
    if path and path.exists():
        rows, _ = read_csv(path)
        return rows
    return []


def score_campaign_readiness(
    manifest_path: Path | None = None,
    campaign_state: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    if campaign_state is None:
        if manifest_path is None:
            raise ValueError("manifest_path or campaign_state is required")
        campaign_state = compile_campaign_state(manifest_path)
    base = manifest_path.parent if manifest_path else Path.cwd()
    ledger_rows = _load_ledger(campaign_state, base)
    workflow_checks = evaluate_workflow_modes(campaign_state)

    gates = [
        _contract_gate(campaign_state),
        _data_trust_gate(ledger_rows),
        _factor_gate(campaign_state),
        _response_gate(campaign_state),
        _assay_gate(campaign_state),
        _assay_power_gate(campaign_state),
        _feasibility_gate(campaign_state),
        _cost_time_gate(campaign_state),
        _mode_transfer_gate(campaign_state),
    ]
    blockers = [issue for gate in gates for issue in gate["issues"] if issue["severity"] == "blocker"]
    warnings = [issue for gate in gates for issue in gate["issues"] if issue["severity"] == "warning"]
    score = round(sum(gate["score"] for gate in gates) / len(gates), 3)
    if blockers:
        status = "RED"
    elif score >= 0.82 and not warnings:
        status = "GREEN"
    else:
        status = "YELLOW"
    result = {
        "schema_version": 1,
        "scorecard_kind": "campaign_readiness",
        "campaign_id": campaign_state.get("campaign_id"),
        "status": status,
        "score": score,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "gates": gates,
        "blockers": blockers,
        "warnings": warnings,
        "workflow_mode_checks": workflow_checks,
        "recommended_action": _recommended_action(status, blockers, warnings),
    }
    if out_path is not None:
        write_json(out_path, result)
    return result


def _issue(field: str, severity: str, message: str) -> dict[str, str]:
    return {"field": field, "severity": severity, "message": message}


def _gate(name: str, score: float, issues: list[dict[str, str]]) -> dict[str, Any]:
    return {"gate": name, "score": round(score, 3), "issues": issues}


def _contract_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not state.get("objective", {}).get("primary"):
        issues.append(_issue("objective.primary", "blocker", "Primary objective is required."))
    if not state.get("responses"):
        issues.append(_issue("responses", "blocker", "At least one response is required."))
    if not state.get("factors"):
        issues.append(_issue("factors", "blocker", "At least one factor is required."))
    return _gate("contract", 1.0 - min(1.0, len(issues) * 0.35), issues)


def _data_trust_gate(rows: list[dict[str, str]]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not rows:
        return _gate("data_trust", 0.35, [_issue("historical_run_ledger", "warning", "No run ledger was available.")])
    trust_values = [parse_number(row.get("trust_score")) for row in rows]
    trust_numbers = [value for value in trust_values if value is not None]
    if len(trust_numbers) != len(rows):
        issues.append(_issue("trust_score", "warning", "Some ledger rows lack trust scores."))
    low = [value for value in trust_numbers if value < 0.6]
    if low:
        issues.append(_issue("trust_score", "warning", "Some ledger rows have low trust scores."))
    average = sum(trust_numbers) / len(trust_numbers) if trust_numbers else 0.0
    score = min(1.0, max(0.2, average))
    return _gate("data_trust", score, issues)


def _factor_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    factors = state.get("factors", [])
    for factor in factors:
        factor_type = str(factor.get("type") or "continuous").lower()
        if factor_type in {"continuous", "discrete", "mixture"} and (factor.get("min") is None or factor.get("max") is None):
            issues.append(_issue(f"factor:{factor.get('factor_id')}", "warning", "Numeric factor lacks bounds."))
        if factor_type in {"categorical", "ordinal", "block", "hard_to_change"} and not factor.get("levels"):
            issues.append(_issue(f"factor:{factor.get('factor_id')}", "warning", "Categorical/block factor lacks levels."))
        if factor_type == "mixture" and not factor.get("mixture_group"):
            issues.append(_issue(f"factor:{factor.get('factor_id')}", "warning", "Mixture factor lacks an explicit mixture group."))
        if factor.get("phase") == "unspecified":
            issues.append(_issue(f"factor:{factor.get('factor_id')}:phase", "warning", "Factor phase is unspecified."))
        if not factor.get("controllable", True):
            issues.append(_issue(f"factor:{factor.get('factor_id')}", "warning", "Factor is marked not controllable."))
    score = 1.0 - min(0.7, len(issues) * 0.12)
    return _gate("factor_feasibility", score, issues)


def _response_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    objective_response = state.get("objective", {}).get("response_id")
    response_ids = {response.get("response_id") for response in state.get("responses", [])}
    if objective_response and objective_response not in response_ids:
        issues.append(_issue("objective.response_id", "blocker", "Objective response is not listed in responses."))
    for response in state.get("responses", []):
        if response_requires_assay(response) and response.get("sample_fraction") == "unknown":
            issues.append(_issue(f"response:{response.get('response_id')}", "warning", "Sample fraction is unknown."))
        if response.get("class") == "unknown":
            issues.append(_issue(f"response:{response.get('response_id')}", "warning", "Response class is unknown."))
    for warning in response_semantics_warnings(state):
        issues.append(_issue(warning["field"], "warning", warning["message"]))
    return _gate("response_semantics", 1.0 - min(0.75, len(issues) * 0.1), issues)


def _assay_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for response in state.get("responses", []):
        if not response_requires_assay(response):
            if response_has_lab_assay_method(response):
                issues.append(_issue(f"assay:{response.get('response_id')}", "warning", "Non-assay response is assigned a lab assay method."))
            continue
        if response.get("assay_method") == "unknown":
            issues.append(_issue(f"assay:{response.get('response_id')}", "warning", "Assay method is not specified."))
        calibration = response.get("calibration") or response.get("standard_curve")
        if calibration in (None, "", "unknown") and response.get("assay_method") != "unknown":
            issues.append(_issue(f"assay:{response.get('response_id')}:calibration", "warning", "Assay calibration or standard curve is not specified."))
        if response.get("matrix_effects_policy") in (None, "", "unknown") and response.get("assay_method") != "unknown":
            issues.append(_issue(f"assay:{response.get('response_id')}:matrix_effects", "warning", "Assay matrix-effects policy is not specified."))
    if "assay-product-class-planner" in state.get("workflow_modes", {}).get("selected", []) and issues:
        issues.append(_issue("assay_contract", "warning", "Assay product-class mode selected but assay contract is incomplete."))
    return _gate("assay_readiness", 1.0 - min(0.8, len(issues) * 0.16), issues)


def _assay_power_gate(state: dict[str, Any]) -> dict[str, Any]:
    assessment = evaluate_assay_power(state)
    issues: list[dict[str, str]] = []
    for item in assessment.get("items", []):
        response_id = str(item.get("response_id") or "")
        for issue in item.get("issues", []):
            if not isinstance(issue, dict):
                continue
            severity = "blocker" if item.get("status") == "FAIL" and issue.get("severity") == "blocker" else "warning"
            issues.append(
                _issue(
                    f"assay_power:{response_id}:{issue.get('field', 'policy')}",
                    severity,
                    str(issue.get("message") or "Assay-power policy issue."),
                )
            )
    return _gate("assay_power", float(assessment.get("score", 0.0)), issues)


def _feasibility_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    input_text = " ".join(str(item) for item in state.get("inputs", [])).lower()
    if "equipment" not in input_text and "capacity" not in input_text:
        issues.append(_issue("equipment_capacity", "warning", "Equipment capacity is not provided."))
    if "reagent" not in input_text:
        issues.append(_issue("reagent_inventory", "warning", "Reagent inventory is not provided."))
    return _gate("equipment_reagent_feasibility", 1.0 - min(0.7, len(issues) * 0.18), issues)


def _cost_time_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    selected = state.get("workflow_modes", {}).get("selected", [])
    manifest_fields = set(state.get("manifest_fields", []))
    if "cost-productivity-minimizer" in selected:
        text = " ".join([str(state.get("constraints", "")), str(state.get("objective", ""))]).lower()
        if "cost" not in text and "$" not in text and "cost_limit" not in manifest_fields:
            issues.append(_issue("cost_model", "warning", "Cost/productivity mode selected without a cost model."))
        if "time" not in text and "duration" not in text and "hour" not in text and "run_duration_limit" not in manifest_fields:
            issues.append(_issue("run_duration", "warning", "Cost/productivity mode selected without duration policy."))
        if "sampling_burden_policy" not in manifest_fields:
            issues.append(_issue("sampling_burden_policy", "warning", "Sampling burden is not bounded or priced."))
    return _gate("cost_time", 1.0 - min(0.7, len(issues) * 0.2), issues)


def _mode_transfer_gate(state: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    existing_fields = set(state) | set(state.get("manifest_fields", []))
    for mode, required_fields in state.get("mode_requirements", {}).items():
        for field in required_fields:
            if field not in existing_fields and field not in {"objective", "responses", "factors"}:
                issues.append(_issue(f"mode:{mode}:{field}", "warning", f"Mode requirement is not yet captured: {field}."))
    checks = evaluate_workflow_modes(state)
    for check in checks.get("checks", []):
        if check.get("status") != "PASS":
            issues.append(_issue(f"mode:{check['mode']}:{check['check']}", "warning", check.get("risk") or "Workflow-mode check did not pass."))
    return _gate("mode_transfer", 1.0 - min(0.85, len(issues) * 0.08), issues)


def _recommended_action(status: str, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
    if status == "RED":
        return "fix_blockers_before_design"
    if warnings:
        return "run_design_tournament_with_caveats"
    return "ready_for_wave1_packet"
