#!/usr/bin/env python3
"""Validate public-safe BioSymphony Ferm DoE sidecar templates.

This checker is deliberately provider-neutral. It validates the reusable
campaign, input, and issue-pack sidecars that a tracker or orchestrator can
consume, while blocking launch bundles or mutation-specific provider records
from becoming part of the public template contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_KINDS = {"campaign_goal", "input_pack", "issue_pack"}
ALLOWED_CLASSIFICATIONS = {
    "public",
    "public_source",
    "synthetic",
    "sanitized_private_reference",
    "secure_store_reference",
}
PROVIDER_TOKENS = {"run" + "pod"}
MUTATION_TOKENS = {"provider_handoff", "launch_manifest", "paid_resource_mutation", "api_key", "token"}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path}: cannot read JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path}: root must be a JSON object"
    return payload, None


def walk_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            out.append(str(key))
            out.extend(walk_strings(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(walk_strings(item))
        return out
    if isinstance(value, str):
        return [value]
    return []


def check_public_boundary(data: dict[str, Any], errors: list[str]) -> None:
    haystack = "\n".join(walk_strings(data)).lower()
    for token in sorted(PROVIDER_TOKENS | MUTATION_TOKENS):
        if token in haystack:
            errors.append(f"sidecar must remain public/provider-neutral; found {token!r}")


def check_common(data: dict[str, Any], errors: list[str]) -> str | None:
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    kind = data.get("sidecar_kind")
    if kind not in ALLOWED_KINDS:
        errors.append(f"sidecar_kind must be one of: {', '.join(sorted(ALLOWED_KINDS))}")
        return None
    for field in ("id", "name"):
        if not is_nonempty_string(data.get(field)):
            errors.append(f"{field} is required")
    interface = data.get("interface")
    if isinstance(interface, dict):
        slots = as_list(interface.get("slots"))
        if kind not in slots:
            errors.append(f"interface.slots must include {kind}")
    return str(kind)


def check_campaign_goal(data: dict[str, Any], errors: list[str]) -> None:
    campaign = data.get("campaign")
    if not isinstance(campaign, dict):
        errors.append("campaign must be an object")
    elif not is_nonempty_string(campaign.get("campaign_id")):
        errors.append("campaign.campaign_id is required")

    objective = data.get("objective")
    if not isinstance(objective, dict) or not is_nonempty_string(objective.get("primary")):
        errors.append("objective.primary is required")

    expected = as_list(data.get("expected_artifacts"))
    if not expected or not all(is_nonempty_string(item) for item in expected):
        errors.append("expected_artifacts must contain artifact paths")

    safety = data.get("data_safety")
    if not isinstance(safety, dict):
        errors.append("data_safety must be an object")
        return
    allowed = set(str(item) for item in as_list(safety.get("allowed_in_repo")))
    if not {"public", "synthetic"}.issubset(allowed):
        errors.append("data_safety.allowed_in_repo must include public and synthetic")


def check_input_pack(data: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(data.get("campaign_goal_ref"), dict):
        errors.append("campaign_goal_ref must be an object")

    inputs = as_list(data.get("inputs"))
    if not inputs:
        errors.append("inputs must contain at least one item")
        return
    for index, item in enumerate(inputs):
        prefix = f"inputs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("input_id", "kind", "path"):
            if not is_nonempty_string(item.get(field)):
                errors.append(f"{prefix}.{field} is required")
        classification = item.get("data_classification")
        if classification not in ALLOWED_CLASSIFICATIONS:
            errors.append(f"{prefix}.data_classification must be public, synthetic, or a sanitized reference")

    normalization = data.get("normalization")
    if isinstance(normalization, dict):
        for field in ("source_fields_preserved", "inferred_fields_labeled", "missing_fields_labeled"):
            if normalization.get(field) is not True:
                errors.append(f"normalization.{field} must be true")


def check_issue_pack(data: dict[str, Any], errors: list[str]) -> None:
    for ref_field in ("campaign_goal_ref", "input_pack_ref"):
        if not isinstance(data.get(ref_field), dict):
            errors.append(f"{ref_field} must be an object")

    tracker = data.get("tracker")
    if isinstance(tracker, dict) and tracker.get("activate_first_wave_only") is not True:
        errors.append("tracker.activate_first_wave_only must be true for public issue packs")

    issues = as_list(data.get("issues"))
    if not issues:
        errors.append("issues must contain at least one issue")
        return
    ids: set[str] = set()
    for index, item in enumerate(issues):
        prefix = f"issues[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        issue_id = item.get("issue_id")
        if not is_nonempty_string(issue_id):
            errors.append(f"{prefix}.issue_id is required")
        elif str(issue_id) in ids:
            errors.append(f"{prefix}.issue_id duplicates {issue_id}")
        else:
            ids.add(str(issue_id))
        for field in ("title", "state", "body_template_path"):
            if not is_nonempty_string(item.get(field)):
                errors.append(f"{prefix}.{field} is required")
        if not isinstance(item.get("depends_on"), list):
            errors.append(f"{prefix}.depends_on must be a list")
        commands = as_list(item.get("validation_commands"))
        if not commands or not all(is_nonempty_string(command) for command in commands):
            errors.append(f"{prefix}.validation_commands must contain commands")


def check_sidecar(path: Path) -> dict[str, Any]:
    data, error = load_json(path)
    errors: list[str] = []
    if error:
        errors.append(error)
        return {"path": str(path), "ok": False, "errors": errors}

    assert data is not None
    check_public_boundary(data, errors)
    kind = check_common(data, errors)
    if kind == "campaign_goal":
        check_campaign_goal(data, errors)
    elif kind == "input_pack":
        check_input_pack(data, errors)
    elif kind == "issue_pack":
        check_issue_pack(data, errors)
    return {"path": str(path), "kind": kind, "ok": not errors, "errors": errors}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate provider-neutral BioSymphony sidecar JSON files.")
    parser.add_argument("paths", nargs="+", help="Sidecar JSON files to validate.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = [check_sidecar(Path(path)) for path in args.paths]
    ok = all(result["ok"] for result in results)
    if args.json:
        print(json.dumps({"status": "PASS" if ok else "FAIL", "results": results}, indent=2, sort_keys=True))
    else:
        for result in results:
            if result["ok"]:
                print(f"OK: {result['path']}")
            else:
                print(f"ERROR: {result['path']}", file=sys.stderr)
                for error in result["errors"]:
                    print(f"  - {error}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
