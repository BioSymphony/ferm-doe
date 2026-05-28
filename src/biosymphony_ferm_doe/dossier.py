"""Compile and validate runnable Ferm DoE dossiers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .assay_power import evaluate_assay_power
from .campaign_arms import (
    campaign_arms_enabled,
    evaluate_bridge_policy,
    project_state_for_arm,
    propose_per_arm_candidate_designs,
    selected_design_index_rows,
    selected_designs_by_arm,
    write_campaign_arm_artifacts,
)
from .compiler import compile_campaign_state
from .contract import CONTRACT_PROOF_FILES, contract_self_check, write_contract_artifacts
from .doe import CONTROL_ROW_HEADERS, propose_candidate_designs
from .io_utils import markdown_table, read_csv, resolve_path, write_csv, write_json
from .parity import write_parity_artifacts
from .readiness import score_campaign_readiness
from .swarm import SWARM_DOSSIER_FILES, ensure_swarm_review, swarm_enabled, write_swarm_artifacts
from .tournament import design_comparison, run_design_tournament, run_per_arm_design_tournament
from .workflow_modes import evaluate_workflow_modes


REQUIRED_DOSSIER_FILES = [
    "campaign_state.json",
    "missing_info.json",
    "readiness_scorecard.json",
    "data_trust_report.md",
    "factor_space_audit.md",
    "assay_readiness_report.md",
    "feasibility_report.md",
    "design_adjudication.json",
    "design_adjudication.md",
    "design_comparison.json",
    "design_comparison.md",
    "design_diagnostics.json",
    "experimental_setup.json",
    "experimental_setup.md",
    "selected_wave_1_design.csv",
    "horizontal_doe.csv",
    "horizontal_doe.json",
    "doe_reference_export.csv",
    "doe_parity_matrix.json",
    "doe_parity_report.md",
    "assumptions_and_nonparity.md",
    "workflow_mode_checks.json",
    "run_sheet.md",
    "sampling_schedule.md",
    "result_capture_template.csv",
    "wave_2_decision_rules.json",
    "wave_2_decision_rules.md",
    "provenance.md",
    "readiness_verdict.md",
    "dossier_manifest.json",
]
REQUIRED_DOSSIER_FILES.extend(CONTRACT_PROOF_FILES)


def compile_dossier(manifest_path: Path, out_dir: Path, run_budget: int | None = None, enable_swarm: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = compile_campaign_state(manifest_path, out_dir, enable_swarm=enable_swarm)
    swarm_outputs: list[dict[str, Any]] = []
    required_files = list(REQUIRED_DOSSIER_FILES)
    if swarm_enabled(state):
        state = ensure_swarm_review(manifest_path, state)
        write_json(out_dir / "campaign_state.json", state)
        write_swarm_artifacts(out_dir, state)
        swarm_outputs.append(
            {
                "schema_version": 1,
                "swarm_plan_kind": "scientific_swarm_plan",
                "campaign_id": state["campaign_id"],
                "artifact_count": len(SWARM_DOSSIER_FILES),
                "artifacts": SWARM_DOSSIER_FILES,
                "evidence_rows": state["swarm_review"]["evidence_ingestion"]["usable_row_count"],
            }
        )
        required_files.extend(SWARM_DOSSIER_FILES)
    readiness = score_campaign_readiness(manifest_path, state, out_dir / "readiness_scorecard.json")
    multi_arm = campaign_arms_enabled(state)
    if multi_arm:
        designs = propose_per_arm_candidate_designs(manifest_path, state, out_dir / "design_candidates", run_budget)
        tournament = run_per_arm_design_tournament(manifest_path, state, out_dir, run_budget, designs=designs)
        selected_by_arm = selected_designs_by_arm(designs, tournament)
        comparison = design_comparison(tournament)
        _write_per_arm_design_artifacts(out_dir, state, designs, tournament, selected_by_arm)
        selected_design = None
        selected_headers = ["run_id", "arm_id", "design_run_id", "source_run_id", "selected_design_id", "source_design_id", "executable_artifact", "planned_status"]
        write_csv(out_dir / "selected_wave_1_design.csv", selected_design_index_rows(selected_by_arm), selected_headers)
        write_json(
            out_dir / "design_diagnostics.json",
            {
                "schema_version": 1,
                "items": [
                    {"arm_id": arm_id, "design_id": c["design_id"], **c.get("diagnostics", {})}
                    for arm_id, arm_designs in designs.get("per_arm", {}).items()
                    for c in arm_designs.get("candidates", [])
                ],
            },
        )
        bridge_report = evaluate_bridge_policy(state)
        write_json(out_dir / "arm_bridge_eligibility.json", bridge_report)
        write_campaign_arm_artifacts(out_dir, state, bridge_report)
    else:
        designs = propose_candidate_designs(manifest_path, state, out_dir / "design_candidates", run_budget)
        tournament = run_design_tournament(manifest_path, state, out_dir, run_budget)
        comparison = design_comparison(tournament)
        selected_design = _find_design(designs, tournament["selected_design_id"])
        selected_headers = ["run_id"] + CONTROL_ROW_HEADERS + [factor["factor_id"] for factor in state["factors"]]
        if selected_design and selected_design.get("rows"):
            write_csv(
                out_dir / "selected_wave_1_design.csv",
                selected_design["rows"],
                selected_headers,
            )
        else:
            write_csv(out_dir / "selected_wave_1_design.csv", [], selected_headers)
        write_json(out_dir / "design_diagnostics.json", {"schema_version": 1, "items": [{"design_id": c["design_id"], **c.get("diagnostics", {})} for c in designs["candidates"]]})
    write_json(out_dir / "design_comparison.json", comparison)
    workflow_checks = evaluate_workflow_modes(state)
    write_json(out_dir / "workflow_mode_checks.json", workflow_checks)

    _write_experimental_setup(out_dir, state, selected_design, tournament)
    _write_horizontal_doe(out_dir, state, selected_design, tournament)
    _write_doe_export(out_dir / "doe_reference_export.csv", state, selected_design)

    _write_data_trust(out_dir / "data_trust_report.md", state, manifest_path)
    _write_factor_audit(out_dir / "factor_space_audit.md", state)
    _write_assay_report(out_dir / "assay_readiness_report.md", state, readiness)
    _write_feasibility_report(out_dir / "feasibility_report.md", state, readiness)
    _write_adjudication_md(out_dir / "design_adjudication.md", tournament)
    _write_design_comparison_md(out_dir / "design_comparison.md", comparison)
    _write_run_sheet(out_dir / "run_sheet.md", state, selected_design)
    _write_sampling_schedule(out_dir / "sampling_schedule.md", state)
    _write_result_template(out_dir / "result_capture_template.csv", state)
    _write_wave2_rules(out_dir / "wave_2_decision_rules.md", state, tournament)
    _write_provenance(out_dir / "provenance.md", state, manifest_path)
    _write_verdict(out_dir / "readiness_verdict.md", readiness, tournament)
    selected_diagnostics = selected_design.get("diagnostics", {}) if selected_design else {}
    utility_outputs = _compile_required_utilities(manifest_path, out_dir, state, run_budget)
    write_parity_artifacts(out_dir, state, tournament, selected_diagnostics)
    contract_check = write_contract_artifacts(out_dir, state, selected_design, tournament, readiness)

    manifest = {
        "schema_version": 1,
        "dossier_kind": "ferm_doe_dossier",
        "campaign_id": state["campaign_id"],
        "readiness_status": readiness["status"],
        "selected_design_id": tournament["selected_design_id"],
        "utility_outputs": utility_outputs,
        "swarm_outputs": swarm_outputs,
        "contract_self_check_status": contract_check["status"],
        "required_files": required_files,
        "files": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    if multi_arm:
        manifest["campaign_arm_mode"] = "per_arm"
        manifest["campaign_arms"] = state.get("campaign_arms", [])
        manifest["per_arm_contract_status"] = contract_check.get("per_arm_status")
    write_json(out_dir / "dossier_manifest.json", manifest)
    return manifest


def check_dossier(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required_files = list(REQUIRED_DOSSIER_FILES)
    campaign_state_path = path / "campaign_state.json"
    if campaign_state_path.exists():
        try:
            import json

            state = json.loads(campaign_state_path.read_text())
            if swarm_enabled(state):
                required_files.extend(SWARM_DOSSIER_FILES)
        except Exception:
            pass
    for name in required_files:
        target = path / name
        if not target.exists():
            errors.append(f"missing required file: {name}")
        elif target.stat().st_size == 0:
            errors.append(f"empty required file: {name}")
    for json_name in [
        "campaign_state.json",
        "readiness_scorecard.json",
        "design_adjudication.json",
        "design_comparison.json",
        "design_diagnostics.json",
        "doe_parity_matrix.json",
        "workflow_mode_checks.json",
        "experimental_setup.json",
        "horizontal_doe.json",
        "wave_2_decision_rules.json",
        "execution_plan.json",
        "model-report.json",
        "campaign_maturity.json",
        "claim_audit.json",
        "contract_self_check.json",
        "dossier_manifest.json",
        "evidence_swarm_plan.json",
        "evidence_ingestion_report.json",
        "factor_universe.json",
        "assumption_attack_report.json",
        "observability_plan.json",
        "control_run_strategy.json",
        "symphony_agent_graph.json",
    ]:
        target = path / json_name
        if target.exists():
            try:
                import json

                json.loads(target.read_text())
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"invalid JSON in {json_name}: {exc}")
    selected = path / "selected_wave_1_design.csv"
    if selected.exists():
        rows, headers = read_csv(selected)
        if "run_id" not in headers:
            errors.append("selected_wave_1_design.csv lacks run_id")
        if not rows:
            warnings.append("selected_wave_1_design.csv has no executable rows")
    campaign_state_path = path / "campaign_state.json"
    if campaign_state_path.exists():
        try:
            import json

            state = json.loads(campaign_state_path.read_text())
            policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
            required_utilities = policy.get("required_utilities") if isinstance(policy.get("required_utilities"), list) else []
            for utility in required_utilities:
                utility_dir = path / "utility_outputs" / str(utility)
                if not (utility_dir / "utility_manifest.json").exists():
                    errors.append(f"missing required utility output: {utility}")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"could not inspect campaign_state.json for utility requirements: {exc}")
    contract = contract_self_check(path)
    errors.extend(f"contract self-check: {item}" for item in contract["errors"])
    warnings.extend(f"contract self-check: {item}" for item in contract["warnings"])
    return {
        "schema_version": 1,
        "dossier_check_kind": "ferm_doe_dossier_check",
        "path": str(path),
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
    }


def _find_design(designs: dict[str, Any], design_id: str) -> dict[str, Any] | None:
    for candidate in designs.get("candidates", []):
        if candidate.get("design_id") == design_id:
            return candidate
    return None


def _write_per_arm_design_artifacts(
    out_dir: Path,
    state: dict[str, Any],
    designs: dict[str, Any],
    tournament: dict[str, Any],
    selected_by_arm: dict[str, dict[str, Any]],
) -> None:
    factor_ids_by_arm = {
        str(arm.get("arm_id")): set(str(item) for item in arm.get("factor_ids", []) if item)
        for arm in state.get("campaign_arms", [])
    }
    summary_arms: list[dict[str, Any]] = []
    variance_items: list[dict[str, Any]] = []
    for arm in state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        arm_dir = out_dir / "campaign_arms" / arm_id
        arm_dir.mkdir(parents=True, exist_ok=True)
        arm_designs = designs.get("per_arm", {}).get(arm_id, {})
        arm_tournament = tournament.get("per_arm", {}).get(arm_id, {})
        selected = selected_by_arm.get(arm_id, {})
        selected_rows = selected.get("rows", [])
        projected = project_state_for_arm(state, arm_id)
        factor_headers = [factor["factor_id"] for factor in projected.get("factors", []) if factor.get("factor_id")]
        selected_headers = ["run_id"] + CONTROL_ROW_HEADERS + factor_headers
        write_json(arm_dir / "candidate_designs.json", arm_designs)
        write_json(arm_dir / "design_adjudication.json", arm_tournament)
        write_json(arm_dir / "design_comparison.json", design_comparison(arm_tournament))
        write_csv(arm_dir / "selected_wave_1_design.csv", selected_rows, selected_headers)
        _write_sampling_schedule(arm_dir / "sampling_schedule.md", projected)
        _write_result_template(arm_dir / "result_capture_template.csv", projected)
        write_csv(out_dir / f"selected_wave_1_design.{arm_id}.csv", selected_rows, selected_headers)
        leak_columns = _cross_arm_factor_leakage(selected_rows, arm_id, factor_ids_by_arm)
        variance_items.extend(_factor_variance_items(arm_id, selected_rows, factor_headers))
        summary_arms.append(
            {
                "arm_id": arm_id,
                "selected_design_id": selected.get("design_id", ""),
                "source_design_id": selected.get("source_design_id", ""),
                "row_count": len(selected_rows),
                "factor_count": len(factor_headers),
                "factor_ids": factor_headers,
                "cross_arm_factor_leakage": leak_columns,
                "selected_design_path": f"campaign_arms/{arm_id}/selected_wave_1_design.csv",
            }
        )
    write_json(
        out_dir / "per_arm_projection_summary.json",
        {
            "schema_version": 1,
            "projection_summary_kind": "ferm_doe_per_arm_projection_summary",
            "campaign_id": state.get("campaign_id"),
            "arms": summary_arms,
        },
    )
    write_json(
        out_dir / "factor_variance_report.json",
        {
            "schema_version": 1,
            "report_kind": "ferm_doe_per_arm_factor_variance",
            "items": variance_items,
        },
    )
    write_json(
        out_dir / "categorical_aliasing_report.json",
        {
            "schema_version": 1,
            "report_kind": "ferm_doe_per_arm_categorical_aliasing",
            "method": "cramers_v",
            "items": [],
            "notes": ["Per-arm categorical aliasing is emitted when categorical factors are present in selected arm designs."],
        },
    )


def _cross_arm_factor_leakage(rows: list[dict[str, Any]], arm_id: str, factor_ids_by_arm: dict[str, set[str]]) -> list[str]:
    own = factor_ids_by_arm.get(arm_id, set())
    others = set().union(*(ids for other_arm, ids in factor_ids_by_arm.items() if other_arm != arm_id)) if factor_ids_by_arm else set()
    leaked = []
    for row in rows:
        for factor_id in sorted(others - own):
            if row.get(factor_id) not in {None, ""}:
                leaked.append(factor_id)
    return sorted(set(leaked))


def _factor_variance_items(arm_id: str, rows: list[dict[str, Any]], factor_headers: list[str]) -> list[dict[str, Any]]:
    items = []
    for factor_id in factor_headers:
        values = {str(row.get(factor_id, "")) for row in rows if row.get(factor_id, "") not in {None, ""}}
        status = "constant" if len(values) <= 1 else "varied"
        items.append({"arm_id": arm_id, "factor_id": factor_id, "distinct_value_count": len(values), "status": status})
    return items


def _ledger_rows(state: dict[str, Any], manifest_path: Path) -> list[dict[str, str]]:
    for item in state.get("inputs", []):
        text = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower()
        if "ledger" in text or "run" in text:
            path = resolve_path(str(item.get("path") or ""), manifest_path.parent)
            if path and path.exists():
                rows, _ = read_csv(path)
                return rows
    return []


def _write_data_trust(path: Path, state: dict[str, Any], manifest_path: Path) -> None:
    rows = _ledger_rows(state, manifest_path)
    trusted = sum(1 for row in rows if str(row.get("inclusion_status", "")).lower() in {"trusted", "included", "usable"})
    path.write_text(
        "# Data Trust Report\n\n"
        f"- Rows: {len(rows)}\n"
        f"- Trusted or usable rows: {trusted}\n"
        "- Policy: source-derived, transformed, inferred, synthetic, and excluded data must remain distinguishable.\n"
    )


def _write_factor_audit(path: Path, state: dict[str, Any]) -> None:
    rows = [
        [
            factor["factor_id"],
            factor.get("type", ""),
            factor.get("unit", ""),
            factor.get("min", ""),
            factor.get("max", ""),
            factor.get("phase", ""),
            factor.get("controllable", ""),
        ]
        for factor in state.get("factors", [])
    ]
    path.write_text("# Factor Space Audit\n\n" + markdown_table(["Factor", "Type", "Unit", "Min", "Max", "Phase", "Controllable"], rows) + "\n")


def _write_assay_report(path: Path, state: dict[str, Any], readiness: dict[str, Any]) -> None:
    issues = [issue for issue in readiness.get("warnings", []) + readiness.get("blockers", []) if "assay" in issue.get("field", "") or "response" in issue.get("field", "")]
    issue_rows = [[issue["field"], issue["severity"], issue["message"]] for issue in issues]
    response_rows = []
    for response in state.get("responses", []):
        response_rows.append(
            [
                response.get("response_id", ""),
                response.get("class", ""),
                response.get("measurement_type", ""),
                response.get("assay_required", ""),
                response.get("assay_method", ""),
                response.get("sample_fraction", ""),
                response.get("calibration") or response.get("standard_curve") or "",
                response.get("matrix_effects_policy", ""),
            ]
        )
    power = evaluate_assay_power(state)
    power_rows = [
        [item.get("response_id", ""), item.get("status", ""), item.get("score", ""), item.get("metrics", {}).get("power_proxy", "")]
        for item in power.get("items", [])
    ]
    path.write_text(
        "# Assay Readiness Report\n\n"
        "This gate blocks optimization when response semantics or assay readiness are not credible.\n\n"
        "## Response Contract\n\n"
        + markdown_table(["Response", "Class", "Measurement", "Assay required", "Method", "Fraction", "Calibration", "Matrix policy"], response_rows)
        + "\n\n## Assay Power Proxy\n\n"
        + markdown_table(["Response", "Status", "Score", "Power proxy"], power_rows)
        + "\n\n## Issues\n\n"
        + markdown_table(["Field", "Severity", "Message"], issue_rows)
        + "\n"
    )


def _write_feasibility_report(path: Path, state: dict[str, Any], readiness: dict[str, Any]) -> None:
    issues = [
        issue
        for issue in readiness.get("warnings", []) + readiness.get("blockers", [])
        if any(token in issue.get("field", "") for token in ["equipment", "reagent", "cost", "mode"])
    ]
    path.write_text(
        "# Feasibility Report\n\n"
        + markdown_table(["Field", "Severity", "Message"], [[i["field"], i["severity"], i["message"]] for i in issues])
        + "\n"
    )


def _write_adjudication_md(path: Path, tournament: dict[str, Any]) -> None:
    rows = [
        [item["design_id"], item["lane"], item["accepted"], item["total_score"], "; ".join(item["rejection_reasons"])]
        for item in tournament.get("candidates", [])
    ]
    path.write_text(
        "# Design Adjudication\n\n"
        f"- Verdict: {tournament['verdict']}\n"
        f"- Selected design: {tournament['selected_design_id']}\n\n"
        + markdown_table(["Design", "Lane", "Accepted", "Score", "Rejection reasons"], rows)
        + "\n"
    )


def _write_design_comparison_md(path: Path, comparison: dict[str, Any]) -> None:
    has_swarm = any(item.get("swarm_factor_universe_alignment") is not None for item in comparison.get("rows", []))
    rows = [
        [
            item["design_id"],
            item["lane"],
            item["accepted"],
            item["total_score"],
            item.get("rank", ""),
            item.get("model_term_count", ""),
            item.get("d_efficiency", ""),
            item.get("swarm_factor_universe_alignment", "") if has_swarm else None,
            item.get("swarm_assumption_safety", "") if has_swarm else None,
            item.get("swarm_observability_coverage", "") if has_swarm else None,
            item.get("swarm_control_strategy_fit", "") if has_swarm else None,
            item.get("constraint_violations", ""),
        ]
        for item in comparison.get("rows", [])
    ]
    headers = ["Design", "Lane", "Accepted", "Score", "Rank", "Terms", "D-eff"]
    if has_swarm:
        headers.extend(["Factor align", "Assumption", "Observability", "Controls"])
    headers.append("Violations")
    if not has_swarm:
        rows = [[cell for cell in row if cell is not None] for row in rows]
    path.write_text(
        "# Design Comparison\n\n"
        f"- Selected design: {comparison.get('selected_design_id')}\n\n"
        + markdown_table(headers, rows)
        + "\n"
    )


def _write_experimental_setup(
    out_dir: Path,
    state: dict[str, Any],
    selected: dict[str, Any] | None,
    tournament: dict[str, Any],
) -> None:
    setup = _experimental_setup_payload(out_dir, state, selected, tournament)
    write_json(out_dir / "experimental_setup.json", setup)
    rows = []
    for arm in setup.get("arms", []):
        rows.append(
            [
                arm.get("arm_id", ""),
                arm.get("target_format", ""),
                arm.get("target_scale", ""),
                arm.get("vessel", ""),
                arm.get("working_volume_ml", ""),
                arm.get("duration_h", ""),
                arm.get("planned_run_count", ""),
                arm.get("purpose", ""),
            ]
        )
    goal_rows = [
        [goal.get("goal_id", ""), goal.get("response_id", ""), goal.get("direction", ""), goal.get("description", "")]
        for goal in setup.get("optimization_goals", [])
    ]
    (out_dir / "experimental_setup.md").write_text(
        "# Experimental Setup\n\n"
        f"- Campaign: {setup.get('campaign_id')}\n"
        f"- Scale direction: {setup.get('scale_direction')}\n"
        f"- Current format: {setup.get('current_format')}\n"
        f"- Current scale: {setup.get('current_scale')}\n"
        f"- Target format: {setup.get('target_format')}\n"
        f"- Target scale: {setup.get('target_scale')}\n"
        f"- Claim boundary: {setup.get('claim_boundary')}\n\n"
        "## Arms\n\n"
        + markdown_table(["Arm", "Format", "Scale", "Vessel", "Volume mL", "Duration h", "Runs", "Purpose"], rows)
        + "\n\n## Optimization Goals\n\n"
        + markdown_table(["Goal", "Response", "Direction", "Description"], goal_rows)
        + "\n"
    )


def _experimental_setup_payload(
    out_dir: Path,
    state: dict[str, Any],
    selected: dict[str, Any] | None,
    tournament: dict[str, Any],
) -> dict[str, Any]:
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    selected_rows = selected.get("rows", []) if selected else []
    if campaign_arms_enabled(state):
        selected_rows, _ = _read_csv_if_exists(out_dir / "selected_wave_1_design.csv")
    arms = _setup_arms(out_dir, state, selected, tournament)
    return {
        "schema_version": 1,
        "setup_kind": "ferm_doe_experimental_setup",
        "campaign_id": state.get("campaign_id"),
        "current_format": _first_context(context, "current_format", "source_format"),
        "current_scale": _first_context(context, "current_scale", "source_scale"),
        "target_format": _first_context(context, "target_format", "desired_format", "vessel"),
        "target_scale": _first_context(context, "target_scale", "desired_scale", "working_volume_ml"),
        "scale_direction": _scale_direction(state),
        "workflow_modes": state.get("workflow_modes", {}).get("selected", []),
        "planned_run_count": len(selected_rows),
        "selected_design_id": tournament.get("selected_design_id"),
        "optimization_goals": _optimization_goals(state),
        "arms": arms,
        "setup_context": context.get("experimental_setup") or context.get("setup_plan") or {},
        "claim_boundary": "planned_experimental_setup_only",
        "forbidden_claims": ["optimized", "validated", "production_ready", "validated_transfer"],
    }


def _setup_arms(
    out_dir: Path,
    state: dict[str, Any],
    selected: dict[str, Any] | None,
    tournament: dict[str, Any],
) -> list[dict[str, Any]]:
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    if campaign_arms_enabled(state):
        arms = []
        for arm in state.get("campaign_arms", []) or []:
            arm_id = str(arm.get("arm_id") or "").strip()
            rows, _ = _read_csv_if_exists(out_dir / "campaign_arms" / arm_id / "selected_wave_1_design.csv")
            arm_tournament = tournament.get("per_arm", {}).get(arm_id, {}) if isinstance(tournament.get("per_arm"), dict) else {}
            arms.append(_setup_arm_payload(arm, context, len(rows), arm_tournament.get("selected_design_id", "")))
        return arms

    active_arm = state.get("campaign_arm") if isinstance(state.get("campaign_arm"), dict) else {}
    selected_rows = selected.get("rows", []) if selected else []
    if active_arm:
        return [_setup_arm_payload(active_arm, context, len(selected_rows), tournament.get("selected_design_id", ""))]
    return [
        {
            "arm_id": "campaign",
            "name": state.get("name", ""),
            "purpose": state.get("objective", {}).get("primary", ""),
            "target_format": _first_context(context, "target_format", "desired_format", "vessel"),
            "target_scale": _first_context(context, "target_scale", "desired_scale", "working_volume_ml"),
            "vessel": context.get("vessel", ""),
            "working_volume_ml": context.get("working_volume_ml", ""),
            "duration_h": context.get("duration_h", ""),
            "planned_run_count": len(selected_rows),
            "selected_design_id": tournament.get("selected_design_id", ""),
            "factor_ids": [factor.get("factor_id", "") for factor in state.get("factors", [])],
            "response_ids": [response.get("response_id", "") for response in state.get("responses", [])],
            "constraint_ids": [constraint.get("constraint_id") or constraint.get("id") or "" for constraint in state.get("constraints", [])],
            "execution_policy": state.get("design_policy", {}).get("execution_policy", {}),
            "notes": [],
        }
    ]


def _setup_arm_payload(arm: dict[str, Any], context: dict[str, Any], run_count: int, selected_design_id: str) -> dict[str, Any]:
    working_volume = arm.get("working_volume_ml", "")
    target_scale = f"{working_volume} mL" if not _is_blank(working_volume) else _first_context(context, "target_scale", "desired_scale", "working_volume_ml")
    return {
        "arm_id": arm.get("arm_id", ""),
        "name": arm.get("name", ""),
        "purpose": arm.get("purpose", ""),
        "target_format": arm.get("kind") or arm.get("vessel") or _first_context(context, "target_format", "desired_format", "vessel"),
        "target_scale": target_scale,
        "vessel": arm.get("vessel", ""),
        "working_volume_ml": working_volume,
        "duration_h": arm.get("duration_h", ""),
        "planned_run_count": run_count,
        "selected_design_id": selected_design_id,
        "factor_ids": arm.get("factor_ids", []),
        "response_ids": arm.get("response_ids", []),
        "constraint_ids": arm.get("constraint_ids", []),
        "execution_policy": arm.get("execution_policy", {}),
        "notes": arm.get("notes", []),
    }


def _write_horizontal_doe(
    out_dir: Path,
    state: dict[str, Any],
    selected: dict[str, Any] | None,
    tournament: dict[str, Any],
) -> None:
    rows = _horizontal_doe_rows(out_dir, state, selected, tournament)
    factor_ids = [str(factor.get("factor_id") or "") for factor in state.get("factors", []) if factor.get("factor_id")]
    response_ids = [str(response.get("response_id") or "") for response in state.get("responses", []) if response.get("response_id")]
    headers = _horizontal_doe_headers(rows, factor_ids, response_ids)
    write_csv(out_dir / "horizontal_doe.csv", rows, headers)
    write_json(
        out_dir / "horizontal_doe.json",
        {
            "schema_version": 1,
            "doe_kind": "ferm_doe_horizontal_planned_conditions",
            "campaign_id": state.get("campaign_id"),
            "row_count": len(rows),
            "headers": headers,
            "rows": rows,
            "claim_boundary": "planned_conditions_only",
            "notes": [
                "Rows are a horizontal review surface for planned conditions and goals.",
                "Per-arm executable CSVs remain the authority for physical setup when campaign arms are incompatible.",
            ],
        },
    )


def _horizontal_doe_rows(
    out_dir: Path,
    state: dict[str, Any],
    selected: dict[str, Any] | None,
    tournament: dict[str, Any],
) -> list[dict[str, Any]]:
    if campaign_arms_enabled(state):
        rows: list[dict[str, Any]] = []
        for arm in state.get("campaign_arms", []) or []:
            arm_id = str(arm.get("arm_id") or "").strip()
            selected_rows, _ = _read_csv_if_exists(out_dir / "campaign_arms" / arm_id / "selected_wave_1_design.csv")
            arm_tournament = tournament.get("per_arm", {}).get(arm_id, {}) if isinstance(tournament.get("per_arm"), dict) else {}
            for row in selected_rows:
                rows.append(_horizontal_doe_row(state, row, arm, arm_tournament.get("selected_design_id", "")))
        return rows

    rows = []
    for row in selected.get("rows", []) if selected else []:
        rows.append(_horizontal_doe_row(state, row, {}, tournament.get("selected_design_id", "")))
    return rows


def _horizontal_doe_row(
    state: dict[str, Any],
    source_row: dict[str, Any],
    arm: dict[str, Any],
    selected_design_id: str,
) -> dict[str, Any]:
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    arm_id = str(arm.get("arm_id") or state.get("active_campaign_arm") or source_row.get("arm_id") or "").strip()
    goal_text = state.get("objective", {}).get("primary", "")
    secondary = _secondary_goal_text(state)
    row = {
        "run_id": source_row.get("run_id", ""),
        "arm_id": arm_id,
        "selected_design_id": selected_design_id,
        "condition_set_kind": "new_planned_condition",
        "scale_direction": _scale_direction(state),
        "target_format": arm.get("kind") or arm.get("vessel") or _first_context(context, "target_format", "desired_format", "vessel"),
        "target_scale": _target_scale_for_row(arm, context),
        "vessel": arm.get("vessel", context.get("vessel", "")),
        "working_volume_ml": arm.get("working_volume_ml", context.get("working_volume_ml", "")),
        "duration_h": arm.get("duration_h", context.get("duration_h", "")),
        "optimization_goal": goal_text,
        "secondary_goals": secondary,
        "primary_response_id": state.get("objective", {}).get("response_id", ""),
        "objective_direction": state.get("objective", {}).get("direction", ""),
        "design_intent": state.get("design_policy", {}).get("design_intent", ""),
        "planned_status": source_row.get("planned_status", "planned"),
    }
    for header in CONTROL_ROW_HEADERS:
        row[header] = source_row.get(header, "")
    for factor in state.get("factors", []):
        factor_id = str(factor.get("factor_id") or "")
        if factor_id:
            row[factor_id] = source_row.get(factor_id, "")
    for response in state.get("responses", []):
        response_id = str(response.get("response_id") or "")
        if response_id:
            row[response_id] = ""
    return row


def _horizontal_doe_headers(rows: list[dict[str, Any]], factor_ids: list[str], response_ids: list[str]) -> list[str]:
    preferred = [
        "run_id",
        "arm_id",
        "selected_design_id",
        "condition_set_kind",
        "scale_direction",
        "target_format",
        "target_scale",
        "vessel",
        "working_volume_ml",
        "duration_h",
        "optimization_goal",
        "secondary_goals",
        "primary_response_id",
        "objective_direction",
        "design_intent",
        "planned_status",
    ] + CONTROL_ROW_HEADERS + factor_ids + response_ids
    return _ordered_csv_headers(rows, preferred)


def _ordered_csv_headers(rows: list[dict[str, Any]], preferred: list[str]) -> list[str]:
    headers = [header for header in preferred if header]
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def _read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    return read_csv(path)


def _scale_direction(state: dict[str, Any]) -> str:
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    explicit = _first_context(context, "scale_direction", "scale_transfer_direction")
    if explicit:
        return str(explicit)
    selected_modes = set(state.get("workflow_modes", {}).get("selected", []))
    has_scale_up = "bioreactor-scale-up" in selected_modes
    has_downscale = "bioreactor-to-plate-downscale" in selected_modes
    if has_scale_up and has_downscale:
        return "coupled_scale_up_downscale"
    if has_scale_up:
        return "scale_up"
    if has_downscale:
        return "scale_down"
    if campaign_arms_enabled(state):
        return "coupled_scale_transfer"
    return "not_declared"


def _optimization_goals(state: dict[str, Any]) -> list[dict[str, Any]]:
    objective = state.get("objective") if isinstance(state.get("objective"), dict) else {}
    goals = [
        {
            "goal_id": "primary",
            "response_id": objective.get("response_id", ""),
            "direction": objective.get("direction", ""),
            "description": objective.get("primary", ""),
        }
    ]
    secondary = objective.get("secondary", [])
    if isinstance(secondary, list):
        for index, item in enumerate(secondary, start=1):
            if isinstance(item, dict):
                goals.append(
                    {
                        "goal_id": str(item.get("goal_id") or item.get("id") or f"secondary_{index}"),
                        "response_id": item.get("response_id", ""),
                        "direction": item.get("direction", ""),
                        "description": item.get("description") or item.get("primary") or item.get("name") or "",
                    }
                )
            else:
                goals.append({"goal_id": f"secondary_{index}", "response_id": "", "direction": "", "description": str(item)})
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    raw_goals = context.get("optimization_goals")
    if isinstance(raw_goals, list):
        for index, item in enumerate(raw_goals, start=1):
            if isinstance(item, dict):
                goals.append(
                    {
                        "goal_id": str(item.get("goal_id") or item.get("id") or f"manifest_goal_{index}"),
                        "response_id": item.get("response_id", ""),
                        "direction": item.get("direction", ""),
                        "description": item.get("description") or item.get("name") or "",
                    }
                )
            else:
                goals.append({"goal_id": f"manifest_goal_{index}", "response_id": "", "direction": "", "description": str(item)})
    return [goal for goal in goals if goal.get("description") or goal.get("response_id")]


def _secondary_goal_text(state: dict[str, Any]) -> str:
    goals = _optimization_goals(state)
    return "; ".join(str(goal.get("description") or goal.get("response_id") or "") for goal in goals[1:] if goal)


def _target_scale_for_row(arm: dict[str, Any], context: dict[str, Any]) -> Any:
    working_volume = arm.get("working_volume_ml", "")
    if not _is_blank(working_volume):
        return f"{working_volume} mL"
    return _first_context(context, "target_scale", "desired_scale", "working_volume_ml")


def _first_context(context: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = context.get(key)
        if not _is_blank(value):
            return value
    return ""


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def _write_run_sheet(path: Path, state: dict[str, Any], selected: dict[str, Any] | None) -> None:
    run_count = len(selected.get("rows", [])) if selected else 0
    control_rows = [row for row in selected.get("rows", [])] if selected else []
    control_rows = [row for row in control_rows if row.get("run_role") == "control"]
    control_types = sorted({str(row.get("control_type")) for row in control_rows if row.get("control_type")})
    modes = ", ".join(state.get("workflow_modes", {}).get("selected", []))
    phases = sorted({factor.get("phase", "unspecified") for factor in state.get("factors", [])})
    path.write_text(
        "# first-batch Run Sheet\n\n"
        f"- Campaign: {state['campaign_id']}\n"
        f"- Selected design: {selected.get('design_id') if selected else 'none'}\n"
        f"- Planned runs: {run_count}\n"
        + f"- Explicit control rows: {len(control_rows)}"
        + (f" ({', '.join(control_types)})\n" if control_types else "\n")
        + f"- Workflow modes: {modes}\n"
        f"- Factor phases represented: {', '.join(phases)}\n"
        "- Control strategy: preserve campaign pH, DO, feed, induction, sampling, and assay policies from the manifest; unresolved policies remain readiness caveats.\n"
        "- Operator note: review assay, safety, and equipment readiness before physical setup.\n"
    )


def _write_sampling_schedule(path: Path, state: dict[str, Any]) -> None:
    response_rows = [
        [response["response_id"], response.get("class", ""), response.get("sample_fraction", ""), response.get("assay_method", "")]
        for response in state.get("responses", [])
    ]
    path.write_text(
        "# Sampling Schedule\n\n"
        "- Default: capture time zero, induction/feed switch if applicable, midpoint, endpoint, and any campaign-specified offline biomass/product timepoints.\n"
        "- Product assay timing must be compatible with response semantics and sample stability.\n"
        "- For hydrophobic or pellet-associated products, capture whole-broth or pellet-compatible samples unless the assay contract says otherwise.\n\n"
        + markdown_table(["Response", "Class", "Sample fraction", "Assay"], response_rows)
        + "\n"
    )


def _write_result_template(path: Path, state: dict[str, Any]) -> None:
    headers = ["run_id"]
    if state.get("active_campaign_arm") or campaign_arms_enabled(state):
        headers.append("arm_id")
    headers += ["assay_time_h"] + [factor["factor_id"] for factor in state.get("factors", [])]
    headers += [response["response_id"] for response in state.get("responses", [])]
    headers += ["biomass", "notes", "inclusion_status", "trust_score"]
    write_csv(path, [], headers)


def _write_wave2_rules(path: Path, state: dict[str, Any], tournament: dict[str, Any]) -> None:
    rules = build_wave2_decision_rules(state, tournament)
    write_json(path.with_suffix(".json"), rules)
    path.write_text(
        "# follow-up Decision Rules\n\n"
        "- If assay or response semantics fail, pause and repair assay before more DoE.\n"
        "- If the best run is on a factor boundary, expand or shift that factor range after feasibility review.\n"
        "- If top titer and productivity disagree, adjudicate with the campaign objective and cost/time policy.\n"
        "- If all candidates underperform the control, confirm the control and record failed regions as negative-result memory.\n"
        "- If oxygen, feed, pH/base, foam, sampling, or assay artifacts dominate response variation, pause DOE and repair the process or assay contract.\n"
        "- If selected design is not accepted, do not run; resolve rejection reasons first.\n"
        f"- Current selected design: {tournament['selected_design_id']}.\n"
        "- Claim boundary: planned next-experiment-round candidates only; no optimized, validated, production-ready, or scale-transfer success claim is allowed without executed joined evidence.\n"
    )


def build_wave2_decision_rules(state: dict[str, Any], tournament: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "rules_kind": "ferm_doe_wave2_decision_rules",
        "campaign_id": state.get("campaign_id"),
        "selected_design_id": tournament.get("selected_design_id"),
        "response_id": state.get("objective", {}).get("response_id"),
        "allowed_actions": ["confirm", "narrow", "expand", "pause", "stop", "scale_or_downscale"],
        "required_checks": [
            "result rows join selected first-batch design by run_id or arm_id/run_id",
            "QC-failed, excluded, and low-trust rows do not drive recommendations",
            "assay_power must pass or be explicitly caveated before RSM/confirmatory claims",
            "negative-result memory remains arm-scoped",
            "scale_or_downscale requires passing arm_bridge_policy evidence",
        ],
        "claim_boundary": "planned_wave2_design_only",
        "forbidden_claims": ["optimized", "validated", "production_ready", "validated_transfer"],
    }


def _write_provenance(path: Path, state: dict[str, Any], manifest_path: Path) -> None:
    compute = state.get("compute_policy") if isinstance(state.get("compute_policy"), dict) else {}
    default_profile = compute.get("default_profile", "local-stdlib")
    approved_provider = compute.get("approved_remote_provider") or compute.get("blessed_remote_provider", "external_adapter")
    path.write_text(
        "# Provenance\n\n"
        f"- Source manifest: {manifest_path}\n"
        "- Generator: biosymphony_ferm_doe.dossier.compile_dossier\n"
        f"- Compute profile: {default_profile}\n"
        f"- Approved remote provider: {approved_provider}\n"
        "- Execution mode: local dry-run; no Linear issues created and no remote compute resources launched.\n"
    )


def _write_verdict(path: Path, readiness: dict[str, Any], tournament: dict[str, Any]) -> None:
    path.write_text(
        "# Readiness Verdict\n\n"
        f"- Status: {readiness['status']}\n"
        f"- Score: {readiness['score']}\n"
        f"- Recommended action: {readiness['recommended_action']}\n"
        f"- Selected design: {tournament['selected_design_id']}\n"
        f"- Tournament verdict: {tournament['verdict']}\n"
    )


def _write_doe_export(path: Path, state: dict[str, Any], selected: dict[str, Any] | None) -> None:
    factors = [factor["factor_id"] for factor in state.get("factors", [])]
    responses = [response["response_id"] for response in state.get("responses", [])]
    headers = ["design_id", "run_id", "block", "randomization_group"] + CONTROL_ROW_HEADERS + factors + responses
    rows = []
    for index, row in enumerate(selected.get("rows", []) if selected else []):
        export_row = {
            "design_id": selected.get("design_id", ""),
            "run_id": row.get("run_id", ""),
            "block": row.get("block", ""),
            "randomization_group": index + 1,
        }
        for header in CONTROL_ROW_HEADERS:
            export_row[header] = row.get(header, "")
        for factor_id in factors:
            export_row[factor_id] = row.get(factor_id, "")
        for response_id in responses:
            export_row[response_id] = ""
        rows.append(export_row)
    write_csv(path, rows, headers)


def _compile_required_utilities(
    manifest_path: Path,
    out_dir: Path,
    state: dict[str, Any],
    run_budget: int | None,
) -> list[dict[str, Any]]:
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    required = policy.get("required_utilities") if isinstance(policy.get("required_utilities"), list) else []
    outputs: list[dict[str, Any]] = []
    if not required:
        return outputs
    utility_root = out_dir / "utility_outputs"
    backend = policy.get("utility_backend")
    for utility in required:
        utility_name = str(utility)
        target = utility_root / utility_name
        if utility_name == "custom-optimal":
            from .utilities.custom_optimal import run_custom_optimal_utility

            run_custom_optimal_utility(manifest_path, target, run_budget=run_budget, backend=backend)
        elif utility_name == "simulate-design":
            from .utilities.simulate import run_simulate_design_utility

            run_simulate_design_utility(manifest_path, target, run_budget=run_budget, backend=backend)
        elif utility_name == "doe-export":
            from .utilities.doe_compat import run_doe_export_utility

            run_doe_export_utility(manifest_path, target, backend=backend)
        elif utility_name == "benchmark-doe":
            from .utilities.benchmark import run_benchmark_doe_utility

            run_benchmark_doe_utility(manifest_path, target, backend=backend)
        elif utility_name == "assay-power":
            from .utilities.assay_power import run_assay_power_utility

            run_assay_power_utility(out_dir / "campaign_state.json", target, backend=backend)
        else:
            target.mkdir(parents=True, exist_ok=True)
            write_json(
                target / "utility_manifest.json",
                {
                    "schema_version": 1,
                    "manifest_kind": "ferm_doe_utility_manifest",
                    "utility": utility_name,
                    "backend": {"requested": backend or "auto", "selected": "none", "status": "skipped", "fallback": "", "caveat": "Utility requires result inputs or is not dossier-runnable."},
                    "artifacts": [],
                    "caveats": ["Utility was marked required but cannot run during dossier compilation without additional inputs."],
                },
            )
        outputs.append({"utility": utility_name, "path": str(target)})
    return outputs


def copy_dossier(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
