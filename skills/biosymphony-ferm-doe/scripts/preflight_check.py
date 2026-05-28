#!/usr/bin/env python3
"""Lightweight preflight checks for BioSymphony Ferm DoE contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "campaign_id",
    "name",
    "objective",
    "readiness_target",
    "sources",
    "inputs",
    "constraints",
    "responses",
    "factors",
}
OPTIONAL_MANIFEST_LIST_FIELDS = {"artifacts"}
READINESS_VALUES = {"GREEN", "YELLOW", "RED"}

REQUIRED_ISSUE_SECTIONS = [
    "## Summary",
    "## Inputs",
    "## Acceptance Criteria",
    "## Validation Commands",
    "## Touched Areas",
    "## Dependencies",
    "## Risk Notes",
    "<!-- symphony:schema",
]


def check_full_manifest(data: dict) -> list[str]:
    errors: list[str] = []

    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(data))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    for field in ["sources", "inputs", "responses", "factors"]:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list")
    for field in OPTIONAL_MANIFEST_LIST_FIELDS:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list")

    objective = data.get("objective", {})
    if not isinstance(objective, dict):
        errors.append("objective must be an object")
    elif not objective.get("primary"):
        errors.append("objective.primary is required")

    readiness_target = data.get("readiness_target")
    if readiness_target not in READINESS_VALUES:
        errors.append("readiness_target must be GREEN, YELLOW, or RED")

    return errors


def check_compact_manifest(data: dict) -> list[str]:
    """Validate lightweight manifest variants used by demos and adapter smokes."""

    errors: list[str] = []
    schema_version = data.get("schema_version")
    if schema_version is not None and schema_version != 1:
        errors.append("schema_version must be 1 when present")

    if not _nonempty_string(data.get("campaign_id")):
        errors.append("campaign_id must be a non-empty string")

    objective = data.get("objective")
    if isinstance(objective, dict):
        if not _nonempty_string(objective.get("primary")):
            errors.append("objective.primary is required when objective is an object")
    elif not _nonempty_string(objective):
        errors.append("objective must be a non-empty string or an object")

    for field in ["responses", "factors"]:
        value = data.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")

    constraints = data.get("constraints")
    if constraints is not None and not isinstance(constraints, list):
        errors.append("constraints must be a list when present")

    inputs = data.get("inputs")
    if inputs is not None and not isinstance(inputs, (dict, list)):
        errors.append("inputs must be an object or list when present")

    readiness = data.get("readiness_target") or data.get("readiness_expectation")
    if readiness is None and isinstance(data.get("readiness"), dict):
        readiness = data["readiness"].get("overall")
    if readiness is not None and readiness not in READINESS_VALUES:
        errors.append("readiness target/expectation must be GREEN, YELLOW, or RED")

    return errors


def check_public_dossier(path: Path) -> list[str]:
    try:
        from biosymphony_ferm_doe.contracts import check_dossier_contract
    except ImportError as exc:
        return [f"could not import public dossier validator: {exc}"]

    result = check_dossier_contract(path)
    return _result_errors(result, ok_statuses={"PASS"})


def check_task_request(data: dict) -> list[str]:
    if "task_request_id" in data or "public_safety" in data:
        try:
            from biosymphony_ferm_doe.contracts import validate_public_task_request
        except ImportError as exc:
            return [f"could not import public task request validator: {exc}"]
        result = validate_public_task_request(data)
        return _result_errors(result, ok_statuses={"PASS", "OK"})

    try:
        from biosymphony_ferm_doe.task_request import route_task_request
    except ImportError as exc:
        return [f"could not import task request router: {exc}"]
    result = route_task_request(data)
    return _result_errors(result, ok_statuses={"OK"})


def check_json_document(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if isinstance(data, dict) and "sidecar_kind" in data:
        try:
            from sidecar_check import check_sidecar
        except ImportError as exc:
            return [f"could not import sidecar validator: {exc}"]
        result = check_sidecar(path)
        if isinstance(result, dict):
            return list(result.get("errors", []))
        return list(result)

    if isinstance(data, dict) and data.get("request_kind") == "ferm_doe_task_request":
        return check_task_request(data)

    public_root = _public_dossier_root(path)
    if public_root is not None:
        return check_public_dossier(public_root)

    if isinstance(data, dict) and _looks_like_manifest(data):
        if _looks_like_full_manifest(data):
            return check_full_manifest(data)
        return check_compact_manifest(data)

    return ["unrecognized JSON contract; expected sidecar, task request, campaign manifest, or public demo directory"]


def check_directory(path: Path) -> list[str]:
    if not (path / "campaign_manifest.json").exists():
        return ["unsupported directory: expected campaign_manifest.json"]
    public_root = _public_dossier_root(path)
    if public_root is not None:
        return check_public_dossier(path)
    return check_json_document(path / "campaign_manifest.json")


def check_markdown_issue(path: Path) -> list[str]:
    text = path.read_text()
    errors = [f"missing section marker: {marker}" for marker in REQUIRED_ISSUE_SECTIONS if marker not in text]

    if "<path>" in text or "<artifact path>" in text:
        errors.append("template placeholders remain unresolved")

    if "Do not store secrets" not in text and "Do not store" not in text:
        errors.append("risk notes must include data-safety guidance")

    return errors


def _looks_like_manifest(data: dict) -> bool:
    return isinstance(data.get("campaign_id"), str) and ("responses" in data or "factors" in data or "objective" in data)


def _looks_like_full_manifest(data: dict) -> bool:
    return (
        isinstance(data.get("objective"), dict)
        and isinstance(data.get("sources"), list)
        and isinstance(data.get("inputs"), list)
        and "readiness_target" in data
        and "name" in data
    )


def _public_dossier_root(path: Path) -> Path | None:
    root = path if path.is_dir() else path.parent
    if (
        (root / "campaign_manifest.json").exists()
        and (root / "expected" / "readiness_summary.json").exists()
        and (root / "expected" / "AGENTS.md").exists()
    ):
        return root
    return None


def _result_errors(result: dict, *, ok_statuses: set[str]) -> list[str]:
    if result.get("status") in ok_statuses:
        return []
    errors = [str(error) for error in result.get("errors", [])]
    failed = result.get("failed_check_ids", [])
    if failed:
        errors.append(f"failed checks: {', '.join(str(item) for item in failed)}")
    for check in result.get("checks", []):
        if check.get("ok") is False and check.get("severity", "error") == "error":
            check_id = check.get("id", "unknown-check")
            detail = check.get("detail") or check.get("message") or "failed"
            errors.append(f"{check_id}: {detail}")
    return errors or [f"contract status was {result.get('status', 'UNKNOWN')}"]


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: preflight_check.py path/to/campaign_manifest.json|campaign_dir|task_request.json|sidecar.json|issue.md",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: file does not exist: {path}", file=sys.stderr)
        return 2

    if path.is_dir():
        errors = check_directory(path)
    elif path.suffix == ".json":
        errors = check_json_document(path)
    elif path.suffix in {".md", ".markdown"}:
        errors = check_markdown_issue(path)
    else:
        errors = [f"unsupported file type: {path.suffix}"]

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
