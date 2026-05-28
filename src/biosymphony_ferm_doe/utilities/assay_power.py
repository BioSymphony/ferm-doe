"""Optional assay-power utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..assay_power import evaluate_assay_power
from ..io_utils import load_json, read_csv, write_csv, write_json
from .common import utility_manifest


def run_assay_power_utility(
    campaign_state_path: Path,
    out_dir: Path,
    results_path: Path | None = None,
    backend: str | None = None,
    strict: bool | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_json(campaign_state_path)
    result_rows: list[dict[str, Any]] = []
    if results_path is not None:
        result_rows, _ = read_csv(results_path)
    assessment = evaluate_assay_power(state, result_rows, strict=strict)
    rows = []
    for item in assessment.get("items", []):
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        rows.append(
            {
                "response_id": item.get("response_id", ""),
                "status": item.get("status", ""),
                "score": item.get("score", ""),
                "requires_assay": item.get("requires_assay", ""),
                "power_proxy": metrics.get("power_proxy", ""),
                "target_power": metrics.get("target_power", ""),
                "replicate_count": metrics.get("replicate_count", ""),
                "cv_percent": metrics.get("cv_percent", ""),
                "loq": metrics.get("loq", ""),
                "matrix_recovery_min": metrics.get("matrix_recovery_min", ""),
            }
        )
    write_json(out_dir / "assay_power_results.json", assessment)
    write_csv(
        out_dir / "assay_power_summary.csv",
        rows,
        ["response_id", "status", "score", "requires_assay", "power_proxy", "target_power", "replicate_count", "cv_percent", "loq", "matrix_recovery_min"],
    )
    (out_dir / "assay_power_report.md").write_text(render_assay_power_report(assessment))
    utility_manifest(
        utility="assay-power",
        out_dir=out_dir,
        inputs={"campaign_state": str(campaign_state_path), "results": str(results_path) if results_path else ""},
        backend=backend,
        artifacts=["assay_power_results.json", "assay_power_summary.csv", "assay_power_report.md"],
        metric_labels={"power_proxy": "deterministic response-level assay-power proxy"},
        caveats=[
            "This utility checks response-level assay adequacy for planning; it is not a substitute for formal analytical-method validation.",
            "Derived cost, duration, and calculated productivity responses are marked not_applicable rather than assigned fake lab-assay requirements.",
        ],
    )
    return assessment


def render_assay_power_report(assessment: dict[str, Any]) -> str:
    lines = [
        "# Assay Power Assessment",
        "",
        f"- Campaign: {assessment.get('campaign_id')}",
        f"- Status: {assessment.get('status')}",
        f"- Score: {assessment.get('score')}",
        f"- Primary response: {assessment.get('primary_response_id')} ({assessment.get('primary_status')})",
        "",
        "## Responses",
        "",
    ]
    for item in assessment.get("items", []):
        issue_count = len(item.get("issues", [])) if isinstance(item.get("issues"), list) else 0
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        lines.append(
            f"- {item.get('response_id')}: {item.get('status')} "
            f"(score {item.get('score')}, power_proxy {metrics.get('power_proxy', '')}, issues {issue_count})"
        )
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "Planned follow-up decisions may use this assessment, but it does not validate optimization or scale transfer.",
            "",
        ]
    )
    return "\n".join(lines)
