"""Shared helpers for optional utility commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import read_csv, write_json
from .deps import resolve_backend


def utility_manifest(
    *,
    utility: str,
    out_dir: Path,
    inputs: dict[str, Any],
    backend: str | None,
    artifacts: list[str],
    metric_labels: dict[str, str] | None = None,
    caveats: list[str] | None = None,
    adapter_executed: bool = False,
) -> dict[str, Any]:
    resolved = resolve_backend(backend)
    backend_record = {
        "requested": resolved["requested"],
        "available_selected": resolved["selected"],
        "selected": resolved["selected"],
        "status": resolved["status"],
        "fallback": resolved["fallback"],
        "caveat": resolved["caveat"],
        "adapter_executed": adapter_executed,
    }
    if resolved["status"] == "adapter_backed" and not adapter_executed:
        backend_record.update(
            {
                "selected": "stdlib",
                "status": "available_not_used",
                "fallback": "stdlib",
                "caveat": "Optional backend is available, but this utility used the stdlib implementation path.",
            }
        )
    manifest = {
        "schema_version": 1,
        "manifest_kind": "ferm_doe_utility_manifest",
        "utility": utility,
        "inputs": inputs,
        "backend": backend_record,
        "dependency_status": resolved["dependency_status"],
        "metric_labels": metric_labels or {},
        "artifacts": artifacts,
        "caveats": caveats or [],
    }
    write_json(out_dir / "utility_manifest.json", manifest)
    return manifest


def load_optional_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    rows, _ = read_csv(path)
    return rows


def selected_backend_status(backend: str | None, adapter_executed: bool = False) -> str:
    resolved = resolve_backend(backend)
    if resolved["status"] == "adapter_backed" and adapter_executed:
        return f"adapter_backed_{resolved['selected']}"
    if resolved["status"] == "not_available":
        return f"not_available_{resolved['requested']}_fallback_stdlib"
    if resolved["status"] == "adapter_backed" and not adapter_executed:
        return f"available_{resolved['selected']}_used_stdlib"
    return "stdlib"
