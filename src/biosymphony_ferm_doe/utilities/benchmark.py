"""Synthetic reference DOE benchmark harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..compiler import compile_campaign_state
from ..constraints import validate_design_rows
from ..doe import mixture_simplex_design, propose_candidate_designs
from ..io_utils import markdown_table, write_csv, write_json
from .common import utility_manifest
from .custom_optimal import run_custom_optimal_utility


def run_benchmark_doe_utility(
    manifest_path: Path,
    out_dir: Path,
    backend: str | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = compile_campaign_state(manifest_path)
    checks: list[dict[str, Any]] = []
    designs = propose_candidate_designs(manifest_path, state, run_budget=12)
    by_id = {candidate["design_id"]: candidate for candidate in designs["candidates"]}
    checks.append(_check("full_factorial_present", "full_factorial" in by_id, "Full factorial candidate exists."))
    checks.append(_check("pb_shape", len(by_id.get("plackett_burman", {}).get("rows", [])) % 4 == 0, "PB-like design uses run count divisible by 4."))
    checks.append(_check("dsd_present", "definitive_screening_like" in by_id, "DSD-like design exists."))
    custom = by_id.get("custom_optimal", {})
    checks.append(_check("custom_constraints", not custom.get("diagnostics", {}).get("constraint_violations"), "Custom optimal respects explicit constraints."))
    checks.append(_check("rank_reported", custom.get("diagnostics", {}).get("rank") is not None, "Rank is reported."))
    checks.append(_check("estimability_reported", "estimability" in custom.get("diagnostics", {}), "Estimability is reported."))

    mixture_factors = [
        {"factor_id": "a", "type": "mixture", "min": 0, "max": 1, "mixture_group": "m"},
        {"factor_id": "b", "type": "mixture", "min": 0, "max": 1, "mixture_group": "m"},
        {"factor_id": "c", "type": "mixture", "min": 0, "max": 1, "mixture_group": "m"},
    ]
    mixture_rows = mixture_simplex_design(mixture_factors, 8)
    mixture_ok = all(abs(sum(float(row[factor["factor_id"]]) for factor in mixture_factors) - 1.0) <= 1e-6 for row in mixture_rows)
    checks.append(_check("mixture_sum", mixture_ok, "Mixture rows sum to one."))

    fixed_path = out_dir / "fixed_rows.csv"
    if custom.get("rows"):
        fixed = custom["rows"][0]
        write_csv(fixed_path, [fixed], ["run_id"] + [factor["factor_id"] for factor in state.get("factors", [])])
        first = run_custom_optimal_utility(manifest_path, out_dir / "custom_optimal_first", run_budget=8, fixed_runs_path=fixed_path)
        second = run_custom_optimal_utility(manifest_path, out_dir / "custom_optimal_second", run_budget=8, fixed_runs_path=fixed_path)
        checks.append(_check("deterministic_custom_optimal", first["rows"] == second["rows"], "Custom-optimal utility is deterministic."))
        fixed_key = _key(fixed, state.get("factors", []))
        selected_keys = {_key(row, state.get("factors", [])) for row in first["rows"]}
        checks.append(_check("fixed_row_preserved", fixed_key in selected_keys, "Fixed row is preserved."))
        required_files = ["custom_optimal_design.csv", "candidate_set.csv", "model_matrix.csv", "optimality_trace.json", "custom_optimal.scorecard.json", "utility_manifest.json"]
        checks.append(_check("utility_artifacts_complete", all((out_dir / "custom_optimal_first" / name).exists() for name in required_files), "Custom-optimal utility artifacts exist."))
    else:
        checks.append(_check("deterministic_custom_optimal", False, "No custom-optimal rows were available."))
        checks.append(_check("fixed_row_preserved", False, "No custom-optimal rows were available."))
        checks.append(_check("utility_artifacts_complete", False, "No custom-optimal rows were available."))

    if custom.get("rows"):
        checks.append(_check("row_validation", not validate_design_rows(custom["rows"], state.get("factors", []), state.get("constraints", [])), "Selected custom rows validate."))
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    result = {
        "schema_version": 1,
        "utility_result_kind": "doe_benchmark",
        "campaign_id": state.get("campaign_id"),
        "status": status,
        "checks": checks,
    }
    write_json(out_dir / "doe_benchmark_results.json", result)
    (out_dir / "doe_benchmark_report.md").write_text(render_benchmark_report(result))
    utility_manifest(
        utility="benchmark-doe",
        out_dir=out_dir,
        inputs={"manifest": str(manifest_path)},
        backend=backend or state.get("design_policy", {}).get("utility_backend"),
        artifacts=["doe_benchmark_results.json", "doe_benchmark_report.md"],
        metric_labels={"benchmark": "synthetic_property_harness"},
        caveats=["Benchmark checks local design properties; it does not compare against proprietary vendor output."],
    )
    return result


def render_benchmark_report(result: dict[str, Any]) -> str:
    rows = [[item["check"], item["status"], item["message"]] for item in result.get("checks", [])]
    return (
        "# Reference DOE Benchmark Report\n\n"
        f"- Campaign: {result.get('campaign_id')}\n"
        f"- Status: {result.get('status')}\n\n"
        + markdown_table(["Check", "Status", "Message"], rows)
        + "\n"
    )


def _check(check: str, passed: bool, message: str) -> dict[str, str]:
    return {"check": check, "status": "PASS" if passed else "FAIL", "message": message}


def _key(row: dict[str, Any], factors: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(row.get(factor["factor_id"], "")) for factor in factors)
