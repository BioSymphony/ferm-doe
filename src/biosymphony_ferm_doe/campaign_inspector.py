"""Lightweight campaign orientation for humans and agent harnesses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ARTIFACTS = (
    ("manifest", "campaign_manifest.json", "campaign source of truth"),
    ("historical_run_ledger", "inputs/historical_run_ledger.csv", "prior rows"),
    ("evidence_table", "inputs/evidence_table.csv", "evidence rows"),
    ("wave1_results", "inputs/wave1_results.csv", "first-batch result rows"),
    ("readiness_summary", "expected/readiness_summary.json", "public readiness summary"),
    ("selected_wave1_design", "expected/selected_wave_1_design.csv", "selected first-batch design"),
    ("run_packet", "expected/run_packet.md", "handoff packet fixture"),
    ("dossier", "ferm-doe-dossier", "compiled dossier directory"),
)

SKIP_CATALOG_DIRS = {
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    "__pycache__",
    "build",
    "dist",
}


def inspect_campaign(path: Path, *, command_style: str = "public") -> dict[str, Any]:
    """Summarize a campaign directory or manifest without running heavy checks."""

    manifest_path = _manifest_path(Path(path))
    campaign_dir = manifest_path.parent
    manifest = _read_json(manifest_path)

    artifacts = [_artifact(campaign_dir, artifact_id, rel_path, role) for artifact_id, rel_path, role in ARTIFACTS]
    present_artifacts = [artifact["id"] for artifact in artifacts if artifact["present"]]
    results_path = _first_present(campaign_dir, ("inputs/wave1_results.csv", "results/wave1_results.csv", "expected/wave1_results.csv"))

    responses = _responses(manifest)
    factors = _factors(manifest)
    arms = _arms(manifest)
    readiness = _readiness(manifest)

    return {
        "schema_version": 1,
        "inspection_kind": "biosymphony_ferm_doe_campaign_inspection",
        "campaign_dir": campaign_dir.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "campaign_id": manifest.get("campaign_id"),
        "name": manifest.get("name"),
        "claim_level": manifest.get("claim_level"),
        "profiles": _string_list(manifest.get("profiles")),
        "objective": manifest.get("objective"),
        "readiness": readiness,
        "counts": {
            "responses": len(responses),
            "assayed_responses": sum(1 for response in responses if response.get("assay_required") is True),
            "derived_responses": sum(1 for response in responses if response.get("assay_required") is False),
            "factors": len(factors),
            "numeric_factors": sum(1 for factor in factors if _factor_type(factor) in {"numeric", "continuous"}),
            "categorical_factors": sum(1 for factor in factors if _factor_type(factor) in {"categorical", "category"}),
            "constraints": len(_list(manifest.get("constraints"))),
            "arms": len(arms),
            "risks": len(_list(manifest.get("risk_register"))),
            "decision_rules": len(_list(manifest.get("decision_rules"))),
            "stop_rules": len(_list(manifest.get("stop_rules"))),
        },
        "doe": _doe_summary(manifest),
        "adaptive_wave2": _adaptive_summary(manifest),
        "responses": responses,
        "factors": factors,
        "arms": arms,
        "artifacts": artifacts,
        "present_artifacts": present_artifacts,
        "capabilities": _capabilities(manifest, artifacts, results_path),
        "recommended_next_commands": _commands(campaign_dir, manifest_path, results_path, command_style=command_style),
        "non_claim": "Campaign inspection summarizes declared planning metadata; it does not validate readiness, assay results, or physical execution.",
    }


def catalog_campaigns(root: Path, *, command_style: str = "public") -> dict[str, Any]:
    """Build a compact catalog of campaign manifests below ``root``."""

    root = Path(root)
    campaigns = [_catalog_row(inspect_campaign(path, command_style=command_style), root) for path in _manifest_paths(root)]
    campaigns.sort(key=lambda item: (item.get("path") or "", item.get("campaign_id") or ""))
    return {
        "schema_version": 1,
        "catalog_kind": "biosymphony_ferm_doe_campaign_catalog",
        "root": root.as_posix(),
        "campaign_count": len(campaigns),
        "readiness_counts": _count_values(campaign.get("readiness", {}).get("overall") for campaign in campaigns),
        "profile_counts": _count_many(campaign.get("profiles", []) for campaign in campaigns),
        "capability_counts": _capability_counts(campaigns),
        "campaigns": campaigns,
        "non_claim": "Campaign cataloging summarizes declared planning metadata; it does not validate readiness, assay results, or physical execution.",
    }


def _manifest_path(path: Path) -> Path:
    if path.is_dir():
        return path / "campaign_manifest.json"
    return path


def _manifest_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise FileNotFoundError(root)

    paths: list[Path] = []
    for path in root.rglob("campaign_manifest.json"):
        if any(part in SKIP_CATALOG_DIRS for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def _catalog_row(report: dict[str, Any], root: Path) -> dict[str, Any]:
    campaign_dir = Path(str(report["campaign_dir"]))
    manifest_path = Path(str(report["manifest_path"]))
    path = _relative_or_posix(campaign_dir, root)
    first_command = report["recommended_next_commands"][0] if report["recommended_next_commands"] else None
    return {
        "campaign_id": report.get("campaign_id"),
        "name": report.get("name"),
        "path": path,
        "manifest_path": _relative_or_posix(manifest_path, root),
        "claim_level": report.get("claim_level"),
        "profiles": report.get("profiles", []),
        "readiness": report.get("readiness", {}),
        "counts": report.get("counts", {}),
        "capabilities": report.get("capabilities", {}),
        "present_artifacts": report.get("present_artifacts", []),
        "next_command": first_command,
    }


def _relative_or_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_many(groups: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for values in groups:
        for value in values:
            key = str(value or "unknown")
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _capability_counts(campaigns: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for campaign in campaigns:
        for name, enabled in campaign.get("capabilities", {}).items():
            if enabled:
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _artifact(campaign_dir: Path, artifact_id: str, rel_path: str, role: str) -> dict[str, Any]:
    path = campaign_dir / rel_path
    present = path.exists() and (path.is_dir() or path.stat().st_size > 0)
    return {"id": artifact_id, "path": rel_path, "role": role, "present": present}


def _first_present(campaign_dir: Path, paths: tuple[str, ...]) -> str | None:
    for rel_path in paths:
        path = campaign_dir / rel_path
        if path.is_file() and path.stat().st_size > 0:
            return rel_path
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _responses(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for response in _list(manifest.get("responses")):
        if not isinstance(response, dict):
            continue
        rows.append(
            {
                "response_id": response.get("response_id") or response.get("id"),
                "class": response.get("class"),
                "measurement_type": response.get("measurement_type"),
                "direction": response.get("direction"),
                "assay_required": response.get("assay_required"),
                "assay_method": response.get("assay_method"),
                "sample_fraction": response.get("sample_fraction"),
            }
        )
    return rows


def _factors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for factor in _list(manifest.get("factors")):
        if not isinstance(factor, dict):
            continue
        row: dict[str, Any] = {
            "factor_id": factor.get("factor_id") or factor.get("id"),
            "type": _factor_type(factor),
            "unit": factor.get("unit"),
        }
        if "low" in factor or "high" in factor:
            row["range"] = {"low": factor.get("low"), "high": factor.get("high")}
        if isinstance(factor.get("levels"), list):
            row["level_count"] = len(factor["levels"])
        rows.append(row)
    return rows


def _factor_type(factor: dict[str, Any]) -> str:
    return str(factor.get("type") or factor.get("kind") or "")


def _arms(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for arm in _list(manifest.get("arms") or manifest.get("campaign_arms")):
        if not isinstance(arm, dict):
            continue
        rows.append(
            {
                "arm_id": arm.get("arm_id") or arm.get("id"),
                "purpose": arm.get("purpose"),
                "format": arm.get("format"),
                "run_budget": arm.get("run_budget"),
                "bridge_role": arm.get("bridge_role"),
            }
        )
    return rows


def _readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    readiness = manifest.get("readiness")
    if isinstance(readiness, dict):
        return {
            "overall": readiness.get("overall") or manifest.get("readiness_expectation") or manifest.get("readiness_target"),
            "reasons": readiness.get("reasons", []),
            "axis_count": len(readiness.get("axes", {})) if isinstance(readiness.get("axes"), dict) else 0,
        }
    return {
        "overall": manifest.get("readiness_expectation") or manifest.get("readiness_target"),
        "reasons": [],
        "axis_count": 0,
    }


def _doe_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    doe = manifest.get("doe")
    if not isinstance(doe, dict):
        return {"declared": False}
    return {
        "declared": True,
        "family": doe.get("family"),
        "n_runs": doe.get("n_runs"),
        "randomized": doe.get("randomized"),
        "claim": doe.get("claim"),
        "design_table_path": doe.get("design_table_path"),
        "model_terms": _string_list(doe.get("model_terms")),
    }


def _adaptive_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    wave2 = manifest.get("adaptive_wave2")
    if not isinstance(wave2, dict):
        return {"declared": False}
    return {
        "declared": True,
        "claim_level": wave2.get("claim_level"),
        "primary_response_id": wave2.get("primary_response_id"),
        "allowed_actions": _string_list(wave2.get("allowed_actions")),
        "self_learning_enabled": bool((wave2.get("self_learning") or {}).get("enabled")) if isinstance(wave2.get("self_learning"), dict) else False,
    }


def _capabilities(manifest: dict[str, Any], artifacts: list[dict[str, Any]], results_path: str | None) -> dict[str, Any]:
    present = {artifact["id"] for artifact in artifacts if artifact["present"]}
    return {
        "can_validate_manifest": "manifest" in present,
        "can_check_public_dossier": {"manifest", "readiness_summary"}.issubset(present),
        "can_generate_wave1_design": bool(_list(manifest.get("factors")) and _list(manifest.get("responses"))),
        "can_analyze_results": results_path is not None,
        "can_plan_wave2": results_path is not None and isinstance(manifest.get("adaptive_wave2"), dict),
        "has_evidence_table": "evidence_table" in present,
        "has_selected_wave1_design": "selected_wave1_design" in present,
        "has_run_packet": "run_packet" in present,
        "has_multi_arm_shape": bool(_list(manifest.get("arms") or manifest.get("campaign_arms"))),
    }


def _commands(campaign_dir: Path, manifest_path: Path, results_path: str | None, *, command_style: str) -> list[dict[str, str]]:
    campaign = campaign_dir.as_posix()
    out_root = f".runtime/{campaign_dir.name}"
    commands = [
        {"id": "validate", "reason": "run the public readiness/guidance validator", "command": f"ferm-doe validate {campaign} --summary"},
        {"id": "doctor", "reason": "check repo optional backends and registry surfaces", "command": "ferm-doe doctor"},
        {"id": "generate-design", "reason": "emit a first-batch design from declared factors and DoE policy", "command": f"ferm-doe generate-design {campaign} --out {out_root}/wave1_design.csv --metadata-out {out_root}/wave1_design.metadata.json"},
        {"id": "finalize", "reason": "compose available artifacts into one run packet", "command": f"ferm-doe finalize {campaign} --out {out_root}/run_packet.md --json-out {out_root}/run_packet.json"},
    ]
    if results_path:
        commands.insert(
            3,
            {
                "id": "plan-wave2",
                "reason": "plan the next experiment round from available result rows",
                "command": f"ferm-doe plan-wave2 {campaign} --results {campaign}/{results_path} --out-dir {out_root}/wave2",
            },
        )
    return commands
