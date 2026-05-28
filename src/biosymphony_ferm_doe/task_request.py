"""Public-safe task request contract validation.

The task request contract is intentionally small. It gives an agent or
external issue tracker enough structure to dispatch a bounded Ferm DoE work
item without embedding private tracker ids, provider launch details, or
environment-specific paths in the public package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TASK_REQUEST_KIND = "ferm_doe_task_request"
SCHEMA_VERSION = 1
PUBLIC_SOURCE_TYPES = {"synthetic", "synthetic_demo_note", "public_literature", "public_protocol", "vendor_public", "sanitized_reference"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"proposed", "ready", "in_progress", "blocked", "done"}
VALID_CLAIM_LEVELS = {
    "public_synthetic_demo",
    "internal_planning",
    "physical_execution_planning",
    "planned_wave1_design",
    "planned_wave2_design",
    "evidence_plan_only",
    "evidence_rows_for_review",
    "run_packet_planning_compose",
}
REQUIRED_FIELDS = {
    "schema_version",
    "request_kind",
    "task_request_id",
    "campaign_id",
    "title",
    "public_safety",
    "expected_artifacts",
    "acceptance_criteria",
    "validation_commands",
    "touched_areas",
}
FORBIDDEN_KEYS = {
    "tracker_issue_id",
    "tracker_project_id",
    "provider_pod_id",
    "provider_template_id",
    "provider_mutation",
    "private_artifact_path",
}
FORBIDDEN_COMMAND_TOKENS = {
    "launch-pod",
    "create-pod",
    "delete-pod",
    "providerctl",
}
PRIVATE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])/(?:Users|home|Volumes)/[A-Za-z0-9._-]+(?=[/\s'\"]|$)")
WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+")
SECRET_VALUE_RE = re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{16,}")


def load_task_request(path: Path) -> dict[str, Any]:
    """Read a task request JSON object from disk."""
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("task request must be a JSON object")
    return payload


def validate_task_request(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a public-safe task request.

    The result mirrors the repo's campaign validator style: machine-readable
    checks, a status, and counts. Structural and public-safety issues are
    errors; weaker completeness issues are warnings.
    """
    checks: list[dict[str, Any]] = []
    _add(checks, "task_request-object", isinstance(data, dict), "Task request is a JSON object.")
    if not isinstance(data, dict):
        return _result({}, checks)

    missing = sorted(REQUIRED_FIELDS - set(data))
    _add(checks, "task_request-required-fields", not missing, "Task request declares the required public contract fields.", detail_suffix=_join(missing))
    _add(checks, "task_request-schema-version", data.get("schema_version") == SCHEMA_VERSION, "schema_version is 1.")
    _add(checks, "task_request-kind", data.get("request_kind") == TASK_REQUEST_KIND, f"request_kind is {TASK_REQUEST_KIND}.")
    _add(checks, "task_request-id", _non_empty_str(data.get("task_request_id")), "task_request_id is a non-empty string.")
    _add(checks, "task_request-campaign-id", _non_empty_str(data.get("campaign_id")), "campaign_id is a non-empty string.")
    _add(checks, "task_request-title", _non_empty_str(data.get("title")), "title is a non-empty string.")

    claim_level = data.get("claim_level")
    if claim_level is not None:
        _add(checks, "task_request-claim-level", claim_level in VALID_CLAIM_LEVELS, "claim_level is a known public contract label.", severity="warning")

    priority = data.get("priority")
    if priority is not None:
        _add(checks, "task_request-priority", priority in VALID_PRIORITIES, "priority is low, normal, high, or urgent.", severity="warning")

    status = data.get("status")
    if status is not None:
        _add(checks, "task_request-status", status in VALID_STATUSES, "status is proposed, ready, in_progress, blocked, or done.", severity="warning")

    _validate_public_safety(data, checks)
    _validate_string_list(data, "expected_artifacts", checks, require_relative_paths=True)
    _validate_string_list(data, "acceptance_criteria", checks)
    _validate_string_list(data, "validation_commands", checks)
    _validate_string_list(data, "touched_areas", checks, require_relative_paths=True)
    _validate_inputs(data, checks)
    _validate_work_items(data, checks)
    _validate_forbidden_keys(data, checks)
    _validate_text_safety(data, checks)
    _validate_commands(data, checks)
    return _result(data, checks)


def _validate_public_safety(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    public_safety = data.get("public_safety")
    if not isinstance(public_safety, dict):
        _add(checks, "task_request-public-safety", False, "public_safety is an object.")
        return
    privacy = public_safety.get("privacy")
    _add(checks, "task_request-privacy", privacy == "synthetic_or_public_only", "public_safety.privacy is synthetic_or_public_only.")
    _add(checks, "task_request-no-private-data", public_safety.get("private_data_allowed") is False, "private_data_allowed is false.")
    _add(checks, "task_request-no-provider-mutation", public_safety.get("provider_mutation_allowed") is False, "provider_mutation_allowed is false.")
    _add(checks, "task_request-no-tracker-ids", public_safety.get("tracker_specific_ids_allowed") is False, "tracker_specific_ids_allowed is false.")


def _validate_inputs(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    inputs = data.get("inputs", [])
    if inputs in (None, []):
        return
    if not isinstance(inputs, list):
        _add(checks, "task_request-inputs-shape", False, "inputs is a list.", severity="warning")
        return
    for index, item in enumerate(inputs, start=1):
        if not isinstance(item, dict):
            _add(checks, f"task_request-input-{index}", False, "Input item is an object.", severity="warning")
            continue
        role = item.get("role")
        path = item.get("path")
        source_type = item.get("source_type")
        ok = _non_empty_str(role) and _relative_path(path) and source_type in PUBLIC_SOURCE_TYPES
        _add(
            checks,
            f"task_request-input-{index}",
            ok,
            "Input declares role, relative path, and public-safe source_type.",
            severity="warning" if source_type not in PUBLIC_SOURCE_TYPES else "error",
        )


def _validate_work_items(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    items = data.get("work_items", [])
    if items in (None, []):
        return
    if not isinstance(items, list):
        _add(checks, "task_request-work-items-shape", False, "work_items is a list.", severity="warning")
        return
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            _add(checks, f"task_request-work-item-{index}", False, "Work item is an object.", severity="warning")
            continue
        item_id = item.get("id")
        ok = _non_empty_str(item_id) and _non_empty_str(item.get("title"))
        _add(checks, f"task_request-work-item-{index}", ok, "Work item declares id and title.", severity="warning")
        if isinstance(item_id, str):
            _add(checks, f"task_request-work-item-id-unique-{item_id}", item_id not in seen, f"Work item id is unique: {item_id}.", severity="warning")
            seen.add(item_id)


def _validate_string_list(data: dict[str, Any], key: str, checks: list[dict[str, Any]], *, require_relative_paths: bool = False) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        _add(checks, f"task_request-{key}", False, f"{key} is a non-empty list.")
        return
    strings = all(_non_empty_str(item) for item in value)
    _add(checks, f"task_request-{key}", strings, f"{key} contains non-empty strings.")
    if require_relative_paths and strings:
        bad = [item for item in value if not _relative_path(item)]
        _add(checks, f"task_request-{key}-relative", not bad, f"{key} uses relative public paths.", detail_suffix=_join(bad))


def _validate_forbidden_keys(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    found: list[str] = []

    def walk(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_path = f"{prefix}.{key}" if prefix else str(key)
                if str(key).lower() in FORBIDDEN_KEYS:
                    found.append(key_path)
                walk(child, key_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}[{index}]")

    walk(data)
    _add(checks, "task_request-forbidden-keys", not found, "No private tracker, provider-mutation, or private-artifact keys are present.", detail_suffix=_join(found))


def _validate_text_safety(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    findings: list[str] = []

    def walk(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}[{index}]")
        elif isinstance(value, str):
            if PRIVATE_PATH_RE.search(value) or WINDOWS_USER_PATH_RE.search(value) or SECRET_VALUE_RE.search(value):
                findings.append(prefix or "<root>")

    walk(data)
    _add(checks, "task_request-text-public-safe", not findings, "No private paths or secret-like values appear in text fields.", detail_suffix=_join(findings))


def _validate_commands(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    commands = data.get("validation_commands", [])
    if not isinstance(commands, list):
        return
    blocked: list[str] = []
    for command in commands:
        if not isinstance(command, str):
            continue
        tokens = set(re.findall(r"[A-Za-z0-9_.-]+", command.lower()))
        if tokens & FORBIDDEN_COMMAND_TOKENS:
            blocked.append(command)
        if PRIVATE_PATH_RE.search(command) or WINDOWS_USER_PATH_RE.search(command):
            blocked.append(command)
    _add(checks, "task_request-validation-commands-public-safe", not blocked, "Validation commands are local, stdlib, and public-safe.", detail_suffix=_join(blocked))


def _result(data: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["ok"] and check["severity"] == "warning"]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_kind": "ferm_doe_task_request_validation",
        "task_request_id": data.get("task_request_id") if isinstance(data, dict) else None,
        "campaign_id": data.get("campaign_id") if isinstance(data, dict) else None,
        "status": "FAIL" if errors else "PASS",
        "checks": checks,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "failed_check_ids": [check["id"] for check in checks if not check["ok"]],
        "non_claim": "Task request validation checks dispatch contract shape; it does not approve physical execution.",
    }


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    ok: bool,
    detail: str,
    *,
    severity: str = "error",
    detail_suffix: str | None = None,
) -> None:
    if detail_suffix:
        detail = f"{detail} Offending values: {detail_suffix}."
    checks.append({"id": check_id, "ok": ok, "severity": severity, "detail": detail})


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _relative_path(value: Any) -> bool:
    if not _non_empty_str(value):
        return False
    path = Path(str(value))
    text = str(value)
    return not path.is_absolute() and ".." not in path.parts and not PRIVATE_PATH_RE.search(text) and not WINDOWS_USER_PATH_RE.search(text)


def _join(values: list[Any]) -> str | None:
    if not values:
        return None
    return ", ".join(str(value) for value in values[:5])


__all__ = ["TASK_REQUEST_KIND", "SCHEMA_VERSION", "load_task_request", "validate_task_request"]
