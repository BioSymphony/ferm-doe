"""Optional response profiler utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constraints import design_factors
from ..doe import halton_design
from ..io_utils import markdown_table, parse_number, read_csv, write_csv, write_json
from ..model_matrix import build_model_matrix, cross_product, diagnose_design, invert_matrix, matrix_rank
from .common import utility_manifest


def run_profiler_utility(
    campaign_state_path: Path,
    results_csv: Path,
    out_dir: Path,
    backend: str | None = None,
    grid_size: int = 64,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    from ..io_utils import load_json

    state = load_json(campaign_state_path)
    rows, _ = read_csv(results_csv)
    factors = design_factors(state.get("factors", []))
    response_id = state.get("objective", {}).get("response_id")
    model_spec = state.get("model_terms", {})
    training_rows = [row for row in rows if parse_number(row.get(response_id)) is not None] if response_id else []
    if len(training_rows) < max(3, min(6, len(factors) + 1)):
        result = insufficient_profile(state, response_id, len(training_rows))
        write_json(out_dir / "profiler.json", result)
        write_csv(out_dir / "prediction_grid.csv", [], ["run_id"] + [factor["factor_id"] for factor in factors] + ["predicted_response"])
        write_csv(out_dir / "operating_window.csv", [], ["run_id", "predicted_response", "boundary_warning"])
        (out_dir / "profiler_report.md").write_text(render_profiler_report(result))
        utility_manifest(
            utility="profiler",
            out_dir=out_dir,
            inputs={"campaign_state": str(campaign_state_path), "results": str(results_csv)},
            backend=backend or state.get("design_policy", {}).get("utility_backend"),
            artifacts=["profiler.json", "prediction_grid.csv", "operating_window.csv", "profiler_report.md"],
            metric_labels={"model_fit": "unavailable_insufficient_data"},
            caveats=result["warnings"],
        )
        return result

    fit = fit_response_model(training_rows, factors, response_id, model_spec)
    grid = halton_design(factors, max(8, grid_size))
    predictions = predict_rows(grid, factors, model_spec, fit)
    direction = state.get("objective", {}).get("direction", "maximize")
    reverse = direction != "minimize"
    predictions.sort(key=lambda row: row["predicted_response"], reverse=reverse)
    operating = predictions[: min(12, len(predictions))]
    warnings = boundary_warnings(operating, factors)
    result = {
        "schema_version": 1,
        "utility_result_kind": "profiler",
        "campaign_id": state.get("campaign_id"),
        "response_id": response_id,
        "training_rows": len(training_rows),
        "model": fit,
        "best_predicted_run": operating[0] if operating else {},
        "boundary_warnings": warnings,
        "operating_window_count": len(operating),
    }
    write_json(out_dir / "profiler.json", result)
    headers = ["run_id"] + [factor["factor_id"] for factor in factors] + ["predicted_response", "prediction_label"]
    write_csv(out_dir / "prediction_grid.csv", predictions, headers)
    write_csv(out_dir / "operating_window.csv", operating, headers + ["boundary_warning"])
    (out_dir / "profiler_report.md").write_text(render_profiler_report(result))
    utility_manifest(
        utility="profiler",
        out_dir=out_dir,
        inputs={"campaign_state": str(campaign_state_path), "results": str(results_csv)},
        backend=backend or state.get("design_policy", {}).get("utility_backend"),
        artifacts=["profiler.json", "prediction_grid.csv", "operating_window.csv", "profiler_report.md"],
        metric_labels={"model_fit": fit["label"], "prediction": "stdlib_ridge_linear_model"},
        caveats=warnings or ["Profiler is a local model over available results, not a mechanistic simulator."],
    )
    return result


def fit_response_model(
    rows: list[dict[str, str]],
    factors: list[dict[str, Any]],
    response_id: str,
    model_spec: dict[str, Any],
) -> dict[str, Any]:
    matrix_bundle = build_model_matrix(rows, factors, model_spec)
    matrix = matrix_bundle["matrix"]
    y = [float(parse_number(row.get(response_id)) or 0.0) for row in rows]
    xtx = cross_product(matrix)
    ridge = [line[:] for line in xtx]
    for index in range(len(ridge)):
        ridge[index][index] += 1e-6
    inverse = invert_matrix(ridge) or []
    xty = [sum(matrix[row_index][col] * y[row_index] for row_index in range(len(matrix))) for col in range(len(matrix[0]))]
    coefficients = [sum(inverse[row][col] * xty[col] for col in range(len(xty))) for row in range(len(inverse))] if inverse else [0.0] * len(matrix_bundle["columns"])
    fitted = [sum(row[col] * coefficients[col] for col in range(len(coefficients))) for row in matrix]
    mean = sum(y) / len(y)
    sst = sum((value - mean) ** 2 for value in y)
    sse = sum((value - pred) ** 2 for value, pred in zip(y, fitted))
    r2 = 1.0 - (sse / sst) if sst > 1e-12 else 0.0
    diagnostics = diagnose_design(rows, factors, [], model_spec)
    return {
        "label": "stdlib_ridge_least_squares",
        "columns": matrix_bundle["columns"],
        "coefficients": {column: round(coefficients[index], 6) for index, column in enumerate(matrix_bundle["columns"])},
        "rank": matrix_rank(matrix),
        "r2_training": round(max(0.0, min(1.0, r2)), 4),
        "design_diagnostics": diagnostics,
    }


def predict_rows(
    rows: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    model_spec: dict[str, Any],
    fit: dict[str, Any],
) -> list[dict[str, Any]]:
    matrix_bundle = build_model_matrix(rows, factors, model_spec)
    coefficients = fit.get("coefficients", {})
    output = []
    for row, vector in zip(rows, matrix_bundle["matrix"]):
        prediction = 0.0
        for index, column in enumerate(matrix_bundle["columns"]):
            prediction += float(coefficients.get(column, 0.0)) * vector[index]
        output_row = dict(row)
        output_row["predicted_response"] = round(prediction, 6)
        output_row["prediction_label"] = "stdlib_ridge_linear_model"
        output.append(output_row)
    return output


def boundary_warnings(rows: list[dict[str, Any]], factors: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for row in rows[:5]:
        boundary = []
        for factor in factors:
            low = factor.get("min")
            high = factor.get("max")
            value = parse_number(row.get(factor["factor_id"]))
            if low is None or high is None or value is None:
                continue
            span = float(high) - float(low)
            if span <= 0:
                continue
            if abs(value - float(low)) <= 0.05 * span:
                boundary.append(f"{factor['factor_id']} near min")
            if abs(value - float(high)) <= 0.05 * span:
                boundary.append(f"{factor['factor_id']} near max")
        row["boundary_warning"] = "; ".join(boundary)
        if boundary:
            warnings.append(f"{row.get('run_id')} predicted optimum is on boundary: {', '.join(boundary)}")
    return warnings


def insufficient_profile(state: dict[str, Any], response_id: str | None, count: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "utility_result_kind": "profiler",
        "campaign_id": state.get("campaign_id"),
        "response_id": response_id,
        "training_rows": count,
        "model": {"label": "unavailable_insufficient_data"},
        "best_predicted_run": {},
        "boundary_warnings": [],
        "operating_window_count": 0,
        "warnings": ["Not enough numeric result rows to fit a profiler model."],
    }


def render_profiler_report(result: dict[str, Any]) -> str:
    best = result.get("best_predicted_run", {})
    warning_rows = [[item] for item in result.get("boundary_warnings", [])]
    return (
        "# Profiler Report\n\n"
        f"- Campaign: {result.get('campaign_id')}\n"
        f"- Response: {result.get('response_id')}\n"
        f"- Training rows: {result.get('training_rows')}\n"
        f"- Model: {result.get('model', {}).get('label')}\n"
        f"- Best predicted run: {best.get('run_id', '')}\n"
        f"- Best predicted response: {best.get('predicted_response', '')}\n\n"
        "## Boundary Warnings\n\n"
        + markdown_table(["Warning"], warning_rows)
        + "\n"
    )
