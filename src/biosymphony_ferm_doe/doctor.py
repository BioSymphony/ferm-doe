"""Repository capability report for BioSymphony Ferm DoE."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .adaptive_backend_surface import validate_surface as validate_adaptive_backend_surface
from .tool_registry import validate_tool_registry
from .utilities.deps import dependency_status


def run_doctor(root: Path, *, live_imports: bool = False, fail_on_stale: bool = False) -> dict[str, Any]:
    """Inspect repo-local capability surfaces without mutating the checkout."""

    repo_root = Path(root).resolve()
    checks: list[dict[str, Any]] = []

    pyproject = repo_root / "pyproject.toml"
    registry = repo_root / "docs" / "tool-registry.json"
    surface = repo_root / "docs" / "adaptive-backend-evaluation.json"
    examples_dir = repo_root / "examples"

    _add(checks, "repo-root-exists", repo_root.is_dir(), f"Repository root exists: {repo_root}.")
    _add(checks, "pyproject-present", pyproject.is_file(), "pyproject.toml is present.")
    _add(checks, "tool-registry-present", registry.is_file(), "docs/tool-registry.json is present.")
    _add(checks, "adaptive-backend-surface-present", surface.is_file(), "docs/adaptive-backend-evaluation.json is present.")

    examples = _campaign_examples(examples_dir)
    _add(checks, "campaign-examples-present", bool(examples), "At least one example campaign with campaign_manifest.json is present.")

    deps = dependency_status()
    _add(
        checks,
        "stdlib-backend-available",
        bool(deps.get("backends", {}).get("stdlib", {}).get("available")),
        "Dependency-free stdlib backend is available.",
    )

    registry_report = _run_registry_check(registry, pyproject, repo_root, fail_on_stale=fail_on_stale)
    if registry_report.get("checked"):
        _add(
            checks,
            "tool-registry-valid",
            registry_report.get("status") == "PASS",
            "Tool registry validates against pyproject and route rules.",
            detail=registry_report,
        )

    surface_report = _run_surface_check(surface, registry, pyproject, live_imports=live_imports)
    if surface_report.get("checked"):
        _add(
            checks,
            "adaptive-backend-surface-valid",
            surface_report.get("status") == "PASS",
            "Adaptive backend surface validates against the registry and pyproject.",
            detail=surface_report,
        )

    return {
        "schema_version": 1,
        "doctor_kind": "biosymphony_ferm_doe_repo_doctor",
        "package_version": __version__,
        "root": str(repo_root),
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "status": _status(checks),
        "checks": checks,
        "examples": {"count": len(examples), "campaign_dirs": examples},
        "dependency_status": deps,
        "tool_registry": registry_report,
        "adaptive_backend_surface": surface_report,
        "next_actions": _next_actions(checks),
        "non_claim": "Doctor reports repository capability and configuration health; it does not validate campaign science or physical execution.",
    }


def _campaign_examples(examples_dir: Path) -> list[str]:
    if not examples_dir.is_dir():
        return []
    return sorted(path.relative_to(examples_dir.parent).as_posix() for path in examples_dir.iterdir() if (path / "campaign_manifest.json").is_file())


def _run_registry_check(registry: Path, pyproject: Path, repo_root: Path, *, fail_on_stale: bool) -> dict[str, Any]:
    if not registry.is_file():
        return {"checked": False, "status": "MISSING", "path": str(registry)}
    try:
        report = validate_tool_registry(registry, pyproject_path=pyproject, repo_root=repo_root, fail_on_stale=fail_on_stale)
    except Exception as exc:  # pragma: no cover - defensive report path
        return {"checked": True, "status": "ERROR", "path": str(registry), "error": str(exc)}
    return _compact(report, "registry_check_kind", "tool_count")


def _run_surface_check(surface: Path, registry: Path, pyproject: Path, *, live_imports: bool) -> dict[str, Any]:
    if not surface.is_file():
        return {"checked": False, "status": "MISSING", "path": str(surface)}
    try:
        report = validate_adaptive_backend_surface(surface, registry_path=registry, pyproject_path=pyproject, live_imports=live_imports)
    except Exception as exc:  # pragma: no cover - defensive report path
        return {"checked": True, "status": "ERROR", "path": str(surface), "error": str(exc)}
    return _compact(report, "surface_check_kind", "candidate_count", "scenario_count")


def _compact(report: dict[str, Any], *keys: str) -> dict[str, Any]:
    keep = {"checked": True, "status": report.get("status"), "error_count": report.get("error_count"), "warning_count": report.get("warning_count")}
    for key in keys:
        keep[key] = report.get(key)
    findings = report.get("findings", [])
    if findings:
        keep["findings"] = findings[:10]
        keep["finding_count"] = len(findings)
    return keep


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    ok: bool,
    message: str,
    *,
    severity: str = "error",
    detail: dict[str, Any] | None = None,
) -> None:
    entry: dict[str, Any] = {"id": check_id, "ok": ok, "severity": severity, "message": message}
    if detail is not None:
        entry["detail"] = detail
    checks.append(entry)


def _status(checks: list[dict[str, Any]]) -> str:
    if any(not check["ok"] and check["severity"] == "error" for check in checks):
        return "FAIL"
    if any(not check["ok"] for check in checks):
        return "WARN"
    return "PASS"


def _next_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = []
    for check in checks:
        if check["ok"]:
            continue
        actions.append(f"{check['id']}: {check['message']}")
    return actions
