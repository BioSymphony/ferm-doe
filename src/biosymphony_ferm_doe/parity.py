"""reference DOE parity matrix and report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io_utils import markdown_table, write_csv, write_json


PARITY_ROWS: list[dict[str, Any]] = [
    {
        "surface": "Custom Design",
        "current_status": "implemented_stdlib_core",
        "target_status": "doe_comparable_local",
        "required_artifacts": ["candidate_set.csv", "model_matrix.csv", "custom_design.scorecard.json"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_custom_design_core_artifacts -v",
        "bio_add_on": "fermentation feasibility and readiness gates before optimality selection",
    },
    {
        "surface": "Screening / DSD",
        "current_status": "implemented_with_exact_factorial_pb_and_dsd_like_labels",
        "target_status": "doe_comparable_screening",
        "required_artifacts": ["design_candidates/full_factorial.csv", "design_candidates/plackett_burman.csv", "design_candidates/definitive_screening_like.csv"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_doe_family_properties -v",
        "bio_add_on": "factor-prior audit from phase, product class, prior data, and literature slots",
    },
    {
        "surface": "RSM",
        "current_status": "implemented_ccd_and_box_behnken_like_stdlib",
        "target_status": "doe_comparable_rsm",
        "required_artifacts": ["design_candidates/central_composite.csv", "design_candidates/box_behnken.csv"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_doe_family_properties -v",
        "bio_add_on": "blocks RSM when assay or response semantics are weak",
    },
    {
        "surface": "Mixture",
        "current_status": "implemented_simplex_and_mixture_process_stdlib",
        "target_status": "doe_comparable_mixture",
        "required_artifacts": ["design_candidates/mixture_simplex.csv", "design_candidates/mixture_process.csv"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_mixture_design_enforces_sum -v",
        "bio_add_on": "media/feed feasibility, cost burden, and phase labels",
    },
    {
        "surface": "Space-Filling",
        "current_status": "implemented_lhs_halton_sobol_like_stdlib",
        "target_status": "doe_comparable_space_filling",
        "required_artifacts": ["design_candidates/latin_hypercube.csv", "design_candidates/halton_space_filling.csv", "design_candidates/sobol_like_space_filling.csv"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_space_filling_bounds_and_seed -v",
        "bio_add_on": "scouting only when priors justify wide exploration and follow-up narrowing is pre-registered",
    },
    {
        "surface": "Diagnostics",
        "current_status": "implemented_rank_estimability_efficiency_fds_prediction_variance_labels",
        "target_status": "doe_comparable_diagnostics",
        "required_artifacts": ["design_diagnostics.json", "*.scorecard.json"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_diagnostics_include_doe_comparable_fields -v",
        "bio_add_on": "assay power, sampling, oxygen/feed/pH/base/foam, cost, and mode-transfer diagnostics",
    },
    {
        "surface": "Compare Designs",
        "current_status": "implemented_design_tournament_and_comparison",
        "target_status": "doe_comparable_compare_designs",
        "required_artifacts": ["design_comparison.md", "design_comparison.json"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_compile_and_check_dossier -v",
        "bio_add_on": "skeptical assay, process, scale-transfer, and cost lanes can veto designs",
    },
    {
        "surface": "Augment Design",
        "current_status": "implemented_local_fallback_recommendation",
        "target_status": "doe_comparable_augmentation",
        "required_artifacts": ["wave2_recommendation.json", "negative_result_memory.json"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_ingest_wave_results_recommends_next_action -v",
        "bio_add_on": "negative-result memory and remaining run budget drive next action",
    },
    {
        "surface": "Bayesian Optimization",
        "current_status": "optional_adapter_planned_with_stdlib_fallback",
        "target_status": "optional_bofire_botorch_adapter",
        "required_artifacts": ["wave2_recommendation.json", "assumptions_and_nonparity.md"],
        "validation_command": "PYTHONPATH=src python3 -m unittest discover -s tests -v",
        "bio_add_on": "BO gated by assay readiness, phase logic, and infeasible-region memory",
    },
    {
        "surface": "Profiler / Prediction",
        "current_status": "implemented_operating_window_summary_from_design_diagnostics",
        "target_status": "doe_comparable_prediction_profiler",
        "required_artifacts": ["design_diagnostics.json", "doe_parity_report.md"],
        "validation_command": "PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_doe_parity_artifacts -v",
        "bio_add_on": "operating window includes lab execution caveats and fermentation readiness warnings",
    },
]


def parity_matrix(utility_root: Path | None = None) -> dict[str, Any]:
    rows = [dict(row) for row in PARITY_ROWS]
    utility_status = utility_backend_status(utility_root)
    for row in rows:
        surface = row["surface"]
        if surface == "Custom Design" and "custom-optimal" in utility_status:
            row["current_status"] = utility_status["custom-optimal"]
        elif surface == "Augment Design" and "augment-design" in utility_status:
            row["current_status"] = utility_status["augment-design"]
        elif surface == "Profiler / Prediction" and "profiler" in utility_status:
            row["current_status"] = utility_status["profiler"]
        elif surface == "Bayesian Optimization" and any("botorch" in status or "bofire" in status for status in utility_status.values()):
            row["current_status"] = "optional_adapter_backed_available"
    return {
        "schema_version": 1,
        "matrix_kind": "doe_comparable_parity_matrix",
        "claim_policy": "Current status must not be represented as full reference DOE parity unless validation artifacts exist.",
        "rows": rows,
    }


def write_parity_artifacts(
    out_dir: Path,
    state: dict[str, Any],
    tournament: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matrix = parity_matrix(out_dir / "utility_outputs")
    write_json(out_dir / "doe_parity_matrix.json", matrix)
    write_csv(out_dir / "doe_parity_matrix.csv", matrix["rows"])
    (out_dir / "doe_parity_report.md").write_text(render_parity_report(state, matrix, tournament, diagnostics))
    (out_dir / "assumptions_and_nonparity.md").write_text(render_nonparity_report(state, matrix))
    return matrix


def utility_backend_status(utility_root: Path | None) -> dict[str, str]:
    if utility_root is None or not utility_root.exists():
        return {}
    statuses: dict[str, str] = {}
    for manifest_path in utility_root.glob("*/utility_manifest.json"):
        try:
            data = json.loads(manifest_path.read_text())
        except Exception:
            continue
        utility = str(data.get("utility") or manifest_path.parent.name)
        backend = data.get("backend") if isinstance(data.get("backend"), dict) else {}
        status = str(backend.get("status") or "unknown")
        selected = str(backend.get("selected") or "unknown")
        if status == "adapter_backed":
            statuses[utility] = f"optional_utility_adapter_backed_{selected}"
        elif status == "available":
            statuses[utility] = "optional_utility_stdlib"
        else:
            statuses[utility] = f"optional_utility_{status}"
    return statuses


def render_parity_report(
    state: dict[str, Any],
    matrix: dict[str, Any],
    tournament: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    rows = [
        [
            row["surface"],
            row["current_status"],
            ", ".join(row["required_artifacts"]),
            row["bio_add_on"],
        ]
        for row in matrix["rows"]
    ]
    selected = tournament.get("selected_design_id") if tournament else "not_run"
    rank = diagnostics.get("rank") if diagnostics else "not_available"
    term_count = diagnostics.get("model_term_count") if diagnostics else "not_available"
    return (
        "# reference DOE Comparable Parity Report\n\n"
        f"- Campaign: {state.get('campaign_id')}\n"
        f"- Selected design: {selected}\n"
        f"- Model rank / terms: {rank} / {term_count}\n"
        "- Claim policy: exact, adapter, approximate, and heuristic metrics are labeled separately.\n\n"
        + markdown_table(["reference DOE surface", "Current BioSymphony status", "Artifacts", "BioSymphony add-on"], rows)
        + "\n"
    )


def render_nonparity_report(state: dict[str, Any], matrix: dict[str, Any]) -> str:
    optional = [row for row in matrix["rows"] if "planned" in row["current_status"] or "optional" in row["current_status"]]
    rows = [[row["surface"], row["current_status"], row["target_status"]] for row in optional]
    return (
        "# Assumptions And Non-Parity\n\n"
        f"- Campaign: {state.get('campaign_id')}\n"
        "- BioSymphony Ferm DoE is local-first and does not require reference DOE.\n"
        "- Optional Bayesian dependencies remain behind extras and are not required for dossier generation.\n"
        "- Public starter examples are planning fixtures, not private lab-ready process records.\n"
        "- No Linear API calls or RunPod resources are launched by this engine.\n\n"
        "## Explicit Non-Parity Or Optional Areas\n\n"
        + markdown_table(["Surface", "Current status", "Target status"], rows)
        + "\n"
    )
