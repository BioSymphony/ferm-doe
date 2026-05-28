"""Materialize structured manifest inputs without mutating source files."""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path
from typing import Any

from .io_utils import parse_number, resolve_path


MATERIALIZED_META_KEY = "_materialized_input"

SECTION_ID_KEYS = {
    "factors": ("factor_id", "id", "name"),
    "responses": ("response_id", "id", "name"),
    "constraints": ("constraint_id", "id", "name"),
}

CANONICAL_ALIASES = {
    "factors": {"id": "factor_id"},
    "responses": {"id": "response_id"},
    "constraints": {"id": "constraint_id", "constraint_type": "type"},
}


def materialize_manifest_inputs(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    """Load materializable manifest inputs into raw compiler sections.

    The function is read-only with respect to declared input files. It records
    parse/materialization problems in ``input_conflicts`` instead of raising for
    optional formats such as YAML when their parser is unavailable.
    """

    result: dict[str, Any] = {
        "factors": [],
        "responses": [],
        "constraints": [],
        "materialized_inputs": [],
        "input_conflicts": [],
    }
    inputs = _as_dict_list(manifest.get("inputs"))
    design_policy = manifest.get("design_policy") if isinstance(manifest.get("design_policy"), dict) else {}
    has_inline_factors = bool(_as_dict_list(manifest.get("factors")))

    for item in inputs:
        role = _input_role(item)
        if role not in {"factor_space", "constraint_set"}:
            continue
        summary = _base_summary(item, role)
        result["materialized_inputs"].append(summary)

        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            _record_issue(result, summary, "blocker", "missing_path", "Materialized input has no path.")
            continue
        path = resolve_path(raw_path, manifest_path.parent)
        summary["resolved_path"] = str(path) if path else ""
        if path is None or not path.exists():
            _record_issue(result, summary, "blocker", "missing_file", f"Materialized input file was not found: {raw_path}")
            continue

        summary["format"] = _format_for_path(path)
        data, issue = _load_structured_input(path)
        if issue is not None:
            _record_issue(result, summary, issue["severity"], issue["code"], issue["message"])
            continue

        if role == "factor_space":
            _materialize_factor_space(result, summary, data, design_policy, has_inline_factors)
        elif role == "constraint_set":
            _materialize_constraint_set(result, summary, data)

        if not summary["blockers"]:
            summary["status"] = "materialized" if _contributed_count(summary) else "loaded"

    return result


def merge_materialized_records(
    section: str,
    materialized_records: list[dict[str, Any]],
    inline_records: list[dict[str, Any]],
    input_conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge materialized records with manifest inline records.

    Manifest inline records win by stable identifier. Conflicting overlapping
    fields are recorded before the inline record replaces the materialized one.
    """

    merged: list[dict[str, Any]] = []
    index_by_id: dict[str, int] = {}

    for record in materialized_records:
        record_id = _record_id(record, section)
        if record_id and record_id in index_by_id:
            existing = merged[index_by_id[record_id]]
            input_conflicts.append(
                {
                    "section": section,
                    "record_id": record_id,
                    "severity": "warning",
                    "code": "duplicate_materialized_record",
                    "message": f"Multiple materialized {section} records share id {record_id}; first record is used.",
                    "resolution": "first_materialized_record_wins_until_manifest_override",
                    "input": _source_meta(record),
                    "existing_input": _source_meta(existing),
                }
            )
            continue
        if record_id:
            index_by_id[record_id] = len(merged)
        merged.append(record)

    for inline in inline_records:
        record_id = _record_id(inline, section)
        if record_id and record_id in index_by_id:
            previous = merged[index_by_id[record_id]]
            input_conflicts.extend(_record_conflicts(section, record_id, inline, previous))
            merged[index_by_id[record_id]] = inline
        else:
            if record_id:
                index_by_id[record_id] = len(merged)
            merged.append(inline)

    return [strip_materialization_metadata(record) for record in merged]


def materialization_missing_info(materialization: dict[str, Any]) -> list[dict[str, str]]:
    """Convert materialization warnings/blockers into compiler missing_info rows."""

    items: list[dict[str, str]] = []
    for issue in materialization.get("input_conflicts", []):
        if issue.get("severity") not in {"warning", "blocker"}:
            continue
        input_id = str(issue.get("input_id") or issue.get("input", {}).get("input_id") or "unknown")
        code = str(issue.get("code") or "materialization_issue")
        items.append(
            {
                "field": f"inputs:{input_id}:{code}",
                "severity": str(issue.get("severity")),
                "reason": str(issue.get("message") or issue.get("resolution") or "Input materialization issue."),
            }
        )
    return items


def strip_materialization_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != MATERIALIZED_META_KEY}


def _materialize_factor_space(
    result: dict[str, Any],
    summary: dict[str, Any],
    data: Any,
    design_policy: dict[str, Any],
    has_inline_factors: bool,
) -> None:
    factor_space = _coerce_factor_space(data)
    summary["factor_space"] = factor_space

    top_factors = _as_dict_list(factor_space.get("factors"))
    responses = _as_dict_list(factor_space.get("responses"))
    constraints = _as_dict_list(factor_space.get("constraints"))
    arms = _as_dict_list(factor_space.get("arms"))

    selected_factors = _select_executable_factors(
        result=result,
        summary=summary,
        top_factors=top_factors,
        arms=arms,
        design_policy=design_policy,
        has_inline_factors=has_inline_factors,
    )
    result["factors"].extend(_with_source(factor, summary, "factors") for factor in selected_factors)
    result["responses"].extend(_with_source(response, summary, "responses") for response in responses)
    result["constraints"].extend(_with_source(constraint, summary, "constraints") for constraint in constraints)

    summary["materialized_counts"]["factor_spaces"] = 1
    summary["materialized_counts"]["factors"] = len(selected_factors)
    summary["materialized_counts"]["responses"] = len(responses)
    summary["materialized_counts"]["constraints"] = len(constraints)


def _materialize_constraint_set(result: dict[str, Any], summary: dict[str, Any], data: Any) -> None:
    if isinstance(data, list):
        constraints = _as_dict_list(data)
        constraint_set = {"constraints": constraints}
    elif isinstance(data, dict):
        constraints = _as_dict_list(data.get("constraints"))
        if not constraints and _record_id(data, "constraints"):
            constraints = [data]
        constraint_set = data
    else:
        constraints = []
        constraint_set = {"constraints": []}

    if not constraints:
        _record_issue(result, summary, "warning", "empty_constraint_set", "Constraint set contained no constraints.")

    summary["constraint_set"] = constraint_set
    result["constraints"].extend(_with_source(constraint, summary, "constraints") for constraint in constraints)
    summary["materialized_counts"]["constraints"] = len(constraints)


def _select_executable_factors(
    result: dict[str, Any],
    summary: dict[str, Any],
    top_factors: list[dict[str, Any]],
    arms: list[dict[str, Any]],
    design_policy: dict[str, Any],
    has_inline_factors: bool,
) -> list[dict[str, Any]]:
    active = str(design_policy.get("active_factor_space") or "").strip()
    if arms:
        summary["preserved_multi_arm"] = len(arms) > 1
        summary["arms"] = [_arm_id(arm) for arm in arms if _arm_id(arm)]
        if len(arms) > 1:
            if not active:
                severity = "warning" if has_inline_factors else "blocker"
                _record_issue(
                    result,
                    summary,
                    severity,
                    "active_factor_space_required",
                    "Multi-arm factor_space was preserved but not flattened; set design_policy.active_factor_space for executable factors.",
                )
                return []
            arm = _find_arm(arms, active)
            if arm is None:
                severity = "warning" if has_inline_factors else "blocker"
                _record_issue(
                    result,
                    summary,
                    severity,
                    "active_factor_space_not_found",
                    f"design_policy.active_factor_space={active} did not match any factor_space arm.",
                )
                return []
            summary["active_factor_space"] = active
            summary["flattening"] = "active_arm"
            return top_factors + _arm_factors(arm)

        arm = arms[0]
        summary["active_factor_space"] = _arm_id(arm)
        summary["flattening"] = "single_arm"
        return top_factors + _arm_factors(arm)

    arm_ids = sorted({str(factor.get("arm_id") or "").strip() for factor in top_factors if str(factor.get("arm_id") or "").strip()})
    if len(arm_ids) > 1:
        summary["preserved_multi_arm"] = True
        summary["arms"] = arm_ids
        if not active:
            severity = "warning" if has_inline_factors else "blocker"
            _record_issue(
                result,
                summary,
                severity,
                "active_factor_space_required",
                "Factor rows span multiple arm_id values; set design_policy.active_factor_space for executable factors.",
            )
            return []
        if active not in arm_ids:
            severity = "warning" if has_inline_factors else "blocker"
            _record_issue(
                result,
                summary,
                severity,
                "active_factor_space_not_found",
                f"design_policy.active_factor_space={active} did not match any factor row arm_id.",
            )
            return []
        summary["active_factor_space"] = active
        summary["flattening"] = "active_arm_rows"
        return [factor for factor in top_factors if str(factor.get("arm_id") or "").strip() == active]

    summary["flattening"] = "top_level"
    return top_factors


def _coerce_factor_space(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        factors = _as_dict_list(data)
        arm_ids = sorted({str(row.get("arm_id") or "").strip() for row in factors if str(row.get("arm_id") or "").strip()})
        if len(arm_ids) > 1:
            arms = []
            for arm_id in arm_ids:
                arms.append({"arm_id": arm_id, "factors": [row for row in factors if str(row.get("arm_id") or "").strip() == arm_id]})
            return {"arms": arms}
        return {"factors": factors}
    if isinstance(data, dict):
        return data
    return {"factors": []}


def _load_structured_input(path: Path) -> tuple[Any | None, dict[str, str] | None]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            return json.loads(path.read_text()), None
        if suffix in {".yaml", ".yml"}:
            try:
                yaml = importlib.import_module("yaml")
            except ImportError:
                try:
                    return simple_yaml_load(path.read_text()), None
                except Exception as exc:
                    return None, {
                        "severity": "warning",
                        "code": "yaml_parser_unavailable",
                        "message": f"PyYAML is not installed and stdlib YAML fallback could not parse {path.name}: {exc}",
                    }
            return yaml.safe_load(path.read_text()), None
        if suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            return _read_delimited_rows(path, delimiter), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"severity": "blocker", "code": "parse_failed", "message": f"Could not parse {path.name}: {exc}"}
    except Exception as exc:  # PyYAML raises parser-specific exceptions.
        return None, {"severity": "blocker", "code": "parse_failed", "message": f"Could not parse {path.name}: {exc}"}
    return None, {
        "severity": "warning",
        "code": "unsupported_format",
        "message": f"Unsupported materialized input format: {suffix or 'unknown'}",
    }


def simple_yaml_load(text: str) -> Any:
    """Parse the small YAML subset used by repo fixtures when PyYAML is absent."""

    lines = _yaml_lines(text)
    if not lines:
        return {}
    value, index = _parse_yaml_block(lines, 0, lines[0]["indent"])
    if index < len(lines):
        raise ValueError(f"unexpected trailing YAML content near line {lines[index]['number']}")
    return value


def _yaml_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.lstrip(" ")
        if stripped in {"---", "..."}:
            continue
        rows.append({"number": number, "indent": len(raw) - len(stripped), "text": stripped.rstrip(), "raw": raw.rstrip()})
    return rows


def _parse_yaml_block(lines: list[dict[str, Any]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index]["indent"] < indent:
        return {}, index
    if lines[index]["text"].startswith("- "):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_dict(lines, index, indent)


def _parse_yaml_list(lines: list[dict[str, Any]], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines) and lines[index]["indent"] == indent and lines[index]["text"].startswith("- "):
        rest = lines[index]["text"][2:].strip()
        index += 1
        if rest == "":
            if index < len(lines) and lines[index]["indent"] > indent:
                item, index = _parse_yaml_block(lines, index, lines[index]["indent"])
            else:
                item = {}
        elif _looks_like_key_value(rest):
            key, value_text = _split_yaml_key_value(rest, lines[index - 1]["number"])
            item = {}
            if value_text in {"|", ">"}:
                item[key], index = _parse_yaml_scalar_block(lines, index, indent, folded=value_text == ">")
            elif value_text == "":
                if index < len(lines) and lines[index]["indent"] > indent:
                    item[key], index = _parse_yaml_block(lines, index, lines[index]["indent"])
                else:
                    item[key] = {}
            else:
                item[key] = _parse_yaml_scalar(value_text)
            if index < len(lines) and lines[index]["indent"] > indent:
                extra, index = _parse_yaml_block(lines, index, lines[index]["indent"])
                if isinstance(extra, dict):
                    item.update(extra)
                elif extra:
                    item.setdefault("items", extra)
        elif rest in {"|", ">"}:
            item, index = _parse_yaml_scalar_block(lines, index, indent, folded=rest == ">")
        else:
            item = _parse_yaml_scalar(rest)
            if index < len(lines) and lines[index]["indent"] > indent:
                continuation, index = _parse_yaml_plain_continuation(lines, index, indent)
                if isinstance(item, str) and continuation:
                    item = f"{item} {continuation}".strip()
        items.append(item)
    return items, index


def _parse_yaml_dict(lines: list[dict[str, Any]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    while index < len(lines) and lines[index]["indent"] == indent and not lines[index]["text"].startswith("- "):
        key, value_text = _split_yaml_key_value(lines[index]["text"], lines[index]["number"])
        index += 1
        if value_text in {"|", ">"}:
            data[key], index = _parse_yaml_scalar_block(lines, index, indent, folded=value_text == ">")
        elif value_text == "":
            if index < len(lines) and lines[index]["indent"] > indent:
                data[key], index = _parse_yaml_block(lines, index, lines[index]["indent"])
            else:
                data[key] = {}
        else:
            data[key] = _parse_yaml_scalar(value_text)
    return data, index


def _parse_yaml_scalar_block(lines: list[dict[str, Any]], index: int, parent_indent: int, folded: bool) -> tuple[str, int]:
    parts: list[str] = []
    while index < len(lines) and lines[index]["indent"] > parent_indent:
        parts.append(lines[index]["raw"].strip())
        index += 1
    separator = " " if folded else "\n"
    return separator.join(parts).strip(), index


def _parse_yaml_plain_continuation(lines: list[dict[str, Any]], index: int, parent_indent: int) -> tuple[str, int]:
    parts: list[str] = []
    while index < len(lines) and lines[index]["indent"] > parent_indent:
        parts.append(lines[index]["text"].strip())
        index += 1
    return " ".join(parts).strip(), index


def _looks_like_key_value(text: str) -> bool:
    if ":" not in text:
        return False
    key = text.split(":", 1)[0].strip()
    return bool(key) and " " not in key


def _split_yaml_key_value(text: str, number: int) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"expected key/value at YAML line {number}")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ValueError(f"empty key at YAML line {number}")
    return key, value.strip()


def _parse_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_parse_yaml_scalar(item.strip()) for item in body.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    number = parse_number(value)
    if number is not None:
        return int(number) if float(number).is_integer() else number
    return value


def _read_delimited_rows(path: Path, delimiter: str) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [_clean_csv_row(row) for row in reader]


def _clean_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        clean_key = str(key).strip()
        if not clean_key:
            continue
        clean_value = "" if value is None else str(value).strip()
        if clean_value == "":
            continue
        if clean_key in {"min", "max", "fixed_value", "mixture_sum", "cost_per_unit", "sampling_burden"}:
            cleaned[clean_key] = parse_number(clean_value) if parse_number(clean_value) is not None else clean_value
        elif clean_key == "levels":
            cleaned[clean_key] = _split_levels(clean_value)
        else:
            cleaned[clean_key] = clean_value
    return cleaned


def _split_levels(value: str) -> list[str]:
    for delimiter in ["|", ";"]:
        if delimiter in value:
            return [item.strip() for item in value.split(delimiter) if item.strip()]
    return [value]


def _with_source(record: dict[str, Any], summary: dict[str, Any], section: str) -> dict[str, Any]:
    sourced = dict(record)
    if section == "factors" and "factor_id" not in sourced and "id" in sourced:
        sourced["factor_id"] = sourced["id"]
    if section == "responses" and "response_id" not in sourced and "id" in sourced:
        sourced["response_id"] = sourced["id"]
    if section == "constraints" and "constraint_id" not in sourced and "id" in sourced:
        sourced["constraint_id"] = sourced["id"]
    sourced.setdefault("source", f"input:{summary['input_id']}")
    sourced[MATERIALIZED_META_KEY] = {
        "input_id": summary["input_id"],
        "path": summary.get("path", ""),
        "role": summary["role"],
        "format": summary.get("format", ""),
    }
    return sourced


def _record_conflicts(
    section: str,
    record_id: str,
    inline_record: dict[str, Any],
    materialized_record: dict[str, Any],
) -> list[dict[str, Any]]:
    inline = _canonical_record(section, inline_record)
    materialized = _canonical_record(section, materialized_record)
    conflicts: list[dict[str, Any]] = []
    for field in sorted(set(inline) & set(materialized)):
        if field == SECTION_ID_KEYS[section][0]:
            continue
        inline_value = inline[field]
        materialized_value = materialized[field]
        if _empty(inline_value) or _empty(materialized_value):
            continue
        if _comparable(inline_value) == _comparable(materialized_value):
            continue
        conflicts.append(
            {
                "section": section,
                "record_id": record_id,
                "field": field,
                "severity": "warning",
                "code": "manifest_inline_conflict",
                "manifest_value": inline_value,
                "input_value": materialized_value,
                "message": f"Manifest inline {section} value wins for {record_id}.{field}.",
                "resolution": "manifest_inline_wins",
                "input": _source_meta(materialized_record),
            }
        )
    return conflicts


def _canonical_record(section: str, record: dict[str, Any]) -> dict[str, Any]:
    aliases = CANONICAL_ALIASES.get(section, {})
    canonical: dict[str, Any] = {}
    for key, value in strip_materialization_metadata(record).items():
        canonical_key = aliases.get(key, key)
        if canonical_key == "source":
            continue
        canonical[canonical_key] = value
    return canonical


def _record_id(record: dict[str, Any], section: str) -> str:
    for key in SECTION_ID_KEYS[section]:
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def _record_issue(
    result: dict[str, Any],
    summary: dict[str, Any],
    severity: str,
    code: str,
    message: str,
) -> None:
    summary["status"] = "blocked" if severity == "blocker" else summary.get("status", "warning")
    bucket = "blockers" if severity == "blocker" else "warnings"
    summary[bucket].append(message)
    result["input_conflicts"].append(
        {
            "section": summary["role"],
            "input_id": summary["input_id"],
            "path": summary.get("path", ""),
            "severity": severity,
            "code": code,
            "message": message,
            "resolution": "not_materialized" if severity == "blocker" else "materialized_with_warning",
        }
    )


def _source_meta(record: dict[str, Any]) -> dict[str, Any]:
    meta = record.get(MATERIALIZED_META_KEY)
    if isinstance(meta, dict):
        return dict(meta)
    return {}


def _input_role(item: dict[str, Any]) -> str:
    haystack = _normalize_token(" ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]))
    if "factor_space" in haystack:
        return "factor_space"
    if "constraint_set" in haystack:
        return "constraint_set"
    return ""


def _normalize_token(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _base_summary(item: dict[str, Any], role: str) -> dict[str, Any]:
    input_id = str(item.get("input_id") or item.get("id") or role).strip() or role
    return {
        "input_id": input_id,
        "kind": str(item.get("kind") or ""),
        "role": role,
        "path": str(item.get("path") or ""),
        "resolved_path": "",
        "format": "",
        "status": "pending",
        "warnings": [],
        "blockers": [],
        "materialized_counts": {
            "factor_spaces": 0,
            "factors": 0,
            "responses": 0,
            "constraints": 0,
        },
    }


def _format_for_path(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return "yaml" if suffix in {"yaml", "yml"} else suffix


def _contributed_count(summary: dict[str, Any]) -> int:
    counts = summary.get("materialized_counts") if isinstance(summary.get("materialized_counts"), dict) else {}
    return sum(int(value or 0) for value in counts.values())


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _arm_id(arm: dict[str, Any]) -> str:
    return str(arm.get("arm_id") or arm.get("id") or arm.get("name") or "").strip()


def _find_arm(arms: list[dict[str, Any]], active: str) -> dict[str, Any] | None:
    for arm in arms:
        if _arm_id(arm) == active:
            return arm
    return None


def _arm_factors(arm: dict[str, Any]) -> list[dict[str, Any]]:
    arm_id = _arm_id(arm)
    factors = []
    for factor in _as_dict_list(arm.get("factors")):
        factor_with_arm = dict(factor)
        if arm_id:
            factor_with_arm.setdefault("arm_id", arm_id)
        factors.append(factor_with_arm)
    return factors


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _comparable(value: Any) -> Any:
    if isinstance(value, str):
        number = parse_number(value)
        if number is not None:
            return number
        return value.strip()
    if isinstance(value, list):
        return [_comparable(item) for item in value]
    if isinstance(value, dict):
        return {key: _comparable(value[key]) for key in sorted(value)}
    return value
