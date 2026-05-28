"""Public-safe contract helpers for compact Ferm DoE artifacts.

Internal deployments may carry richer dossier contracts outside this package.
This module carries the smaller public-facing contract from the public repo:
it validates synthetic/public demos, bounded public task requests, and public
release scans.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .public_release import scan_paths


DOSSIER_CONTRACT_KIND = "ferm_doe_public_dossier_contract"
TASK_REQUEST_KIND = "ferm_doe_task_request"
TASK_REQUEST_VALIDATION_KIND = "ferm_doe_public_task_request_validation"
SCHEMA_VERSION = 1

REQUIRED_PUBLIC_DOSSIER_FILES = [
    "campaign_manifest.json",
    "expected/readiness_summary.json",
    "expected/AGENTS.md",
]
OPTIONAL_CONTRACT_FILES = [
    "expected/selected_wave_1_design.csv",
    "expected/run_packet.md",
]
EVIDENCE_REQUIRED_HEADERS = {
    "evidence_id",
    "source_type",
    "source_ref",
    "claim",
    "confidence",
    "review_status",
    "decision_impact",
}
PUBLIC_EVIDENCE_SOURCE_TYPES = {
    "public_literature",
    "public_literature_placeholder",
    "paper_numeric",
    "public_database",
    "public_protocol",
    "vendor_public",
    "synthetic_demo",
    "synthetic_demo_note",
    "sanitized_reference",
}
PUBLIC_TASK_SOURCE_TYPES = {
    "synthetic",
    "synthetic_demo_note",
    "public_literature",
    "public_protocol",
    "vendor_public",
    "sanitized_reference",
}
PUBLIC_TASK_REQUIRED_FIELDS = {
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
PUBLIC_TASK_CLAIM_LEVELS = {
    "public_synthetic_demo",
    "internal_planning",
    "physical_execution_planning",
    "planned_wave1_design",
    "planned_wave2_design",
    "evidence_plan_only",
    "evidence_rows_for_review",
    "run_packet_planning_compose",
}
PUBLIC_TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
PUBLIC_TASK_STATUSES = {"proposed", "ready", "in_progress", "blocked", "done"}
FORBIDDEN_TASK_KEYS = {
    "tracker_issue_id",
    "tracker_project_id",
    "provider_pod_id",
    "provider_template_id",
    "provider_mutation",
    "private_artifact_path",
}
FORBIDDEN_COMMAND_TOKENS = {"launch-pod", "create-pod", "delete-pod", "providerctl"}

PRIVATE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])/(?:Users|home|Volumes)/[A-Za-z0-9._-]+(?=[/\s'\"]|$)")
WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+")
SECRET_VALUE_RE = re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{16,}")
OVERCLAIM_PATTERNS = [
    re.compile(r"\bvalidated optimization\b", re.IGNORECASE),
    re.compile(r"\bvalidated scale(?:-| )transfer\b", re.IGNORECASE),
    re.compile(r"\bproduction(?:-| )ready\b", re.IGNORECASE),
    re.compile(r"\bapproved for (?:lab[- ])?execution\b", re.IGNORECASE),
    re.compile(r"\bgxp batch record\b", re.IGNORECASE),
    re.compile(r"\boptimized conditions?\b", re.IGNORECASE),
]
NEGATION_HINTS = {
    "no ",
    "not ",
    "never ",
    "without ",
    "do not ",
    "does not ",
    "cannot ",
    "planning",
    "planned",
    "candidate",
    "non-claim",
    "non_claim",
}


def load_public_task_request(path: str | Path) -> dict[str, Any]:
    """Read a public task request JSON object from disk."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task request must be a JSON object")
    return payload


def validate_public_task_request(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the public-safe task request contract."""

    checks: list[dict[str, Any]] = []
    _add(checks, "task_request-object", isinstance(data, dict), "Task request is a JSON object.")
    if not isinstance(data, dict):
        return _task_result({}, checks)

    missing = sorted(PUBLIC_TASK_REQUIRED_FIELDS - set(data))
    _add(checks, "task_request-required-fields", not missing, "Task request declares required public contract fields.", detail=missing)
    _add(checks, "task_request-schema-version", data.get("schema_version") == SCHEMA_VERSION, "schema_version is 1.")
    _add(checks, "task_request-kind", data.get("request_kind") == TASK_REQUEST_KIND, f"request_kind is {TASK_REQUEST_KIND}.")
    _add(checks, "task_request-id", _non_empty_str(data.get("task_request_id")), "task_request_id is a non-empty string.")
    _add(checks, "task_request-campaign-id", _non_empty_str(data.get("campaign_id")), "campaign_id is a non-empty string.")
    _add(checks, "task_request-title", _non_empty_str(data.get("title")), "title is a non-empty string.")

    claim_level = data.get("claim_level")
    if claim_level is not None:
        _add(checks, "task_request-claim-level", claim_level in PUBLIC_TASK_CLAIM_LEVELS, "claim_level is known.", severity="warning")
    priority = data.get("priority")
    if priority is not None:
        _add(checks, "task_request-priority", priority in PUBLIC_TASK_PRIORITIES, "priority is known.", severity="warning")
    status = data.get("status")
    if status is not None:
        _add(checks, "task_request-status", status in PUBLIC_TASK_STATUSES, "status is known.", severity="warning")

    _validate_public_task_safety(data, checks)
    _validate_public_task_string_list(data, "expected_artifacts", checks, require_relative_paths=True)
    _validate_public_task_string_list(data, "acceptance_criteria", checks)
    _validate_public_task_string_list(data, "validation_commands", checks)
    _validate_public_task_string_list(data, "touched_areas", checks, require_relative_paths=True)
    _validate_public_task_inputs(data, checks)
    _validate_public_task_work_items(data, checks)
    _validate_public_task_forbidden_keys(data, checks)
    _validate_public_task_text_safety(data, checks)
    _validate_public_task_commands(data, checks)
    return _task_result(data, checks)


def check_dossier_contract(path: Path) -> dict[str, Any]:
    """Validate a compact public demo or public-facing dossier surface."""

    root = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    _check_required_files(root, checks, errors)
    manifest = _load_json_optional(root / "campaign_manifest.json", errors)
    readiness = _load_json_optional(root / "expected" / "readiness_summary.json", errors)

    if manifest:
        _check_manifest(root, manifest, checks, errors, warnings)
        _check_evidence_inputs(root, manifest, checks, errors, warnings)
    if readiness:
        _check_readiness_summary(readiness, checks, errors, warnings)

    _check_selected_design(root / "expected" / "selected_wave_1_design.csv", checks, errors, warnings)
    _check_markdown_claims(root, checks, errors)

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_kind": DOSSIER_CONTRACT_KIND,
        "path": _public_path_label(root),
        "campaign_id": manifest.get("campaign_id") if isinstance(manifest, dict) else None,
        "status": "FAIL" if errors else "PASS",
        "required_files": REQUIRED_PUBLIC_DOSSIER_FILES,
        "optional_contract_files": OPTIONAL_CONTRACT_FILES,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "non_claim": "Public dossier checks cover planning artifacts only; they do not verify physical execution or validation.",
    }


def summarize_public_contract(result: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary for public validators and CLI output."""

    failed = [check for check in result.get("checks", []) if not check.get("ok")]
    return {
        "campaign_id": result.get("campaign_id"),
        "task_request_id": result.get("task_request_id"),
        "status": result.get("status"),
        "contract_kind": result.get("contract_kind"),
        "error_count": result.get("error_count", 0),
        "warning_count": result.get("warning_count", 0),
        "failed_check_ids": [check.get("id") for check in failed],
        "non_claim": result.get("non_claim"),
    }


def audit_public_tree(root: Path) -> dict[str, Any]:
    """Run the stricter public-release scanner over a tree."""

    root = Path(root)
    findings = scan_paths([root], root=root, allow_private=[])
    return {
        "root": _public_path_label(root),
        "status": "PASS" if not findings else "FAIL",
        "issue_count": len(findings),
        "issues": [finding.to_dict() for finding in findings],
        "non_claim": "Public audit is a release scrubber; it does not classify campaign completeness.",
    }


def _validate_public_task_safety(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    public_safety = data.get("public_safety")
    if not isinstance(public_safety, dict):
        _add(checks, "task_request-public-safety", False, "public_safety is an object.")
        return
    _add(checks, "task_request-privacy", public_safety.get("privacy") == "synthetic_or_public_only", "privacy is synthetic_or_public_only.")
    _add(checks, "task_request-no-private-data", public_safety.get("private_data_allowed") is False, "private_data_allowed is false.")
    _add(checks, "task_request-no-provider-mutation", public_safety.get("provider_mutation_allowed") is False, "provider_mutation_allowed is false.")
    _add(checks, "task_request-no-tracker-ids", public_safety.get("tracker_specific_ids_allowed") is False, "tracker_specific_ids_allowed is false.")


def _validate_public_task_inputs(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
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
        ok = _non_empty_str(item.get("role")) and _relative_path(item.get("path")) and item.get("source_type") in PUBLIC_TASK_SOURCE_TYPES
        _add(checks, f"task_request-input-{index}", ok, "Input declares role, relative path, and public-safe source_type.")


def _validate_public_task_work_items(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
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
        _add(checks, f"task_request-work-item-{index}", _non_empty_str(item_id) and _non_empty_str(item.get("title")), "Work item declares id and title.", severity="warning")
        if isinstance(item_id, str):
            _add(checks, f"task_request-work-item-id-unique-{item_id}", item_id not in seen, f"Work item id is unique: {item_id}.", severity="warning")
            seen.add(item_id)


def _validate_public_task_string_list(data: dict[str, Any], key: str, checks: list[dict[str, Any]], *, require_relative_paths: bool = False) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        _add(checks, f"task_request-{key}", False, f"{key} is a non-empty list.")
        return
    strings = all(_non_empty_str(item) for item in value)
    _add(checks, f"task_request-{key}", strings, f"{key} contains non-empty strings.")
    if require_relative_paths and strings:
        bad = [item for item in value if not _relative_path(item)]
        _add(checks, f"task_request-{key}-relative", not bad, f"{key} uses relative public paths.", detail=bad)


def _validate_public_task_forbidden_keys(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    found: list[str] = []

    def walk(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_path = f"{prefix}.{key}" if prefix else str(key)
                if str(key).lower() in FORBIDDEN_TASK_KEYS:
                    found.append(key_path)
                walk(child, key_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}[{index}]")

    walk(data)
    _add(checks, "task_request-forbidden-keys", not found, "No private tracker, provider-mutation, or private-artifact keys are present.", detail=found)


def _validate_public_task_text_safety(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    findings: list[str] = []

    def walk(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}[{index}]")
        elif isinstance(value, str) and (PRIVATE_PATH_RE.search(value) or WINDOWS_USER_PATH_RE.search(value) or SECRET_VALUE_RE.search(value)):
            findings.append(prefix or "<root>")

    walk(data)
    _add(checks, "task_request-text-public-safe", not findings, "No private paths or secret-like values appear in text fields.", detail=findings)


def _validate_public_task_commands(data: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    commands = data.get("validation_commands", [])
    if not isinstance(commands, list):
        return
    blocked: list[str] = []
    for command in commands:
        if not isinstance(command, str):
            continue
        tokens = set(re.findall(r"[A-Za-z0-9_.-]+", command.lower()))
        if tokens & FORBIDDEN_COMMAND_TOKENS or PRIVATE_PATH_RE.search(command) or WINDOWS_USER_PATH_RE.search(command):
            blocked.append(command)
    _add(checks, "task_request-validation-commands-public-safe", not blocked, "Validation commands are local and public-safe.", detail=blocked)


def _task_result(data: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["ok"] and check["severity"] == "warning"]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_kind": TASK_REQUEST_VALIDATION_KIND,
        "task_request_id": data.get("task_request_id") if isinstance(data, dict) else None,
        "campaign_id": data.get("campaign_id") if isinstance(data, dict) else None,
        "status": "FAIL" if errors else "PASS",
        "checks": checks,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "failed_check_ids": [check["id"] for check in checks if not check["ok"]],
        "non_claim": "Task request validation checks dispatch contract shape; it does not approve physical execution.",
    }


def _check_required_files(root: Path, checks: list[dict[str, Any]], errors: list[str]) -> None:
    for rel_path in REQUIRED_PUBLIC_DOSSIER_FILES:
        target = root / rel_path
        ok = target.is_file() and target.stat().st_size > 0
        _add(checks, f"dossier-file-{rel_path}", ok, f"Required dossier file exists and is non-empty: {rel_path}.")
        if not ok:
            errors.append(f"missing or empty required dossier file: {rel_path}")
    for rel_path in OPTIONAL_CONTRACT_FILES:
        target = root / rel_path
        _add(checks, f"dossier-optional-{rel_path}", target.is_file() and target.stat().st_size > 0, f"Optional contract file is available: {rel_path}.", severity="warning")


def _check_manifest(root: Path, manifest: dict[str, Any], checks: list[dict[str, Any]], errors: list[str], warnings: list[str]) -> None:
    _add(checks, "dossier-manifest-campaign-id", _non_empty_str(manifest.get("campaign_id")), "Manifest declares campaign_id.")
    if not _non_empty_str(manifest.get("campaign_id")):
        errors.append("campaign_manifest.json has no campaign_id")
    claim_level = manifest.get("claim_level")
    _add(checks, "dossier-manifest-claim-level", _non_empty_str(claim_level), "Manifest declares claim_level.", severity="warning")
    if not _non_empty_str(claim_level):
        warnings.append("campaign_manifest.json has no claim_level")
    inputs = manifest.get("inputs")
    if isinstance(inputs, dict):
        for key, rel_path in inputs.items():
            input_path_ok = _relative_path(rel_path)
            _add(checks, f"dossier-input-relative-{key}", input_path_ok, f"Manifest input path is relative: {key}.")
            if not input_path_ok:
                errors.append(f"manifest input path is not relative or public-safe: {key}")
            if isinstance(rel_path, str) and _relative_path(rel_path) and not (root / rel_path).exists():
                warnings.append(f"manifest input not present: {rel_path}")


def _check_readiness_summary(readiness: dict[str, Any], checks: list[dict[str, Any]], errors: list[str], warnings: list[str]) -> None:
    status = readiness.get("status")
    ok_status = status in {"GREEN", "YELLOW", "RED"}
    _add(checks, "dossier-readiness-status", ok_status, "Readiness status is GREEN, YELLOW, or RED.")
    if not ok_status:
        errors.append("readiness_summary.json has invalid status")
    reasons = readiness.get("reasons")
    ok_reasons = isinstance(reasons, list) and bool(reasons)
    _add(checks, "dossier-readiness-reasons", ok_reasons, "Readiness summary carries explicit caveats or reasons.", severity="warning")
    if not ok_reasons:
        warnings.append("readiness_summary.json has no explicit reasons")


def _check_evidence_inputs(root: Path, manifest: dict[str, Any], checks: list[dict[str, Any]], errors: list[str], warnings: list[str]) -> None:
    inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
    rel_path = inputs.get("evidence_table") if isinstance(inputs, dict) else None
    if not isinstance(rel_path, str):
        return
    path = root / rel_path
    if not path.is_file():
        return
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            headers = set(reader.fieldnames or [])
    except OSError as exc:
        errors.append(f"could not read evidence table: {exc}")
        return
    missing_headers = sorted(EVIDENCE_REQUIRED_HEADERS - headers)
    _add(checks, "dossier-evidence-headers", not missing_headers, "Evidence table has provenance and decision-impact headers.", detail=missing_headers)
    if missing_headers:
        errors.append("evidence_table.csv missing headers: " + ", ".join(missing_headers))
    bad_sources = sorted({row.get("source_type", "") for row in rows if row.get("source_type") not in PUBLIC_EVIDENCE_SOURCE_TYPES})
    _add(checks, "dossier-evidence-source-types", not bad_sources, "Evidence source types are public, synthetic, or sanitized.", detail=bad_sources)
    if bad_sources:
        errors.append("evidence_table.csv has non-public source types: " + ", ".join(bad_sources))
    unresolved = [row.get("evidence_id", "<missing>") for row in rows if row.get("review_status") == "needs_source"]
    _add(checks, "dossier-evidence-review-status", not unresolved, "Evidence rows do not rely on unresolved source placeholders.", severity="warning")
    if unresolved:
        warnings.append("evidence rows need source review: " + ", ".join(unresolved[:8]))


def _check_selected_design(path: Path, checks: list[dict[str, Any]], errors: list[str], warnings: list[str]) -> None:
    if not path.exists():
        warnings.append("selected_wave_1_design.csv is not present; dossier remains a readiness-only handoff")
        return
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            headers = reader.fieldnames or []
    except OSError as exc:
        errors.append(f"could not read selected design: {exc}")
        return
    id_field = "run_id" if "run_id" in headers else "design_run_id" if "design_run_id" in headers else None
    _add(checks, "dossier-design-id-column", id_field is not None, "Selected design has run_id or design_run_id.")
    if id_field is None:
        errors.append("selected_wave_1_design.csv lacks run_id or design_run_id")
        return
    ids = [row.get(id_field, "") for row in rows if row.get(id_field)]
    _add(checks, "dossier-design-rows", bool(ids), "Selected design has at least one planned row.", severity="warning")
    if not ids:
        warnings.append("selected_wave_1_design.csv has no planned rows")
    if len(ids) != len(set(ids)):
        errors.append("selected_wave_1_design.csv has duplicate run ids")


def _check_markdown_claims(root: Path, checks: list[dict[str, Any]], errors: list[str]) -> None:
    claim_findings: list[str] = []
    for rel_path in ("expected/run_packet.md", "expected/AGENTS.md"):
        path = root / rel_path
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            normalized = line.lower()
            if any(hint in normalized for hint in NEGATION_HINTS):
                continue
            if any(pattern.search(line) for pattern in OVERCLAIM_PATTERNS):
                claim_findings.append(f"{rel_path}:{line_number}")
    _add(checks, "dossier-overclaim-scan", not claim_findings, "Run packet and handoff avoid unsupported validation, production, and execution claims.", detail=claim_findings)
    if claim_findings:
        errors.append("unsupported claim language found in " + ", ".join(claim_findings[:8]))


def _load_json_optional(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON in {path.name}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return payload


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    ok: bool,
    message: str,
    *,
    severity: str = "error",
    detail: Any | None = None,
) -> None:
    entry: dict[str, Any] = {"id": check_id, "ok": bool(ok), "severity": severity, "detail": message}
    if detail:
        entry["offending_values"] = detail
    checks.append(entry)


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _relative_path(value: Any) -> bool:
    if not _non_empty_str(value):
        return False
    path = Path(str(value))
    text = str(value)
    return not path.is_absolute() and ".." not in path.parts and not PRIVATE_PATH_RE.search(text) and not WINDOWS_USER_PATH_RE.search(text)


def _public_path_label(path: Path) -> str:
    if path.is_absolute():
        return path.name or "<absolute_path_redacted>"
    return path.as_posix()


__all__ = [
    "DOSSIER_CONTRACT_KIND",
    "REQUIRED_PUBLIC_DOSSIER_FILES",
    "audit_public_tree",
    "check_dossier_contract",
    "load_public_task_request",
    "summarize_public_contract",
    "validate_public_task_request",
]
