"""Artifact-lineage and claim self-checks for Ferm DoE dossiers."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .campaign_arms import campaign_arms_enabled, project_state_for_arm, selected_designs_by_arm
from .execution_plan import (
    EXECUTION_PLAN_FIELDS,
    RUN_SHEET_EXECUTION_FIELDS,
    build_execution_plan,
    execution_plan_rows_for_run_sheet,
)
from .io_utils import load_json, markdown_table, parse_number, write_json
from .model_matrix import matrix_rows_for_csv


CONTRACT_PROOF_FILES = [
    "factors.tsv",
    "constraints.tsv",
    "design-matrix.tsv",
    "randomization-seed.txt",
    "execution_plan.json",
    "run-sheet.tsv",
    "results-ledger.tsv",
    "model-report.json",
    "campaign_maturity.json",
    "claim_audit.json",
    "claim_audit.md",
    "contract_self_check.json",
    "contract_self_check.md",
]

CONTROL_ROW_HEADERS = ["run_role", "control_type", "control_source", "control_purpose"]
EXECUTED_STATUSES = {"executed", "complete", "completed", "analyzed", "included", "usable", "locked"}
HIGH_CLAIM_LEVELS = {
    "optimized",
    "validated",
    "production_ready",
    "production-ready",
    "confirmatory_validated",
    "model_supported",
    "final_process",
}
OVERCLAIM_TERMS = {
    "optimized": ["optimized", "optimal condition", "best condition"],
    "production_ready": ["production-ready", "production ready", "ready for manufacturing"],
    "validated": ["validated process", "confirmatory validation passed"],
    "final_process": ["final process"],
    "formal_assay_power": ["powered to detect", "formal power", "validated detectability", "assay detectability validated"],
}
LIVE_PLACEHOLDER_TOKENS = {
    "mock",
    "provider_search",
    "target_species_placeholder",
    "placeholder",
    "reference_only",
    "fixture",
    "dummy",
    "synthetic_only",
}


def write_contract_artifacts(
    out_dir: Path,
    state: dict[str, Any],
    selected_design: dict[str, Any] | None,
    tournament: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    """Emit standard proof artifacts and run the self-check once."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if campaign_arms_enabled(state) and isinstance(tournament.get("per_arm"), dict):
        return _write_multi_arm_contract_artifacts(out_dir, state, tournament, readiness)
    factors = state.get("factors", [])
    selected_rows = selected_design.get("rows", []) if selected_design else []
    selected_design_id = str(tournament.get("selected_design_id") or (selected_design or {}).get("design_id") or "")
    factor_headers = [str(factor.get("factor_id")) for factor in factors if factor.get("factor_id")]
    design_headers = _ordered_headers(selected_rows, ["run_id"] + CONTROL_ROW_HEADERS + factor_headers)
    execution_plan = build_execution_plan(state, selected_design, selected_design_id)
    run_sheet_rows = execution_plan_rows_for_run_sheet(selected_rows, execution_plan)
    run_sheet_headers = _ordered_headers(run_sheet_rows, RUN_SHEET_EXECUTION_FIELDS + design_headers + ["planned_status"])

    _write_tsv(out_dir / "factors.tsv", _factor_rows(factors), ["factor_id", "name", "type", "role", "unit", "min", "max", "levels", "phase", "controllable", "source"])
    _write_tsv(out_dir / "constraints.tsv", _constraint_rows(state.get("constraints", [])), ["constraint_id", "type", "description", "expression", "payload_json"])
    _write_tsv(out_dir / "design-matrix.tsv", selected_rows, design_headers)
    (out_dir / "randomization-seed.txt").write_text(_seed_text(state, selected_design_id, selected_rows, execution_plan))
    write_json(out_dir / "execution_plan.json", execution_plan)
    _write_tsv(out_dir / "run-sheet.tsv", run_sheet_rows, run_sheet_headers)
    _write_tsv(
        out_dir / "results-ledger.tsv",
        _result_ledger_template_rows(state, selected_rows, factor_headers),
        ["run_id", "execution_status", "dry_run", "included_in_model", "assay_status", state.get("objective", {}).get("response_id", "response")] + factor_headers,
    )

    model_report = _model_report(state, selected_design, selected_design_id)
    write_json(out_dir / "model-report.json", model_report)
    claim_audit = _default_claim_audit(state, selected_design_id, readiness, selected_rows, model_report)
    write_json(out_dir / "claim_audit.json", claim_audit)
    (out_dir / "claim_audit.md").write_text(render_claim_audit(claim_audit))

    result = contract_self_check(out_dir, write_outputs=True)
    return result


def _write_multi_arm_contract_artifacts(
    out_dir: Path,
    state: dict[str, Any],
    tournament: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    arm_results = []
    aggregate_selected_rows: list[dict[str, Any]] = []
    aggregate_plan_rows: list[dict[str, Any]] = []
    aggregate_run_sheet_rows: list[dict[str, Any]] = []
    response_id = str(state.get("objective", {}).get("response_id") or "response")
    for arm in state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        arm_dir = out_dir / "campaign_arms" / arm_id
        selected_rows, selected_headers = _read_table_optional(arm_dir / "selected_wave_1_design.csv", ",", [])
        arm_tournament = tournament.get("per_arm", {}).get(arm_id, {})
        selected_design_id = str(arm_tournament.get("selected_design_id") or "")
        selected_design = {
            "design_id": selected_design_id,
            "rows": selected_rows,
            "diagnostics": (arm_tournament.get("selected") or {}).get("diagnostics", {}),
        }
        arm_state = project_state_for_arm(state, arm_id)
        write_json(arm_dir / "campaign_state.json", arm_state)
        arm_check = write_contract_artifacts(arm_dir, arm_state, selected_design, arm_tournament, readiness)
        arm_results.append(
            {
                "arm_id": arm_id,
                "status": arm_check["status"],
                "selected_rows": arm_check.get("selected_rows", len(selected_rows)),
                "errors": arm_check.get("errors", []),
            }
        )
        for row in selected_rows:
            aggregate_selected_rows.append({"arm_id": arm_id, **row})
        plan = _load_json_optional(arm_dir / "execution_plan.json", [])
        for row in (plan or {}).get("rows", []):
            if isinstance(row, dict):
                aggregate_plan_rows.append({"arm_id": arm_id, **row})
        run_sheet_rows, _ = _read_table_optional(arm_dir / "run-sheet.tsv", "\t", [])
        for row in run_sheet_rows:
            aggregate_run_sheet_rows.append({"arm_id": arm_id, **row})
        (out_dir / f"execution_plan.{arm_id}.json").write_text((arm_dir / "execution_plan.json").read_text())
        (out_dir / f"run-sheet.{arm_id}.tsv").write_text((arm_dir / "run-sheet.tsv").read_text())

    write_json(
        out_dir / "per_arm_contract_self_check.json",
        {
            "schema_version": 1,
            "self_check_kind": "ferm_doe_per_arm_contract_self_check",
            "campaign_id": state.get("campaign_id"),
            "status": "FAIL" if any(item["status"] != "PASS" for item in arm_results) else "PASS",
            "arms": arm_results,
        },
    )
    factors = state.get("factors", [])
    factor_headers = [str(factor.get("factor_id")) for factor in factors if factor.get("factor_id")]
    index_headers = _ordered_headers(aggregate_selected_rows, ["arm_id", "run_id"] + CONTROL_ROW_HEADERS + factor_headers)
    _write_tsv(out_dir / "factors.tsv", _factor_rows(factors), ["factor_id", "name", "type", "role", "unit", "min", "max", "levels", "phase", "controllable", "source"])
    _write_tsv(out_dir / "constraints.tsv", _constraint_rows(state.get("constraints", [])), ["constraint_id", "type", "description", "expression", "payload_json"])
    _write_tsv(out_dir / "design-matrix.tsv", aggregate_selected_rows, index_headers)
    write_json(
        out_dir / "execution_plan.json",
        {
            "schema_version": 1,
            "plan_kind": "ferm_doe_multi_arm_execution_index",
            "campaign_id": state.get("campaign_id"),
            "rows": aggregate_plan_rows,
        },
    )
    _write_tsv(out_dir / "run-sheet.tsv", aggregate_run_sheet_rows, _ordered_headers(aggregate_run_sheet_rows, ["arm_id"] + RUN_SHEET_EXECUTION_FIELDS + index_headers + ["planned_status"]))
    _write_tsv(
        out_dir / "results-ledger.tsv",
        [
            {"arm_id": row.get("arm_id", ""), "run_id": row.get("run_id", ""), "execution_status": "planned", "dry_run": "true", "included_in_model": "false", "assay_status": "not_started", response_id: ""}
            for row in aggregate_selected_rows
        ],
        ["arm_id", "run_id", "execution_status", "dry_run", "included_in_model", "assay_status", response_id],
    )
    selected_design_id = str(tournament.get("selected_design_id") or "per_arm")
    (out_dir / "randomization-seed.txt").write_text(_seed_text(state, selected_design_id, aggregate_selected_rows, {"policy": {"mode": "per_arm_execution_index"}}))
    model_report = {
        "schema_version": 1,
        "model_report_kind": "ferm_doe_multi_arm_design_model_report",
        "selected_design_id": selected_design_id,
        "claim_scope": "pre_experiment_per_arm_design_diagnostics",
        "fitted_model": False,
        "run_count": len(aggregate_selected_rows),
        "response_id": response_id,
        "model_matrix_columns": [],
        "model_matrix_row_count": 0,
        "diagnostics": {"per_arm_contracts": arm_results},
        "caveat": "This is a per-arm design index, not a fitted cross-arm result model.",
    }
    write_json(out_dir / "model-report.json", model_report)
    claim_audit = _default_claim_audit(state, selected_design_id, readiness, aggregate_selected_rows, model_report)
    claim_audit["claim_scope"] = "pre_experiment_per_arm_planning"
    claim_audit["allowed_statement"] = "BioSymphony selected per-arm first-batch DOE candidates and compiled arm-specific execution artifacts with explicit bridge caveats."
    write_json(out_dir / "claim_audit.json", claim_audit)
    (out_dir / "claim_audit.md").write_text(render_claim_audit(claim_audit))
    result = contract_self_check(out_dir, write_outputs=True)
    result["per_arm_status"] = (out_dir / "per_arm_contract_self_check.json").exists() and "PASS"
    return result


def contract_self_check(path: Path, require_execution: bool = False, write_outputs: bool = False) -> dict[str, Any]:
    """Join dossier artifacts and reject unsupported success claims."""
    errors: list[str] = []
    warnings: list[str] = []
    join_checks: list[dict[str, Any]] = []

    state = _load_json_optional(path / "campaign_state.json", errors)
    if state and campaign_arms_enabled(state) and (path / "per_arm_contract_self_check.json").exists():
        result = _contract_self_check_multi_arm(path, state, errors, warnings, write_outputs)
        return result
    selected_rows, selected_headers = _read_table_optional(path / "selected_wave_1_design.csv", ",", errors)
    factor_rows, _ = _read_table_optional(path / "factors.tsv", "\t", errors)
    constraint_rows, _ = _read_table_optional(path / "constraints.tsv", "\t", errors)
    design_rows, _ = _read_table_optional(path / "design-matrix.tsv", "\t", errors)
    run_sheet_rows, run_sheet_headers = _read_table_optional(path / "run-sheet.tsv", "\t", errors)
    ledger_rows, ledger_headers = _read_table_optional(path / "results-ledger.tsv", "\t", errors)
    model_report = _load_json_optional(path / "model-report.json", errors)
    claim_audit = _load_json_optional(path / "claim_audit.json", errors)
    execution_plan = _load_json_optional(path / "execution_plan.json", errors)

    selected_ids = _run_ids(selected_rows)
    selected_set = set(selected_ids)
    _record_join(join_checks, "selected_design_run_ids", bool(selected_ids), len(selected_ids), "selected_wave_1_design.csv has run IDs")
    if len(selected_ids) != len(selected_set):
        errors.append("selected_wave_1_design.csv contains duplicate run_id values.")
    if selected_rows and "run_id" not in selected_headers:
        errors.append("selected_wave_1_design.csv lacks run_id.")

    _compare_id_sets("design-matrix.tsv", selected_set, set(_run_ids(design_rows)), errors, warnings, allow_empty=False)
    _compare_id_sets("run-sheet.tsv", selected_set, set(_design_run_ids(run_sheet_rows)), errors, warnings, allow_empty=False)
    _compare_id_sets("results-ledger.tsv", selected_set, set(_run_ids(ledger_rows)), errors, warnings, allow_empty=False)
    _check_execution_plan_join(execution_plan, selected_set, errors, warnings, join_checks)
    _check_run_sheet_execution_fields(run_sheet_headers, errors)

    executed_rows = [row for row in ledger_rows if _is_executed(row)]
    executed_ids = set(_run_ids(executed_rows))
    unknown_executed = sorted(executed_ids - selected_set)
    if unknown_executed:
        errors.append("results-ledger.tsv has executed rows that do not join to selected design: " + ", ".join(unknown_executed))
    if require_execution and not executed_rows:
        errors.append("execution evidence is required, but results-ledger.tsv has no executed rows.")
    _check_live_result_rows(executed_rows, errors)

    response_id = str((state or {}).get("objective", {}).get("response_id") or "")
    if executed_rows and response_id:
        missing_response = [row.get("run_id", "") for row in executed_rows if parse_number(row.get(response_id)) is None]
        if missing_response:
            errors.append("executed rows are missing numeric response values for " + response_id + ": " + ", ".join(missing_response))

    model_selected = str((model_report or {}).get("selected_design_id") or "")
    manifest_selected = _selected_design_id_from_manifest(path)
    if manifest_selected and model_selected and model_selected != manifest_selected:
        errors.append(f"model-report.json selected_design_id {model_selected} does not match dossier_manifest.json {manifest_selected}.")
    if selected_rows and model_report:
        report_count = int((model_report or {}).get("run_count") or 0)
        if report_count != len(selected_rows):
            errors.append(f"model-report.json run_count {report_count} does not match selected design rows {len(selected_rows)}.")

    _check_required_controls(state or {}, selected_rows, model_report or {}, errors, warnings)
    route_proof = _check_route_proof(
        state or {},
        factor_rows,
        constraint_rows,
        selected_rows,
        selected_headers,
        ledger_headers,
        model_report or {},
        errors,
        warnings,
    )
    _check_claims(path, state or {}, claim_audit or {}, model_report or {}, executed_rows, errors, warnings)

    maturity = _maturity_ladder(path, selected_rows, executed_rows, errors, claim_audit or {}, model_report or {})
    if write_outputs:
        write_json(path / "campaign_maturity.json", maturity)
    result = {
        "schema_version": 1,
        "self_check_kind": "ferm_doe_contract_self_check",
        "path": str(path),
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "join_checks": join_checks,
        "route_proof": route_proof,
        "maturity_ladder": maturity,
        "claim_level": (claim_audit or {}).get("claim_level", "missing"),
        "executed_rows": len(executed_rows),
        "selected_rows": len(selected_rows),
    }
    if write_outputs:
        write_json(path / "contract_self_check.json", result)
        (path / "contract_self_check.md").write_text(render_contract_self_check(result))
    return result


def _contract_self_check_multi_arm(
    path: Path,
    state: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    write_outputs: bool,
) -> dict[str, Any]:
    join_checks: list[dict[str, Any]] = []
    per_arm = _load_json_optional(path / "per_arm_contract_self_check.json", errors) or {}
    claim_audit = _load_json_optional(path / "claim_audit.json", errors) or {}
    model_report = _load_json_optional(path / "model-report.json", errors) or {}
    selected_index_rows, _ = _read_table_optional(path / "selected_wave_1_design.csv", ",", errors)
    all_selected_ids: list[str] = []
    factor_ids_by_arm = {
        str(arm.get("arm_id") or ""): {str(item) for item in arm.get("factor_ids", []) if item}
        for arm in state.get("campaign_arms", []) or []
    }
    for arm in state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        arm_dir = path / "campaign_arms" / arm_id
        selected_rows, selected_headers = _read_table_optional(arm_dir / "selected_wave_1_design.csv", ",", errors)
        plan = _load_json_optional(arm_dir / "execution_plan.json", errors)
        run_sheet_rows, run_sheet_headers = _read_table_optional(arm_dir / "run-sheet.tsv", "\t", errors)
        result_template = arm_dir / "result_capture_template.csv"
        if not result_template.exists():
            errors.append(f"campaign arm {arm_id} lacks result_capture_template.csv.")
        else:
            _, result_headers = _read_table_optional(result_template, ",", errors)
            if "arm_id" not in result_headers:
                errors.append(f"campaign arm {arm_id} result_capture_template.csv lacks arm_id.")
        selected_ids = set(_run_ids(selected_rows))
        all_selected_ids.extend(sorted(selected_ids))
        _record_join(join_checks, f"{arm_id}_selected_design_run_ids", bool(selected_ids), len(selected_ids), f"{arm_id} selected design has run IDs")
        _check_execution_plan_join(plan, selected_ids, errors, warnings, join_checks)
        _compare_id_sets(f"campaign_arms/{arm_id}/run-sheet.tsv", selected_ids, set(_design_run_ids(run_sheet_rows)), errors, warnings, allow_empty=False)
        _check_run_sheet_execution_fields(run_sheet_headers, errors)
        leaks = _cross_arm_leakage(selected_rows, arm_id, factor_ids_by_arm)
        if leaks:
            errors.append(f"campaign arm {arm_id} selected design contains factors from another arm: " + ", ".join(leaks[:10]))
        if "run_id" not in selected_headers:
            errors.append(f"campaign arm {arm_id} selected design lacks run_id.")
    if len(all_selected_ids) != len(set(all_selected_ids)):
        errors.append("per-arm selected design run IDs are not globally unique.")
    for item in per_arm.get("arms", []) if isinstance(per_arm.get("arms"), list) else []:
        if item.get("status") != "PASS":
            errors.append(f"per-arm contract failed for {item.get('arm_id')}: " + "; ".join(item.get("errors", [])[:3]))
    _check_claims(path, state, claim_audit, model_report, [], errors, warnings)
    maturity = _maturity_ladder(path, selected_index_rows, [], errors, claim_audit, model_report)
    result = {
        "schema_version": 1,
        "self_check_kind": "ferm_doe_multi_arm_contract_self_check",
        "path": str(path),
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "join_checks": join_checks,
        "route_proof": {
            "schema_version": 1,
            "proof_kind": "ferm_doe_multi_arm_route_proof",
            "passed": not errors,
            "arm_count": len(state.get("campaign_arms", []) or []),
        },
        "maturity_ladder": maturity,
        "claim_level": claim_audit.get("claim_level", "missing"),
        "executed_rows": 0,
        "selected_rows": len(selected_index_rows),
        "per_arm_status": per_arm.get("status", "missing"),
    }
    if write_outputs:
        write_json(path / "campaign_maturity.json", maturity)
        write_json(path / "contract_self_check.json", result)
        (path / "contract_self_check.md").write_text(render_contract_self_check(result))
    return result


def _cross_arm_leakage(rows: list[dict[str, str]], arm_id: str, factor_ids_by_arm: dict[str, set[str]]) -> list[str]:
    own = factor_ids_by_arm.get(arm_id, set())
    other = set().union(*(ids for key, ids in factor_ids_by_arm.items() if key != arm_id)) if factor_ids_by_arm else set()
    leaks = []
    for row in rows:
        for factor_id in sorted(other - own):
            if row.get(factor_id) not in {"", None}:
                leaks.append(factor_id)
    return sorted(set(leaks))


def render_contract_self_check(result: dict[str, Any]) -> str:
    maturity = result.get("maturity_ladder", {})
    rows = []
    for item in maturity.get("levels", []):
        rows.append([item.get("level"), item.get("name"), item.get("complete"), item.get("evidence")])
    route_rows = []
    route = result.get("route_proof") if isinstance(result.get("route_proof"), dict) else {}
    for item in route.get("checks", []):
        route_rows.append([item.get("name"), item.get("passed"), item.get("severity"), item.get("detail")])
    return (
        "# Ferm DoE Contract Self-Check\n\n"
        f"- Status: {result.get('status')}\n"
        f"- Claim level: {result.get('claim_level')}\n"
        f"- Selected rows: {result.get('selected_rows')}\n"
        f"- Executed rows: {result.get('executed_rows')}\n\n"
        "## Maturity Ladder\n\n"
        + markdown_table(["Level", "Name", "Complete", "Evidence"], rows)
        + "\n\n## Route Proof\n\n"
        + markdown_table(["Check", "Passed", "Severity", "Detail"], route_rows)
        + "\n\n## Errors\n\n"
        + ("\n".join(f"- {item}" for item in result.get("errors", [])) or "- None")
        + "\n\n## Warnings\n\n"
        + ("\n".join(f"- {item}" for item in result.get("warnings", [])) or "- None")
        + "\n"
    )


def render_claim_audit(claim_audit: dict[str, Any]) -> str:
    return (
        "# Claim Audit\n\n"
        f"- Claim level: {claim_audit.get('claim_level')}\n"
        f"- Claim scope: {claim_audit.get('claim_scope')}\n"
        f"- Evidence level: {claim_audit.get('evidence_level')}\n"
        f"- Confirmatory validation: {claim_audit.get('confirmatory_validation')}\n"
        f"- Dry-run evidence allowed: {claim_audit.get('dry_run_evidence_allowed')}\n\n"
        "## Allowed Statement\n\n"
        f"{claim_audit.get('allowed_statement', '')}\n\n"
        "## Forbidden Statements\n\n"
        + "\n".join(f"- {item}" for item in claim_audit.get("forbidden_statements", []))
        + "\n"
    )


def _factor_rows(factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for factor in factors:
        rows.append(
            {
                "factor_id": factor.get("factor_id", ""),
                "name": factor.get("name", ""),
                "type": factor.get("type", ""),
                "role": factor.get("role", ""),
                "unit": factor.get("unit", ""),
                "min": factor.get("min", ""),
                "max": factor.get("max", ""),
                "levels": "|".join(str(level) for level in factor.get("levels", [])),
                "phase": factor.get("phase", ""),
                "controllable": factor.get("controllable", ""),
                "source": factor.get("source", ""),
            }
        )
    return rows


def _constraint_rows(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, constraint in enumerate(constraints, start=1):
        rows.append(
            {
                "constraint_id": constraint.get("constraint_id") or constraint.get("id") or f"constraint_{index}",
                "type": constraint.get("type", ""),
                "description": constraint.get("description", ""),
                "expression": constraint.get("expression", ""),
                "payload_json": json.dumps(constraint, sort_keys=True),
            }
        )
    return rows


def _result_ledger_template_rows(state: dict[str, Any], selected_rows: list[dict[str, Any]], factor_headers: list[str]) -> list[dict[str, Any]]:
    response_id = str(state.get("objective", {}).get("response_id") or "response")
    rows = []
    for row in selected_rows:
        item = {
            "run_id": row.get("run_id", ""),
            "execution_status": "planned",
            "dry_run": "true",
            "included_in_model": "false",
            "assay_status": "not_started",
            response_id: "",
        }
        for factor_id in factor_headers:
            item[factor_id] = row.get(factor_id, "")
        rows.append(item)
    return rows


def _model_report(state: dict[str, Any], selected_design: dict[str, Any] | None, selected_design_id: str) -> dict[str, Any]:
    diagnostics = selected_design.get("diagnostics", {}) if selected_design else {}
    rows = selected_design.get("rows", []) if selected_design else []
    factors = state.get("factors", [])
    matrix_rows, matrix_headers = matrix_rows_for_csv(rows, factors, state.get("model_terms") or {}) if rows else ([], [])
    return {
        "schema_version": 1,
        "model_report_kind": "ferm_doe_design_model_report",
        "selected_design_id": selected_design_id,
        "claim_scope": "pre_experiment_design_diagnostics",
        "fitted_model": False,
        "run_count": len(rows),
        "response_id": state.get("objective", {}).get("response_id", ""),
        "model_matrix_columns": matrix_headers,
        "model_matrix_row_count": len(matrix_rows),
        "diagnostics": diagnostics,
        "metric_labels": diagnostics.get("metric_labels", {}),
        "caveat": "This is a design diagnostics report, not a fitted result model and not evidence of optimized conditions.",
    }


def _default_claim_audit(
    state: dict[str, Any],
    selected_design_id: str,
    readiness: dict[str, Any],
    selected_rows: list[dict[str, Any]],
    model_report: dict[str, Any],
) -> dict[str, Any]:
    dry_run_paths = _truthy_key_paths(state, {"dry_run", "dry_run_only", "mock_tools"})
    return {
        "schema_version": 1,
        "claim_audit_kind": "ferm_doe_claim_audit",
        "campaign_id": state.get("campaign_id"),
        "selected_design_id": selected_design_id,
        "claim_level": "planned_wave1_design",
        "claim_scope": "pre_experiment_planning",
        "evidence_level": "manifest_and_design_artifacts",
        "adaptive_wave2_claim_level": "pre_registered_rules_only",
        "assay_power_claim_level": "heuristic_proxy_only",
        "readiness_status": readiness.get("status"),
        "selected_rows": len(selected_rows),
        "fitted_model": bool(model_report.get("fitted_model")),
        "confirmatory_validation": False,
        "dry_run_evidence_allowed": True,
        "dry_run_flags": dry_run_paths,
        "allowed_statement": "BioSymphony selected a first-batch DOE candidate and compiled runnable planning artifacts with explicit caveats.",
        "forbidden_statements": [
            "Do not claim optimized conditions from this dossier.",
            "Do not claim process validation, production readiness, or confirmatory success without executed and joined result evidence.",
            "Do not claim formal assay power or validated detectability from heuristic assay-power proxies.",
            "Do not claim follow-up success before executed, joined, QC-passing follow-up results exist.",
            "Do not treat dry-run, mock, or planned rows as experimental evidence.",
        ],
        "claimed_terms": [],
    }


def _check_required_controls(
    state: dict[str, Any],
    selected_rows: list[dict[str, str]],
    model_report: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    review = state.get("swarm_review") if isinstance(state.get("swarm_review"), dict) else {}
    strategy = review.get("control_run_strategy") if isinstance(review.get("control_run_strategy"), dict) else {}
    controls = strategy.get("controls", []) if isinstance(strategy.get("controls"), list) else []
    if not controls:
        return
    control_rows = [row for row in selected_rows if str(row.get("run_role", "")).lower() == "control"]
    if not control_rows:
        errors.append("Scientific Swarm required control strategy, but selected design has no explicit control rows.")
    required_types = {str(item.get("control_type")) for item in controls if item.get("control_type") in {"baseline", "bridge", "center", "repeat", "phase_switch_control"}}
    present_types = {str(row.get("control_type")) for row in control_rows if row.get("control_type")}
    missing_types = sorted(required_types - present_types)
    if missing_types:
        warnings.append("selected design lacks some recommended control row types: " + ", ".join(missing_types))
    diagnostics = model_report.get("diagnostics") if isinstance(model_report.get("diagnostics"), dict) else {}
    required_centers = int(strategy.get("required_center_points") or 0)
    if required_centers and int(diagnostics.get("center_points") or 0) < required_centers:
        errors.append("selected design does not meet required center-point count from control strategy.")
    required_repeats = int(strategy.get("required_repeats") or 0)
    if required_repeats and int(diagnostics.get("replicate_count") or 0) < required_repeats:
        errors.append("selected design does not meet required repeat count from control strategy.")


def _check_claims(
    path: Path,
    state: dict[str, Any],
    claim_audit: dict[str, Any],
    model_report: dict[str, Any],
    executed_rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    claim_level = str(claim_audit.get("claim_level") or "missing").lower()
    claimed_terms = {str(term).lower() for term in claim_audit.get("claimed_terms", []) if term}
    claimed_terms.update(_scan_overclaim_terms(path))
    dry_run_paths = _truthy_key_paths(state, {"dry_run", "dry_run_only", "mock_tools"})
    high_claim = claim_level in HIGH_CLAIM_LEVELS or bool(claimed_terms)
    if claim_level == "missing":
        errors.append("claim_audit.json is missing claim_level.")
    if high_claim and not executed_rows:
        errors.append("high-level claim is present, but no executed result rows join to the dossier.")
    if high_claim and dry_run_paths:
        errors.append("high-level claim is present while dry-run/mock flags remain true: " + ", ".join(dry_run_paths[:5]))
    if claim_level in {"model_supported", "optimized", "validated", "confirmatory_validated", "production_ready", "production-ready"} and not model_report.get("fitted_model"):
        errors.append("model-supported or optimized claim requires model-report.json with fitted_model=true.")
    if claim_level in {"optimized", "validated", "confirmatory_validated", "production_ready", "production-ready"} and not claim_audit.get("confirmatory_validation"):
        errors.append("optimized/validated/production-ready claim requires confirmatory_validation=true.")
    if "formal_assay_power" in claimed_terms and str(claim_audit.get("assay_power_claim_level") or "") != "formal_power_backed":
        errors.append("formal assay-power or validated detectability claim requires assay_power_claim_level=formal_power_backed.")
    if claimed_terms:
        warnings.append("overclaim terms found and evaluated: " + ", ".join(sorted(claimed_terms)))


def _check_route_proof(
    state: dict[str, Any],
    factor_rows: list[dict[str, str]],
    constraint_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    selected_headers: list[str],
    ledger_headers: list[str],
    model_report: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str, *, severity: str = "error") -> None:
        checks.append({"name": name, "passed": passed, "severity": severity, "detail": detail})
        if not passed:
            message = f"route proof failed: {detail}"
            if severity == "warning":
                warnings.append(message)
            else:
                errors.append(message)

    state_factor_ids = [str(factor.get("factor_id") or "").strip() for factor in state.get("factors", []) if str(factor.get("factor_id") or "").strip()]
    tsv_factor_ids = [str(row.get("factor_id") or "").strip() for row in factor_rows if str(row.get("factor_id") or "").strip()]
    record("campaign_factors_loaded", bool(state_factor_ids), "campaign_state.json must contain factor ids")
    record(
        "factors_tsv_matches_campaign",
        set(state_factor_ids) == set(tsv_factor_ids) and len(tsv_factor_ids) == len(set(tsv_factor_ids)),
        "factors.tsv factor_id set must match campaign_state factors exactly",
    )

    objective = state.get("objective") if isinstance(state.get("objective"), dict) else {}
    response_id = str(objective.get("response_id") or "").strip()
    response_ids = {str(response.get("response_id") or "").strip() for response in state.get("responses", []) if str(response.get("response_id") or "").strip()}
    record("objective_response_declared", bool(response_id), "campaign objective must declare response_id")
    if response_ids:
        record("objective_response_in_responses", response_id in response_ids, f"objective response_id {response_id} must exist in responses")
    record("results_ledger_has_response", response_id in ledger_headers, f"results-ledger.tsv must contain response column {response_id}")
    model_response = str(model_report.get("response_id") or "").strip()
    record("model_report_response_matches_objective", model_response == response_id, f"model-report.json response_id {model_response} must match campaign objective response_id {response_id}")

    expected_constraint_ids = {
        str(constraint.get("constraint_id") or constraint.get("id") or f"constraint_{index}").strip()
        for index, constraint in enumerate(state.get("constraints", []), start=1)
        if isinstance(constraint, dict)
    }
    tsv_constraint_ids = {str(row.get("constraint_id") or "").strip() for row in constraint_rows if str(row.get("constraint_id") or "").strip()}
    if expected_constraint_ids:
        record("constraints_tsv_matches_campaign", expected_constraint_ids <= tsv_constraint_ids, "constraints.tsv must include every campaign constraint id")
    else:
        record("constraints_tsv_present", bool(constraint_rows) or not expected_constraint_ids, "constraints.tsv is present even when no campaign constraints are declared")

    missing_factor_columns = sorted(set(state_factor_ids) - set(selected_headers))
    record("selected_design_has_factor_columns", not missing_factor_columns, "selected_wave_1_design.csv must include campaign factor columns; missing " + ", ".join(missing_factor_columns[:10]))
    record("selected_design_has_rows", bool(selected_rows), "selected_wave_1_design.csv must contain executable or explicitly controlled planned rows")

    diagnostics = model_report.get("diagnostics") if isinstance(model_report.get("diagnostics"), dict) else {}
    violations = diagnostics.get("constraint_violations") if isinstance(diagnostics.get("constraint_violations"), list) else []
    record("selected_design_has_no_constraint_violations", not violations, "selected design diagnostics must have no constraint violations")
    return {
        "schema_version": 1,
        "proof_kind": "ferm_doe_route_proof",
        "checks": checks,
        "passed": all(item["passed"] or item["severity"] == "warning" for item in checks),
        "factor_count": len(state_factor_ids),
        "constraint_count": len(expected_constraint_ids),
        "response_id": response_id,
    }


def _check_live_result_rows(executed_rows: list[dict[str, str]], errors: list[str]) -> None:
    for row in executed_rows:
        run_id = str(row.get("run_id") or "<missing-run-id>")
        if _truthy(row.get("dry_run")):
            errors.append(f"executed row {run_id} is marked dry_run=true; live evidence cannot be dry-run evidence.")
        for field, value in row.items():
            placeholder = _placeholder_token(value)
            if placeholder:
                errors.append(f"executed row {run_id} contains placeholder/mock token {placeholder} in {field}.")


def _placeholder_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    for token in sorted(LIVE_PLACEHOLDER_TOKENS):
        if token in text:
            return token
    return ""


def _maturity_ladder(
    path: Path,
    selected_rows: list[dict[str, str]],
    executed_rows: list[dict[str, str]],
    errors: list[str],
    claim_audit: dict[str, Any],
    model_report: dict[str, Any],
) -> dict[str, Any]:
    levels = [
        ("L0", "plan_exists", (path / "campaign_state.json").exists(), "campaign_state.json"),
        ("L1", "tools_ready", (path / "design_adjudication.json").exists() and (path / "model-report.json").exists(), "design_adjudication.json + model-report.json"),
        ("L2", "inputs_materialized", bool(selected_rows) and all((path / name).exists() for name in ["factors.tsv", "constraints.tsv", "design-matrix.tsv", "run-sheet.tsv", "results-ledger.tsv"]), "standard contract proof artifacts"),
        ("L3", "execution_performed", bool(executed_rows), "executed rows in results-ledger.tsv"),
        ("L4", "evidence_joined", bool(executed_rows) and not any("do not join" in error for error in errors) and bool(model_report.get("fitted_model")), "executed rows join selected design and fitted model report"),
        ("L5", "claim_audited_dossier", bool(claim_audit) and not any("claim" in error.lower() for error in errors), "claim_audit.json + contract self-check"),
    ]
    records = [{"level": level, "name": name, "complete": complete, "evidence": evidence} for level, name, complete, evidence in levels]
    contiguous = "none"
    for item in records:
        if item["complete"]:
            contiguous = item["level"]
        else:
            break
    highest = "none"
    for item in records:
        if item["complete"]:
            highest = item["level"]
    return {
        "schema_version": 1,
        "maturity_kind": "ferm_doe_campaign_maturity",
        "current_contiguous_level": contiguous,
        "highest_completed_level": highest,
        "levels": records,
        "interpretation": "Pre-experiment dossiers normally stop at L2 with L5 claim audit; L3/L4 require executed and joined result evidence.",
    }


def _seed_text(state: dict[str, Any], selected_design_id: str, selected_rows: list[dict[str, Any]], execution_plan: dict[str, Any] | None = None) -> str:
    policy = execution_plan.get("policy", {}) if isinstance(execution_plan, dict) else {}
    raw = str(policy.get("seed_basis") or f"{state.get('campaign_id')}|{selected_design_id}|{len(selected_rows)}")
    raw_seed = policy.get("seed")
    if raw_seed not in (None, ""):
        seed = int(raw_seed)
    else:
        seed = int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)
    mode = str(policy.get("mode") or "full_randomization")
    return (
        f"randomization_seed={seed}\n"
        f"randomization_policy={mode}\n"
        f"seed_basis={raw}\n"
    )


def _ordered_headers(rows: list[dict[str, Any]], preferred: list[str]) -> list[str]:
    headers: list[str] = []
    for header in preferred:
        if header and header not in headers:
            headers.append(header)
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def _write_tsv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _read_table_optional(path: Path, delimiter: str, errors: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        errors.append(f"missing artifact for contract self-check: {path.name}")
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return rows, list(reader.fieldnames or [])


def _load_json_optional(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        errors.append(f"missing artifact for contract self-check: {path.name}")
        return None
    try:
        return load_json(path)
    except Exception as exc:
        errors.append(f"invalid JSON in {path.name}: {exc}")
        return None


def _run_ids(rows: list[dict[str, str]]) -> list[str]:
    return [str(row.get("run_id") or "").strip() for row in rows if str(row.get("run_id") or "").strip()]


def _design_run_ids(rows: list[dict[str, str]]) -> list[str]:
    ids = [str(row.get("design_run_id") or "").strip() for row in rows if str(row.get("design_run_id") or "").strip()]
    if ids:
        return ids
    return _run_ids(rows)


def _check_execution_plan_join(
    execution_plan: dict[str, Any] | None,
    selected_set: set[str],
    errors: list[str],
    warnings: list[str],
    join_checks: list[dict[str, Any]],
) -> None:
    if not execution_plan:
        return
    rows = execution_plan.get("rows") if isinstance(execution_plan.get("rows"), list) else []
    plan_ids = {
        str(row.get("design_run_id") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("design_run_id") or "").strip()
    }
    _record_join(join_checks, "execution_plan_design_run_ids", bool(plan_ids), len(plan_ids), "execution_plan.json rows join selected design run IDs")
    _compare_id_sets("execution_plan.json", selected_set, plan_ids, errors, warnings, allow_empty=False)
    if len(plan_ids) != len(rows):
        errors.append("execution_plan.json has duplicate or missing design_run_id values.")
    required = set(EXECUTION_PLAN_FIELDS)
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"execution_plan.json row {index} is not an object.")
            continue
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"execution_plan.json row {index} lacks required execution fields: " + ", ".join(missing))


def _check_run_sheet_execution_fields(headers: list[str], errors: list[str]) -> None:
    missing = [header for header in RUN_SHEET_EXECUTION_FIELDS if header not in headers]
    if missing:
        errors.append("run-sheet.tsv lacks required execution planning columns: " + ", ".join(missing))


def _compare_id_sets(name: str, selected_set: set[str], observed_set: set[str], errors: list[str], warnings: list[str], allow_empty: bool) -> None:
    if not observed_set and allow_empty:
        return
    missing = sorted(selected_set - observed_set)
    extra = sorted(observed_set - selected_set)
    if missing:
        errors.append(f"{name} is missing selected run IDs: " + ", ".join(missing[:10]))
    if extra:
        errors.append(f"{name} has run IDs not present in selected design: " + ", ".join(extra[:10]))


def _record_join(join_checks: list[dict[str, Any]], name: str, passed: bool, count: int, detail: str) -> None:
    join_checks.append({"name": name, "passed": passed, "count": count, "detail": detail})


def _is_executed(row: dict[str, str]) -> bool:
    status = str(row.get("execution_status") or row.get("status") or row.get("inclusion_status") or "").lower()
    return status in EXECUTED_STATUSES


def _selected_design_id_from_manifest(path: Path) -> str:
    manifest_path = path / "dossier_manifest.json"
    if not manifest_path.exists():
        return ""
    try:
        manifest = load_json(manifest_path)
    except Exception:
        return ""
    return str(manifest.get("selected_design_id") or "")


def _truthy_key_paths(value: Any, names: set[str], prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in names and _truthy(item):
                paths.append(path)
            paths.extend(_truthy_key_paths(item, names, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_truthy_key_paths(item, names, f"{prefix}[{index}]"))
    return paths


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "dry_run", "mock"}
    return False


def _scan_overclaim_terms(path: Path) -> set[str]:
    terms: set[str] = set()
    for name in [
        "readiness_verdict.md",
        "design_adjudication.md",
        "wave_2_decision_rules.md",
        "wave_2_decision_rules.json",
        "claim_audit.md",
        "claim_audit.json",
        "assay_power_report.md",
        "adaptive_wave2_plan.json",
        "wave2_recommendation.md",
        "wave2_recommendation.json",
    ]:
        target = path / name
        if not target.exists():
            continue
        terms.update(_scan_terms_from_text(target.read_text()))
    utility_root = path / "utility_outputs"
    if utility_root.exists():
        for target in utility_root.glob("*/**/*"):
            if target.is_file() and target.suffix.lower() in {".md", ".json"}:
                terms.update(_scan_terms_from_text(target.read_text()))
    return terms


def _scan_terms_from_text(text: str) -> set[str]:
    terms: set[str] = set()
    safe_context_tokens = {
        "do not claim",
        "forbidden",
        "claim boundary",
        "not evidence",
        "not optimized",
        "not validate",
        "not validated",
        "before fitted or optimized claims are allowed",
    }
    for raw_line in text.lower().splitlines():
        stripped = raw_line.strip().strip('", ')
        if any(token in raw_line for token in safe_context_tokens):
            continue
        if stripped in OVERCLAIM_TERMS:
            continue
        for term, needles in OVERCLAIM_TERMS.items():
            if stripped in needles:
                continue
            if any(needle in raw_line for needle in needles):
                terms.add(term)
    return terms
