"""Validate lightweight Frictionless-compatible CSV table contracts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_SCHEMA_DIR = Path("schemas/tables")


@dataclass(frozen=True)
class TableFinding:
    severity: str
    schema: str
    path: str
    message: str
    row_number: int | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_table_contracts(schema_dir: Path, root: Path) -> dict[str, Any]:
    schemas = load_table_schemas(schema_dir)
    findings: list[TableFinding] = []
    checked_files = 0
    checked_schemas = 0

    for schema_path, schema in schemas:
        checked_schemas += 1
        schema_name = str(schema.get("name") or schema_path.stem.removesuffix(".schema"))
        targets = schema.get("x-biosymphony", {}).get("targets", [])
        if not isinstance(targets, list) or not targets:
            findings.append(
                TableFinding(
                    "warning",
                    schema_name,
                    relative(schema_path, root),
                    "schema has no x-biosymphony.targets entries",
                )
            )
            continue
        matched = expand_targets(root, targets)
        if not matched:
            findings.append(
                TableFinding(
                    "warning",
                    schema_name,
                    relative(schema_path, root),
                    "no files matched schema targets",
                )
            )
            continue
        for table_path in matched:
            checked_files += 1
            findings.extend(validate_csv_against_schema(table_path, schema, root=root, schema_name=schema_name))

    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    return {
        "schema_version": 1,
        "contract_kind": "biosymphony_table_contract_report",
        "schema_dir": str(schema_dir),
        "root": str(root),
        "status": "FAIL" if errors else "PASS",
        "checked_schemas": checked_schemas,
        "checked_files": checked_files,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [finding.to_dict() for finding in findings],
    }


def load_table_schemas(schema_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not schema_dir.exists():
        return []
    schemas: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(schema_dir.glob("*.schema.json")):
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            schemas.append((path, data))
    return schemas


def expand_targets(root: Path, targets: list[Any]) -> list[Path]:
    matched: list[Path] = []
    for raw in targets:
        pattern = str(raw)
        for path in root.glob(pattern):
            if path.is_file() and path not in matched:
                matched.append(path)
    return sorted(matched)


def validate_csv_against_schema(
    path: Path,
    schema: dict[str, Any],
    *,
    root: Path,
    schema_name: str,
) -> list[TableFinding]:
    findings: list[TableFinding] = []
    try:
        rows, headers, duplicate_headers = read_csv_rows(path)
    except Exception as exc:
        return [
            TableFinding(
                "error",
                schema_name,
                relative(path, root),
                f"could not read CSV: {type(exc).__name__}: {exc}",
            )
        ]

    path_label = relative(path, root)
    if duplicate_headers:
        findings.append(
            TableFinding(
                "error",
                schema_name,
                path_label,
                "duplicate header(s): " + ", ".join(sorted(duplicate_headers)),
            )
        )

    field_specs = schema.get("fields", [])
    if not isinstance(field_specs, list):
        field_specs = []
    fields = {str(field.get("name")): field for field in field_specs if isinstance(field, dict) and field.get("name")}
    required = [
        name
        for name, field in fields.items()
        if isinstance(field.get("constraints"), dict) and bool(field["constraints"].get("required"))
    ]
    missing = [name for name in required if name not in headers]
    for field_name in missing:
        findings.append(
            TableFinding(
                "error",
                schema_name,
                path_label,
                f"missing required field: {field_name}",
                field=field_name,
            )
        )

    extra = schema.get("x-biosymphony", {})
    for group in extra.get("requiredAny", []) if isinstance(extra, dict) else []:
        if not isinstance(group, dict):
            continue
        choices = [str(item) for item in group.get("fields", [])]
        if choices and not any(choice in headers for choice in choices):
            findings.append(
                TableFinding(
                    "error",
                    schema_name,
                    path_label,
                    str(group.get("message") or "missing one required alternate field group"),
                )
            )

    primary_key = primary_key_fields(schema.get("primaryKey"))
    if primary_key:
        missing_pk = [field_name for field_name in primary_key if field_name not in headers]
        for field_name in missing_pk:
            findings.append(
                TableFinding(
                    "error",
                    schema_name,
                    path_label,
                    f"primaryKey field is missing: {field_name}",
                    field=field_name,
                )
            )
        if not missing_pk:
            seen: dict[tuple[str, ...], int] = {}
            for row_number, row in enumerate(rows, start=2):
                key = tuple(row.get(field_name, "") for field_name in primary_key)
                if any(value == "" for value in key):
                    continue
                if key in seen:
                    findings.append(
                        TableFinding(
                            "error",
                            schema_name,
                            path_label,
                            "duplicate primaryKey value: " + "|".join(key),
                            row_number,
                            ",".join(primary_key),
                        )
                    )
                else:
                    seen[key] = row_number

    for row_number, row in enumerate(rows, start=2):
        for field_name, field in fields.items():
            if field_name not in headers:
                continue
            value = row.get(field_name, "")
            findings.extend(validate_value(value, field, schema_name, path_label, row_number, field_name))
    return findings


def primary_key_fields(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str], set[str]]:
    with path.open(newline="") as handle:
        header_reader = csv.reader(handle)
        try:
            headers = next(header_reader)
        except StopIteration:
            return [], [], set()
        duplicate_headers = {name for name in headers if headers.count(name) > 1}
        handle.seek(0)
        reader = csv.DictReader(handle)
        rows = [{key: (value or "").strip() for key, value in row.items() if key is not None} for row in reader]
    return rows, list(reader.fieldnames or []), duplicate_headers


def validate_value(
    value: str,
    field: dict[str, Any],
    schema_name: str,
    path_label: str,
    row_number: int,
    field_name: str,
) -> list[TableFinding]:
    findings: list[TableFinding] = []
    constraints = field.get("constraints") if isinstance(field.get("constraints"), dict) else {}
    if constraints.get("required") and value == "":
        findings.append(TableFinding("error", schema_name, path_label, "required value is blank", row_number, field_name))
        return findings
    if value == "":
        return findings

    enum = constraints.get("enum")
    if isinstance(enum, list) and enum and value not in {str(item) for item in enum}:
        findings.append(
            TableFinding(
                "error",
                schema_name,
                path_label,
                "value is not in enum: " + ", ".join(str(item) for item in enum),
                row_number,
                field_name,
            )
        )

    field_type = str(field.get("type") or "string").lower()
    if field_type in {"number", "integer"}:
        try:
            number = float(value)
        except ValueError:
            findings.append(TableFinding("error", schema_name, path_label, "value is not numeric", row_number, field_name))
            return findings
        if field_type == "integer" and not number.is_integer():
            findings.append(TableFinding("error", schema_name, path_label, "value is not an integer", row_number, field_name))
        minimum = constraints.get("minimum")
        maximum = constraints.get("maximum")
        if minimum is not None and number < float(minimum):
            findings.append(TableFinding("error", schema_name, path_label, f"value is below minimum {minimum}", row_number, field_name))
        if maximum is not None and number > float(maximum):
            findings.append(TableFinding("error", schema_name, path_label, f"value is above maximum {maximum}", row_number, field_name))
    return findings


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate BioSymphony CSV table contracts.")
    parser.add_argument("--schema-dir", default=str(DEFAULT_SCHEMA_DIR))
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", help="Optional JSON report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    schema_dir = Path(args.schema_dir)
    if not schema_dir.is_absolute():
        schema_dir = root / schema_dir
    report = validate_table_contracts(schema_dir, root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
    print(json.dumps({"status": report["status"], "checked_files": report["checked_files"], "errors": report["error_count"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
