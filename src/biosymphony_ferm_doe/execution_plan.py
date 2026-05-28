"""Deterministic execution planning for selected Ferm DoE designs."""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import Any


EXECUTION_POLICY_MODES = {
    "full_randomization",
    "blocked_randomization",
    "split_plot_like",
    "manual_locked_order",
}

EXECUTION_PLAN_FIELDS = [
    "design_run_id",
    "execution_order",
    "block_id",
    "randomization_group",
    "vessel_id_or_slot",
    "setup_batch",
    "control_placement_reason",
    "operator_actual_start",
    "operator_actual_end",
    "operator_notes",
]

RUN_SHEET_EXECUTION_FIELDS = [
    "design_run_id",
    "execution_order",
    "run_order",
    "block_id",
    "randomization_group",
    "vessel_id_or_slot",
    "setup_batch",
    "control_placement_reason",
    "operator_actual_start",
    "operator_actual_end",
    "operator_notes",
]


def build_execution_plan(
    state: dict[str, Any],
    selected_design: dict[str, Any] | None,
    selected_design_id: str,
) -> dict[str, Any]:
    """Create a deterministic physical execution plan without changing the design table."""
    selected_rows = [dict(row) for row in selected_design.get("rows", [])] if selected_design else []
    policy = execution_policy_from_state(state)
    mode = str(policy.get("mode") or "full_randomization")
    if mode not in EXECUTION_POLICY_MODES:
        raise ValueError(f"unsupported execution planning mode: {mode}")
    row_ids = [str(row.get("run_id") or "").strip() for row in selected_rows]
    seed_basis = seed_basis_for_plan(state, selected_design_id, mode, row_ids, policy)
    seed = deterministic_seed(policy.get("seed"), seed_basis)
    ordered_rows = order_rows(selected_rows, state, policy, mode, seed)
    slots = vessel_slots(policy, len(selected_rows))
    setup_batch_size = int(policy.get("setup_batch_size") or len(slots) or max(1, len(selected_rows)) or 1)
    setup_batch_size = max(1, setup_batch_size)

    plan_rows = []
    for index, row in enumerate(ordered_rows, start=1):
        block_id = block_id_for_row(row, state, policy, mode)
        randomization_group = randomization_group_for_row(row, block_id, mode, policy)
        setup_batch = int((index - 1) / setup_batch_size) + 1
        slot = slots[(index - 1) % len(slots)] if slots else f"slot_{index:02d}"
        plan_rows.append(
            {
                "design_run_id": str(row.get("run_id") or ""),
                "execution_order": index,
                "block_id": block_id,
                "randomization_group": randomization_group,
                "vessel_id_or_slot": slot,
                "setup_batch": f"setup_batch_{setup_batch:02d}",
                "control_placement_reason": control_placement_reason(row, mode),
                "operator_actual_start": "",
                "operator_actual_end": "",
                "operator_notes": "",
            }
        )

    return {
        "schema_version": 1,
        "plan_kind": "ferm_doe_execution_plan",
        "campaign_id": state.get("campaign_id"),
        "selected_design_id": selected_design_id,
        "policy": {
            "mode": mode,
            "seed": seed,
            "seed_basis": seed_basis,
            "deterministic": True,
            "block_field": policy.get("block_field", ""),
            "block_factors": policy.get("block_factors", []),
            "setup_batch_size": setup_batch_size,
            "vessel_slot_count": len(slots),
        },
        "row_count": len(plan_rows),
        "rows": plan_rows,
    }


def execution_policy_from_state(state: dict[str, Any]) -> dict[str, Any]:
    design_policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    nested = {}
    for key in ["execution_plan", "execution_policy", "randomization"]:
        if isinstance(design_policy.get(key), dict):
            nested = dict(design_policy[key])
            break
    policy = dict(nested)
    for key in [
        "mode",
        "seed",
        "block_field",
        "block_factors",
        "manual_order",
        "vessel_slots",
        "vessel_ids",
        "vessel_count",
        "setup_batch_size",
        "randomize_block_order",
    ]:
        if key in design_policy and key not in policy:
            policy[key] = design_policy[key]
    if "mode" not in policy:
        for key in ["execution_mode", "randomization_mode", "policy_mode"]:
            if key in design_policy:
                policy["mode"] = design_policy[key]
                break
    policy["mode"] = str(policy.get("mode") or "full_randomization")
    if not isinstance(policy.get("block_factors"), list):
        policy["block_factors"] = []
    if not isinstance(policy.get("manual_order"), list):
        policy["manual_order"] = []
    return policy


def seed_basis_for_plan(
    state: dict[str, Any],
    selected_design_id: str,
    mode: str,
    row_ids: list[str],
    policy: dict[str, Any],
) -> str:
    if policy.get("seed") not in (None, ""):
        return f"explicit|{state.get('campaign_id')}|{selected_design_id}|{mode}|{len(row_ids)}"
    return "|".join([str(state.get("campaign_id") or ""), selected_design_id, mode, ",".join(row_ids)])


def deterministic_seed(raw_seed: Any, seed_basis: str) -> int:
    if raw_seed not in (None, ""):
        try:
            return int(raw_seed)
        except (TypeError, ValueError):
            text = str(raw_seed)
    else:
        text = seed_basis
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def order_rows(
    rows: list[dict[str, Any]],
    state: dict[str, Any],
    policy: dict[str, Any],
    mode: str,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    if mode == "manual_locked_order":
        return manual_order_rows(rows, policy)
    if mode == "full_randomization":
        ordered = list(rows)
        rng.shuffle(ordered)
        return ordered
    grouped = group_rows(rows, state, policy, mode)
    block_ids = sorted(grouped, key=natural_key)
    if mode == "split_plot_like" or policy.get("randomize_block_order"):
        rng.shuffle(block_ids)
    ordered_rows: list[dict[str, Any]] = []
    for block_id in block_ids:
        items = list(grouped[block_id])
        rng.shuffle(items)
        ordered_rows.extend(items)
    return ordered_rows


def manual_order_rows(rows: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {str(row.get("run_id") or ""): row for row in rows}
    ordered = []
    seen: set[str] = set()
    for run_id in [str(item) for item in policy.get("manual_order", [])]:
        row = by_id.get(run_id)
        if row is not None and run_id not in seen:
            ordered.append(row)
            seen.add(run_id)
    ordered.extend(row for row in rows if str(row.get("run_id") or "") not in seen)
    return ordered


def group_rows(
    rows: list[dict[str, Any]],
    state: dict[str, Any],
    policy: dict[str, Any],
    mode: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[block_id_for_row(row, state, policy, mode)].append(row)
    return dict(grouped)


def block_id_for_row(row: dict[str, Any], state: dict[str, Any], policy: dict[str, Any], mode: str) -> str:
    block_field = str(policy.get("block_field") or "")
    if block_field and row.get(block_field) not in (None, ""):
        return clean_id(row.get(block_field), prefix="block")
    for field in ["block_id", "block", "randomization_group"]:
        if row.get(field) not in (None, ""):
            return clean_id(row.get(field), prefix="block")
    factor_ids = [str(item) for item in policy.get("block_factors", []) if item]
    if mode == "split_plot_like" and not factor_ids:
        factor_ids = hard_to_change_factor_ids(state)
    if factor_ids:
        values = [f"{factor_id}={row.get(factor_id, '')}" for factor_id in factor_ids if factor_id in row]
        if values:
            prefix = "whole_plot" if mode == "split_plot_like" else "block"
            return clean_id("|".join(values), prefix=prefix)
    return "block_1"


def hard_to_change_factor_ids(state: dict[str, Any]) -> list[str]:
    factors = state.get("factors") if isinstance(state.get("factors"), list) else []
    ids = []
    for factor in factors:
        if not isinstance(factor, dict):
            continue
        factor_type = str(factor.get("type") or "").lower()
        if factor.get("hard_to_change") or factor_type in {"hard_to_change", "block"}:
            factor_id = str(factor.get("factor_id") or "")
            if factor_id:
                ids.append(factor_id)
    return ids


def randomization_group_for_row(row: dict[str, Any], block_id: str, mode: str, policy: dict[str, Any]) -> str:
    group_field = str(policy.get("randomization_group_field") or "")
    if group_field and row.get(group_field) not in (None, ""):
        return clean_id(row.get(group_field), prefix="group")
    if mode == "full_randomization":
        return "all_runs"
    if mode == "manual_locked_order":
        return "manual_locked"
    return block_id


def vessel_slots(policy: dict[str, Any], row_count: int) -> list[str]:
    raw_slots = policy.get("vessel_slots") or policy.get("vessel_ids")
    if isinstance(raw_slots, list) and raw_slots:
        return [str(item) for item in raw_slots if str(item)]
    vessel_count = 0
    try:
        vessel_count = int(policy.get("vessel_count") or 0)
    except (TypeError, ValueError):
        vessel_count = 0
    slot_count = vessel_count if vessel_count > 0 else row_count
    slot_count = max(1, slot_count)
    return [f"slot_{index:02d}" for index in range(1, slot_count + 1)]


def control_placement_reason(row: dict[str, Any], mode: str) -> str:
    if str(row.get("run_role") or "").lower() == "control":
        purpose = str(row.get("control_purpose") or "").strip()
        if purpose:
            return f"control row retained under {mode}; {purpose}"
        control_type = str(row.get("control_type") or "control").strip()
        return f"{control_type} control row retained under {mode}"
    return "experimental row placed by execution planning policy"


def execution_plan_rows_for_run_sheet(
    selected_rows: list[dict[str, Any]],
    execution_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id = {str(row.get("run_id") or ""): row for row in selected_rows}
    rows = []
    for plan_row in execution_plan.get("rows", []):
        design_run_id = str(plan_row.get("design_run_id") or "")
        design_row = dict(by_id.get(design_run_id, {}))
        item = {**plan_row, "run_order": plan_row.get("execution_order", ""), **design_row, "planned_status": "planned"}
        rows.append(item)
    return rows


def clean_id(value: Any, prefix: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return f"{prefix}_1"
    out = []
    for char in raw.lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "_":
            out.append("_")
    text = "".join(out).strip("_")
    if not text:
        return f"{prefix}_1"
    if text.startswith(f"{prefix}_"):
        return text
    return f"{prefix}_{text}"


def natural_key(value: str) -> list[Any]:
    parts: list[Any] = []
    current = ""
    is_digit = False
    for char in value:
        if char.isdigit() != is_digit and current:
            parts.append(int(current) if is_digit else current)
            current = ""
        current += char
        is_digit = char.isdigit()
    if current:
        parts.append(int(current) if is_digit else current)
    return parts
