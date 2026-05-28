#!/usr/bin/env python3
"""Generate deterministic baseline BioSymphony Ferm DoE dossier files.

This script intentionally uses only the Python standard library so it can run
in a local checkout, inside a Symphony worker, or in a minimal container.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DOSSIER_FILES = [
    "data_trust_report.md",
    "factor_space_audit.md",
    "model_summary.md",
    "provenance.md",
    "readiness_verdict.md",
]


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    return data


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ValueError(f"ledger has no header row: {path}")
    return rows, headers


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float | int | None) -> str:
    if value is None:
        return "missing"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["None recorded" for _ in headers]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def resolve_optional_path(raw_path: str, manifest_path: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    return manifest_path.parent / candidate


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def find_manifest_ledger(manifest: dict[str, Any], manifest_path: Path) -> Path | None:
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list):
        return None

    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip().endswith(".csv"):
            continue
        text = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower()
        if "ledger" in text or "run" in text:
            preferred.append(item)
        else:
            fallback.append(item)

    for item in preferred + fallback:
        path = resolve_optional_path(str(item["path"]), manifest_path)
        if path.exists():
            return path
    return None


def require_list(manifest: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = manifest.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def objective_response(manifest: dict[str, Any]) -> tuple[str, str]:
    objective = manifest.get("objective", {})
    response_id = ""
    direction = "maximize"
    if isinstance(objective, dict):
        response_id = str(objective.get("response_id", "")).strip()
        direction = str(objective.get("direction", "maximize")).strip().lower() or "maximize"

    if not response_id:
        responses = require_list(manifest, "responses")
        if responses:
            response_id = str(responses[0].get("response_id", "")).strip()
            direction = str(responses[0].get("direction", direction)).strip().lower() or direction
    return response_id, direction


def response_label(manifest: dict[str, Any], response_id: str) -> str:
    for response in require_list(manifest, "responses"):
        if response.get("response_id") == response_id:
            name = str(response.get("name", response_id)).strip() or response_id
            unit = str(response.get("unit", "")).strip()
            return f"{name} ({unit})" if unit else name
    return response_id


def factor_rows(manifest: dict[str, Any], ledger_rows: list[dict[str, str]]) -> tuple[list[list[str]], list[str]]:
    rows: list[list[str]] = []
    warnings: list[str] = []
    for factor in require_list(manifest, "factors"):
        factor_id = str(factor.get("factor_id", "")).strip()
        if not factor_id:
            continue
        observed = [parse_number(row.get(factor_id)) for row in ledger_rows]
        observed_numbers = [value for value in observed if value is not None]
        manifest_min = parse_number(factor.get("min"))
        manifest_max = parse_number(factor.get("max"))
        out_of_range = 0
        if observed_numbers and (manifest_min is not None or manifest_max is not None):
            for value in observed_numbers:
                if manifest_min is not None and value < manifest_min:
                    out_of_range += 1
                elif manifest_max is not None and value > manifest_max:
                    out_of_range += 1

        missing = len(ledger_rows) - len(observed_numbers)
        if missing:
            warnings.append(f"{factor_id} has {missing} missing ledger values.")
        if out_of_range:
            warnings.append(f"{factor_id} has {out_of_range} values outside manifest bounds.")

        rows.append(
            [
                factor_id,
                str(factor.get("name", factor_id)),
                str(factor.get("unit", "")),
                f"{format_number(manifest_min)} to {format_number(manifest_max)}",
                (
                    f"{format_number(min(observed_numbers))} to {format_number(max(observed_numbers))}"
                    if observed_numbers
                    else "missing"
                ),
                str(missing),
                str(out_of_range),
            ]
        )
    return rows, warnings


def numeric_summary(rows: list[dict[str, str]], column: str) -> dict[str, float | int | None]:
    values = [parse_number(row.get(column)) for row in rows]
    numbers = [value for value in values if value is not None]
    if not numbers:
        return {"count": 0, "min": None, "mean": None, "max": None}
    return {
        "count": len(numbers),
        "min": min(numbers),
        "mean": statistics.fmean(numbers),
        "max": max(numbers),
    }


def top_response_row(
    rows: list[dict[str, str]], response_id: str, direction: str
) -> tuple[dict[str, str] | None, float | None]:
    candidates: list[tuple[float, dict[str, str]]] = []
    for row in rows:
        value = parse_number(row.get(response_id))
        if value is not None:
            candidates.append((value, row))
    if not candidates:
        return None, None
    reverse = direction != "minimize"
    value, row = sorted(candidates, key=lambda item: item[0], reverse=reverse)[0]
    return row, value


def trust_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    status_counts = Counter((row.get("inclusion_status") or "missing").strip() or "missing" for row in rows)
    source_counts = Counter((row.get("source_type") or "missing").strip() or "missing" for row in rows)
    trust_values = [parse_number(row.get("trust_score")) for row in rows]
    trust_numbers = [value for value in trust_values if value is not None]
    excluded = sum(count for status, count in status_counts.items() if status.lower() in {"excluded", "reject", "rejected"})
    low_trust = sum(1 for value in trust_numbers if value < 0.6)
    missing_trust = len(rows) - len(trust_numbers)
    average = statistics.fmean(trust_numbers) if trust_numbers else None

    if not rows:
        status = "RED"
        rationale = "No ledger rows were available."
    elif excluded or missing_trust or low_trust or average is None or average < 0.6:
        status = "YELLOW"
        rationale = "Some rows need trust-score or inclusion review before model use."
    else:
        status = "GREEN"
        rationale = "All rows have usable trust scores and no excluded status was detected."

    return {
        "status": status,
        "rationale": rationale,
        "status_counts": status_counts,
        "source_counts": source_counts,
        "average": average,
        "minimum": min(trust_numbers) if trust_numbers else None,
        "maximum": max(trust_numbers) if trust_numbers else None,
        "missing": missing_trust,
        "low_trust": low_trust,
        "excluded": excluded,
    }


def readiness_status(
    manifest: dict[str, Any],
    rows: list[dict[str, str]],
    response_id: str,
    response_stats: dict[str, float | int | None],
    factor_warnings: list[str],
    trust: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    target = str(manifest.get("readiness_target", "YELLOW")).strip().upper() or "YELLOW"
    blockers: list[str] = []
    cautions: list[str] = []

    if not rows:
        blockers.append("Run ledger has no data rows.")
    if not response_id:
        blockers.append("No objective response_id is defined.")
    elif response_stats["count"] == 0:
        blockers.append(f"Objective response column has no numeric values: {response_id}.")
    if not require_list(manifest, "factors"):
        blockers.append("Manifest defines no factors.")
    if factor_warnings:
        cautions.extend(factor_warnings)
    if trust["status"] != "GREEN":
        cautions.append(str(trust["rationale"]))
    if any("demo" in str(constraint.get("constraint_id", "")).lower() for constraint in require_list(manifest, "constraints")):
        cautions.append("Manifest includes a demo-only constraint; do not treat this as a lab-ready packet.")

    if blockers:
        status = "RED"
    elif target == "GREEN" and cautions:
        status = "YELLOW"
    elif target in {"GREEN", "YELLOW", "RED"}:
        status = target
    else:
        status = "YELLOW"
        cautions.append(f"Unrecognized readiness_target {target!r}; defaulted to YELLOW.")
    return status, blockers, cautions


def write_data_trust_report(output_dir: Path, rows: list[dict[str, str]], trust: dict[str, Any]) -> None:
    status_rows = [[key, str(trust["status_counts"][key])] for key in sorted(trust["status_counts"])]
    source_rows = [[key, str(trust["source_counts"][key])] for key in sorted(trust["source_counts"])]
    text = f"""# Data Trust Report

Trust status: `{trust["status"]}`

{trust["rationale"]}

## Ledger Coverage

- Run count: {len(rows)}
- Average trust score: {format_number(trust["average"])}
- Trust score range: {format_number(trust["minimum"])} to {format_number(trust["maximum"])}
- Missing trust scores: {trust["missing"]}
- Low-trust rows below 0.6: {trust["low_trust"]}
- Excluded rows: {trust["excluded"]}

## Inclusion Status Counts

{markdown_table(["Status", "Rows"], status_rows)}

## Source Type Counts

{markdown_table(["Source type", "Rows"], source_rows)}
"""
    (output_dir / "data_trust_report.md").write_text(text)


def write_factor_space_audit(output_dir: Path, factor_rows_data: list[list[str]], warnings: list[str]) -> None:
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- No factor range warnings detected."
    text = f"""# Factor Space Audit

## Factor Ranges

{markdown_table(["Factor", "Name", "Unit", "Manifest range", "Observed range", "Missing", "Out of range"], factor_rows_data)}

## Warnings

{warning_lines}
"""
    (output_dir / "factor_space_audit.md").write_text(text)


def write_model_summary(
    output_dir: Path,
    manifest: dict[str, Any],
    rows: list[dict[str, str]],
    response_id: str,
    direction: str,
    response_stats: dict[str, float | int | None],
    top_row: dict[str, str] | None,
    top_value: float | None,
) -> None:
    response_name = response_label(manifest, response_id)
    top_lines = ["- Top run: missing", "- Top response: missing"]
    if top_row is not None:
        top_lines = [
            f"- Top run: `{top_row.get('run_id', 'missing')}`",
            f"- Source run: `{top_row.get('source_run_id', 'missing')}`",
            f"- Top response: {format_number(top_value)}",
        ]

    text = f"""# Model Summary

This baseline dossier does not fit a predictive model. It reports deterministic descriptive statistics suitable for readiness review.

## Objective Response

- Response: `{response_id}` ({response_name})
- Direction: `{direction}`
- Numeric observations: {response_stats["count"]} of {len(rows)}
- Response range: {format_number(response_stats["min"])} to {format_number(response_stats["max"])}
- Response mean: {format_number(response_stats["mean"])}

## Best Observed Run

{chr(10).join(top_lines)}

## Modeling Readiness

- Use these summaries to check whether the ledger is worth a follow-on design or model-selection issue.
- Do not treat the best observed row as an experimental recommendation without assay, equipment, organism, and safety review.
"""
    (output_dir / "model_summary.md").write_text(text)


def write_provenance(output_dir: Path, manifest: dict[str, Any], manifest_path: Path, ledger_path: Path) -> None:
    source_rows = []
    for source in require_list(manifest, "sources"):
        source_rows.append(
            [
                str(source.get("source_id", "missing")),
                str(source.get("title", "missing")),
                str(source.get("year", "missing")),
                str(source.get("license", "missing")),
                str(source.get("doi", source.get("url", "missing"))),
            ]
        )

    input_rows = []
    for item in require_list(manifest, "inputs"):
        input_rows.append(
            [
                str(item.get("input_id", "missing")),
                str(item.get("kind", "missing")),
                str(item.get("path", "missing")),
            ]
        )

    constraint_lines = "\n".join(
        f"- `{constraint.get('constraint_id', 'missing')}`: {constraint.get('description', 'missing')}"
        for constraint in require_list(manifest, "constraints")
    )
    if not constraint_lines:
        constraint_lines = "- None recorded."

    text = f"""# Provenance

## Campaign

- Campaign ID: `{manifest.get("campaign_id", "missing")}`
- Name: {manifest.get("name", "missing")}
- Manifest: `{display_path(manifest_path)}`
- Ledger: `{display_path(ledger_path)}`
- Generator: `skills/biosymphony-ferm-doe/scripts/dossier_generate.py`

## Sources

{markdown_table(["Source ID", "Title", "Year", "License", "DOI or URL"], source_rows)}

## Inputs

{markdown_table(["Input ID", "Kind", "Path"], input_rows)}

## Constraints

{constraint_lines}
"""
    (output_dir / "provenance.md").write_text(text)


def write_readiness_verdict(
    output_dir: Path,
    status: str,
    blockers: list[str],
    cautions: list[str],
    trust: dict[str, Any],
    run_count: int,
    top_row: dict[str, str] | None,
    top_value: float | None,
) -> None:
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers) if blockers else "- No hard blockers detected."
    caution_lines = "\n".join(f"- {caution}" for caution in cautions) if cautions else "- No caution items detected."
    top_run = top_row.get("run_id", "missing") if top_row else "missing"
    top_response = format_number(top_value) if top_value is not None else "missing"
    text = f"""# Readiness Verdict

Status: `{status}`

## Summary

- Run count: {run_count}
- Top observed run: `{top_run}`
- Top observed response: {top_response}
- Trust status: `{trust["status"]}`

## Blockers

{blocker_lines}

## Cautions

{caution_lines}

## Decision

This dossier is suitable for a deterministic readiness pass campaign review. Physical execution still requires a lab-specific packet, assay readiness review, equipment feasibility check, and safety review.
"""
    (output_dir / "readiness_verdict.md").write_text(text)


def generate_dossier(manifest_path: Path, ledger_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = load_json_object(manifest_path)
    rows, _headers = load_csv_rows(ledger_path)
    response_id, direction = objective_response(manifest)
    response_stats = numeric_summary(rows, response_id) if response_id else {"count": 0, "min": None, "mean": None, "max": None}
    top_row, top_value = top_response_row(rows, response_id, direction) if response_id else (None, None)
    factor_rows_data, factor_warnings = factor_rows(manifest, rows)
    trust = trust_summary(rows)
    status, blockers, cautions = readiness_status(manifest, rows, response_id, response_stats, factor_warnings, trust)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_data_trust_report(output_dir, rows, trust)
    write_factor_space_audit(output_dir, factor_rows_data, factor_warnings)
    write_model_summary(output_dir, manifest, rows, response_id, direction, response_stats, top_row, top_value)
    write_provenance(output_dir, manifest, manifest_path, ledger_path)
    write_readiness_verdict(output_dir, status, blockers, cautions, trust, len(rows), top_row, top_value)

    return {
        "status": status,
        "run_count": len(rows),
        "response_id": response_id,
        "top_run": top_row.get("run_id") if top_row else None,
        "top_response": top_value,
        "trust_status": trust["status"],
        "output_dir": str(output_dir),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an ferm-doe-dossier from a campaign manifest and CSV ledger.")
    parser.add_argument("--manifest", required=True, type=Path, help="Path to campaign_manifest.json")
    parser.add_argument(
        "--ledger",
        type=Path,
        help="Path to historical run ledger CSV. If omitted, the first ledger-like CSV input in the manifest is used.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ferm-doe-dossier"),
        help="Directory to write dossier Markdown files. Defaults to ./ferm-doe-dossier.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest_path = args.manifest
    if not manifest_path.exists():
        print(f"ERROR: manifest does not exist: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_json_object(manifest_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ledger_path = args.ledger
    if ledger_path is None:
        ledger_path = find_manifest_ledger(manifest, manifest_path)
        if ledger_path is None:
            print("ERROR: could not infer ledger path from manifest; pass --ledger", file=sys.stderr)
            return 2
    if not ledger_path.exists():
        print(f"ERROR: ledger does not exist: {ledger_path}", file=sys.stderr)
        return 2

    try:
        summary = generate_dossier(manifest_path, ledger_path, args.output)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: wrote {summary['output_dir']}")
    print(f"status={summary['status']}")
    print(f"run_count={summary['run_count']}")
    print(f"response_id={summary['response_id']}")
    print(f"top_run={summary['top_run']}")
    print(f"top_response={format_number(summary['top_response'])}")
    print(f"trust_status={summary['trust_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
