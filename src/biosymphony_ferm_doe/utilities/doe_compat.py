"""Optional reference DOE import/export utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..compiler import compile_campaign_state
from ..constraints import validate_design_rows
from ..doe import propose_candidate_designs
from ..io_utils import read_csv, write_csv, write_json
from ..model_matrix import diagnose_design
from .common import utility_manifest


def run_doe_export_utility(
    manifest_path: Path,
    out_dir: Path,
    backend: str | None = None,
    import_factors: Path | None = None,
    import_design: Path | None = None,
    import_results: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / "doe_export_bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    state = compile_campaign_state(manifest_path)
    designs = propose_candidate_designs(manifest_path, state)
    selected = _select_export_design(designs)
    factors = state.get("factors", [])
    responses = state.get("responses", [])
    constraints = state.get("constraints", [])
    write_csv(bundle / "factors.csv", export_factor_rows(factors), factor_export_headers())
    write_csv(bundle / "responses.csv", export_response_rows(responses), response_export_headers())
    write_csv(bundle / "constraints.csv", export_constraint_rows(constraints), constraint_export_headers())
    write_json(bundle / "constraints.json", {"schema_version": 1, "constraints": constraints})
    write_json(bundle / "model_terms.json", state.get("model_terms", {}))
    write_csv(bundle / "design_table.csv", selected.get("rows", []), design_export_headers(selected.get("rows", []), factors))
    write_json(bundle / "diagnostics.json", selected.get("diagnostics", {}))
    write_json(bundle / "randomization.json", export_randomization_policy(state))
    write_json(bundle / "assumptions.json", {"schema_version": 1, "items": state.get("assumptions", [])})
    write_json(bundle / "non_parity_notes.json", non_parity_notes(state, selected))
    write_csv(
        bundle / "result_template.csv",
        [],
        ["run_id"] + [factor["factor_id"] for factor in factors] + [response["response_id"] for response in responses] + ["block_id", "execution_order", "notes", "inclusion_status", "trust_score"],
    )
    import_report = import_doe_like_files(state, import_factors, import_design, import_results, out_dir)
    result = {
        "schema_version": 1,
        "utility_result_kind": "doe_compatibility",
        "campaign_id": state.get("campaign_id"),
        "export_bundle": str(bundle),
        "selected_design_id": selected.get("design_id", ""),
        "exported_files": sorted(path.name for path in bundle.iterdir()),
        "import_report": import_report,
    }
    write_json(out_dir / "doe_compatibility.json", result)
    utility_manifest(
        utility="doe-export",
        out_dir=out_dir,
        inputs={
            "manifest": str(manifest_path),
            "import_factors": str(import_factors) if import_factors else "",
            "import_design": str(import_design) if import_design else "",
            "import_results": str(import_results) if import_results else "",
        },
        backend=backend or state.get("design_policy", {}).get("utility_backend"),
        artifacts=["doe_export_bundle/", "doe_import_report.json", "doe_compatibility.json"],
        metric_labels={"export": "csv_compatibility"},
        caveats=["Import accepts simple CSV-shaped factor/design/result tables, not proprietary project files."],
    )
    return result


def import_doe_like_files(
    state: dict[str, Any],
    factor_csv: Path | None,
    design_csv: Path | None,
    results_csv: Path | None,
    out_dir: Path,
) -> dict[str, Any]:
    report = {
        "schema_version": 1,
        "import_kind": "doe_like_csv_import",
        "campaign_id": state.get("campaign_id"),
        "imported": {},
        "warnings": [],
    }
    if factor_csv:
        rows, headers = read_csv(factor_csv)
        factors = []
        for row in rows:
            factor_id = row.get("factor_id") or row.get("Factor") or row.get("Name") or row.get("name")
            if not factor_id:
                continue
            factors.append(
                {
                    "factor_id": factor_id,
                    "name": row.get("name") or row.get("Name") or factor_id,
                    "type": (row.get("type") or row.get("Type") or "continuous").lower(),
                    "min": row.get("min") or row.get("Low") or row.get("low"),
                    "max": row.get("max") or row.get("High") or row.get("high"),
                    "levels": [item.strip() for item in (row.get("levels") or row.get("Levels") or "").split(";") if item.strip()],
                }
            )
        write_json(out_dir / "imported_manifest_fragment.json", {"schema_version": 1, "factors": factors})
        report["imported"]["factors"] = {"path": str(factor_csv), "rows": len(factors), "headers": headers}
    if design_csv:
        rows, headers = read_csv(design_csv)
        write_csv(out_dir / "imported_design_table.csv", rows, headers)
        factors = state.get("factors", [])
        constraints = state.get("constraints", [])
        diagnostics = diagnose_design(rows, factors, constraints, state.get("model_terms") or {})
        violations = validate_design_rows(rows, factors, constraints)
        design_report = {
            "path": str(design_csv),
            "rows": len(rows),
            "headers": headers,
            "claim_level": "user_supplied_design_import_validated",
            "method_family": "user_supplied_design",
            "constraint_violation_count": len(violations),
            "diagnostic_verdict": diagnostics.get("diagnostic_verdict", {}),
            "exactness": "user_supplied_unknown",
            "backend_used": "csv_import",
        }
        write_json(out_dir / "imported_design_metadata.json", {**design_report, "diagnostics": diagnostics, "constraint_violations": violations})
        report["imported"]["design"] = design_report
    if results_csv:
        rows, headers = read_csv(results_csv)
        write_csv(out_dir / "imported_results.csv", rows, headers)
        report["imported"]["results"] = {"path": str(results_csv), "rows": len(rows), "headers": headers}
    if not report["imported"]:
        report["warnings"].append("No import CSVs supplied; export-only run.")
    write_json(out_dir / "doe_import_report.json", report)
    return report


def _select_export_design(designs: dict[str, Any]) -> dict[str, Any]:
    for design_id in ["custom_optimal", "space_filling", "classical_screening"]:
        for candidate in designs.get("candidates", []):
            if candidate.get("design_id") == design_id and candidate.get("rows"):
                return candidate
    for candidate in designs.get("candidates", []):
        if candidate.get("rows"):
            return candidate
    return {"design_id": "", "rows": [], "diagnostics": {}}


def factor_export_headers() -> list[str]:
    return [
        "factor_id",
        "name",
        "type",
        "unit",
        "min",
        "max",
        "levels",
        "transform",
        "role",
        "phase",
        "controllable",
        "fixed_value",
        "block",
        "hard_to_change",
        "arm_id",
        "mixture_group",
        "mixture_sum",
        "source",
    ]


def response_export_headers() -> list[str]:
    return [
        "response_id",
        "name",
        "unit",
        "direction",
        "class",
        "measurement_type",
        "assay_required",
        "assay_method",
        "sample_fraction",
        "calibration",
        "standard_curve",
        "matrix_effects_policy",
        "derived_from",
        "primary",
    ]


def constraint_export_headers() -> list[str]:
    return ["constraint_id", "type", "description", "expression", "operator", "rhs", "coefficients", "values", "when", "run_ids"]


def export_factor_rows(factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _csv_value(factor.get(key)) for key in factor_export_headers()} for factor in factors]


def export_response_rows(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _csv_value(response.get(key)) for key in response_export_headers()} for response in responses]


def export_constraint_rows(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, constraint in enumerate(constraints, start=1):
        item = {key: _csv_value(constraint.get(key)) for key in constraint_export_headers()}
        item["constraint_id"] = item["constraint_id"] or constraint.get("id") or f"constraint_{index}"
        item["type"] = item["type"] or constraint.get("constraint_type", "")
        rows.append(item)
    return rows


def design_export_headers(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> list[str]:
    headers = ["run_id", "run_role", "control_type", "control_source", "control_purpose", "block_id", "block", "randomization_group", "fixed_row"]
    for factor in factors:
        factor_id = str(factor.get("factor_id") or "")
        if factor_id and factor_id not in headers:
            headers.append(factor_id)
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def export_randomization_policy(state: dict[str, Any]) -> dict[str, Any]:
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    execution = {}
    for key in ["execution_plan", "execution_policy", "randomization"]:
        if isinstance(policy.get(key), dict):
            execution = dict(policy[key])
            break
    return {
        "schema_version": 1,
        "randomization_kind": "ferm_doe_randomization_policy_export",
        "design_intent": policy.get("design_intent", ""),
        "run_budget": policy.get("run_budget", ""),
        "execution_policy": execution,
        "seed": execution.get("seed", policy.get("seed", "")) if isinstance(execution, dict) else policy.get("seed", ""),
        "notes": [
            "This export records planned randomization/blocking policy. Physical execution order lives in execution_plan.json when a dossier is compiled.",
        ],
    }


def non_parity_notes(state: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "notes_kind": "doe_export_non_parity_notes",
        "campaign_id": state.get("campaign_id"),
        "selected_design_id": selected.get("design_id", ""),
        "claim_level": selected.get("claim_level", ""),
        "exactness": selected.get("exactness", ""),
        "backend_used": selected.get("backend_used", ""),
        "method_family": selected.get("method_family", ""),
        "notes": [
            "CSV export is for DOE/statistician review and round-trip compatibility, not a proprietary project-file clone.",
            "Generation and scoring claims remain bounded by exactness, backend_used, diagnostics, and campaign readiness.",
            "Executed results must join back to selected run IDs before fitted or optimized claims are allowed.",
        ],
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        import json

        return json.dumps(value, sort_keys=True)
    if value is None:
        return ""
    return value
