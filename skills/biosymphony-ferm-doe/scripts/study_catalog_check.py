#!/usr/bin/env python3
"""Validate starter fermentation study catalogs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "study_id",
    "rank",
    "year",
    "title",
    "organism_or_system",
    "product",
    "problem_class",
    "method",
    "factors",
    "responses",
    "doi",
    "url",
    "license_status",
    "table_status",
    "recommended_goal_pack",
    "recommended_input_pack",
}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_catalog(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["top-level catalog must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not nonempty_string(data.get("catalog_id")):
        errors.append("catalog_id is required")

    studies = data.get("studies")
    if not isinstance(studies, list) or not studies:
        errors.append("studies must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    for index, study in enumerate(studies):
        prefix = f"studies[{index}]"
        if not isinstance(study, dict):
            errors.append(f"{prefix} must be an object")
            continue

        missing = sorted(REQUIRED_FIELDS - set(study))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")

        study_id = study.get("study_id")
        if not nonempty_string(study_id):
            errors.append(f"{prefix}.study_id is required")
        elif study_id in seen_ids:
            errors.append(f"{prefix}.study_id duplicates {study_id}")
        else:
            seen_ids.add(study_id)

        rank = study.get("rank")
        if not isinstance(rank, int) or rank < 1:
            errors.append(f"{prefix}.rank must be a positive integer")
        elif rank in seen_ranks:
            errors.append(f"{prefix}.rank duplicates {rank}")
        else:
            seen_ranks.add(rank)

        year = study.get("year")
        if not isinstance(year, int) or year < 1900 or year > 2100:
            errors.append(f"{prefix}.year must be a plausible integer year")

        for field in ["title", "organism_or_system", "product", "problem_class", "doi", "url"]:
            if field in study and not nonempty_string(study.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        for field in ["method", "factors", "responses"]:
            value = study.get(field)
            if not isinstance(value, list) or not value or not all(nonempty_string(item) for item in value):
                errors.append(f"{prefix}.{field} must be a non-empty list of strings")

        table_status = str(study.get("table_status", ""))
        license_status = str(study.get("license_status", "")).lower()
        if table_status.startswith("extract_ready") and not any(token in license_status for token in ["cc", "open"]):
            errors.append(f"{prefix} is extract-ready but license_status lacks open/CC signal")

    if seen_ranks and sorted(seen_ranks) != list(range(1, len(seen_ranks) + 1)):
        errors.append("ranks must be sequential from 1")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: study_catalog_check.py examples/starter-studies/study_catalog.json", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"ERROR: file does not exist: {path}", file=sys.stderr)
        return 2

    errors = check_catalog(path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

