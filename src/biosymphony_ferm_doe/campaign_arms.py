"""First-class campaign-arm helpers for coupled Ferm DoE campaigns."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .constraints import design_factors
from .io_utils import markdown_table, write_json


ARM_ID_FIELDS = ("arm_id", "id", "name")
ARM_RUN_ID_SEPARATOR = ":"


def build_campaign_arms(
    manifest: dict[str, Any],
    materialization: dict[str, Any],
    factors: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compile manifest/materialized arm declarations into stable state rows."""

    arms: dict[str, dict[str, Any]] = {}
    for raw_arm in _dict_list(manifest.get("campaign_arms")) or _dict_list(manifest.get("arms")):
        arm = _normalize_arm(raw_arm, source="manifest")
        if arm["arm_id"]:
            arms[arm["arm_id"]] = arm

    for summary in _dict_list(materialization.get("materialized_inputs")):
        factor_space = summary.get("factor_space") if isinstance(summary.get("factor_space"), dict) else {}
        for raw_arm in _dict_list(factor_space.get("arms")):
            arm = _normalize_arm(raw_arm, source=f"input:{summary.get('input_id', 'factor_space')}")
            if not arm["arm_id"]:
                continue
            if arm["arm_id"] in arms:
                arms[arm["arm_id"]] = _merge_arm(arms[arm["arm_id"]], arm)
            else:
                arms[arm["arm_id"]] = arm

    for factor in factors:
        arm_id = str(factor.get("arm_id") or "").strip()
        if not arm_id:
            continue
        arm = arms.setdefault(arm_id, _normalize_arm({"arm_id": arm_id}, source="factor_rows"))
        _append_unique(arm["factor_ids"], str(factor.get("factor_id") or ""))

    for response in responses:
        for arm_id in _record_arm_ids(response):
            arm = arms.setdefault(arm_id, _normalize_arm({"arm_id": arm_id}, source="response_rows"))
            _append_unique(arm["response_ids"], str(response.get("response_id") or ""))

    for constraint in constraints:
        for arm_id in _record_arm_ids(constraint):
            arm = arms.setdefault(arm_id, _normalize_arm({"arm_id": arm_id}, source="constraint_rows"))
            _append_unique(arm["constraint_ids"], str(constraint.get("constraint_id") or constraint.get("id") or ""))

    for arm in arms.values():
        arm["factor_ids"] = _sorted_nonempty(arm.get("factor_ids", []))
        arm["response_ids"] = _sorted_nonempty(arm.get("response_ids", []))
        arm["constraint_ids"] = _sorted_nonempty(arm.get("constraint_ids", []))
    return sorted(arms.values(), key=lambda item: item["arm_id"])


def build_arm_bridge_policy(manifest: dict[str, Any], materialization: dict[str, Any], arms: list[dict[str, Any]]) -> dict[str, Any]:
    raw = manifest.get("arm_bridge_policy")
    if raw is None:
        raw = manifest.get("arm_bridge")
    if raw is None:
        for summary in _dict_list(materialization.get("materialized_inputs")):
            factor_space = summary.get("factor_space") if isinstance(summary.get("factor_space"), dict) else {}
            if isinstance(factor_space.get("arm_bridge"), dict):
                raw = factor_space["arm_bridge"]
                break
    raw_policy = raw if isinstance(raw, dict) else {}
    bridges = _normalize_bridges(raw_policy)
    return {
        "schema_version": 1,
        "policy_kind": "ferm_doe_arm_bridge_policy",
        "status": "declared" if raw_policy else "not_declared",
        "arm_ids": [arm["arm_id"] for arm in arms],
        "description": str(raw_policy.get("description") or ""),
        "bridges": bridges,
        "shared_concepts": raw_policy.get("shared_concepts", []),
        "reserved_blocks": raw_policy.get("reserved_blocks", []),
        "raw_policy": raw_policy,
    }


def apply_active_arm_projection(factors: list[dict[str, Any]], design_policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter inline multi-arm factors when the manifest selected one active arm."""

    active = active_arm_id({"design_policy": design_policy})
    if not active:
        return factors
    arm_ids = {str(factor.get("arm_id") or "").strip() for factor in factors if str(factor.get("arm_id") or "").strip()}
    if len(arm_ids) <= 1 or active not in arm_ids:
        return factors
    return [factor for factor in factors if not str(factor.get("arm_id") or "").strip() or str(factor.get("arm_id") or "").strip() == active]


def campaign_arms_enabled(state: dict[str, Any]) -> bool:
    return len(state.get("campaign_arms", []) or []) > 1 and not active_arm_id(state)


def active_arm_id(state: dict[str, Any]) -> str:
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    return str(policy.get("active_factor_space") or policy.get("active_arm_id") or "").strip()


def multi_arm_factor_ids(state: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for factor in state.get("factors", []):
        arm_id = str(factor.get("arm_id") or "").strip()
        if not arm_id:
            continue
        result.setdefault(arm_id, set()).add(str(factor.get("factor_id") or ""))
    for arm in state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        result.setdefault(arm_id, set()).update(str(item) for item in arm.get("factor_ids", []) if item)
    return result


def project_state_for_arm(state: dict[str, Any], arm_id: str) -> dict[str, Any]:
    """Return a single-arm campaign state projection for existing DOE code."""

    projected = copy.deepcopy(state)
    arm = campaign_arm_by_id(state, arm_id)
    common_factors = [factor for factor in state.get("factors", []) if not str(factor.get("arm_id") or "").strip()]
    arm_factors = [factor for factor in state.get("factors", []) if str(factor.get("arm_id") or "").strip() == arm_id]
    if not arm_factors and arm:
        wanted = {str(item) for item in arm.get("factor_ids", [])}
        arm_factors = [factor for factor in state.get("factors", []) if str(factor.get("factor_id") or "") in wanted]
    projected["factors"] = common_factors + arm_factors
    projected["active_campaign_arm"] = arm_id
    projected["campaign_arm"] = arm or {"arm_id": arm_id}
    projected["campaign_arms_mode"] = "single_arm_projection"
    policy = projected.get("design_policy") if isinstance(projected.get("design_policy"), dict) else {}
    policy = dict(policy)
    arm_policy = arm.get("design_policy") if isinstance(arm, dict) and isinstance(arm.get("design_policy"), dict) else {}
    policy.update(arm_policy)
    policy.setdefault("active_factor_space", arm_id)
    if isinstance(arm, dict) and isinstance(arm.get("run_budget"), int):
        policy["run_budget"] = arm["run_budget"]
    projected["design_policy"] = policy
    projected["missing_info"] = [
        item
        for item in projected.get("missing_info", [])
        if not (isinstance(item, dict) and item.get("code") == "active_factor_space_required")
    ]
    projected["readiness_precheck"] = {
        "status": "RED" if any(isinstance(item, dict) and item.get("severity") == "blocker" for item in projected["missing_info"]) else "YELLOW",
        "blocker_count": sum(1 for item in projected["missing_info"] if isinstance(item, dict) and item.get("severity") == "blocker"),
        "warning_count": sum(1 for item in projected["missing_info"] if isinstance(item, dict) and item.get("severity") == "warning"),
    }
    projected["responses"] = _project_records_to_arm(state.get("responses", []), arm_id, arm.get("response_ids", []) if isinstance(arm, dict) else [])
    projected["constraints"] = _project_records_to_arm(state.get("constraints", []), arm_id, arm.get("constraint_ids", []) if isinstance(arm, dict) else [])
    return projected


def campaign_arm_by_id(state: dict[str, Any], arm_id: str) -> dict[str, Any]:
    for arm in state.get("campaign_arms", []) or []:
        if str(arm.get("arm_id") or "").strip() == arm_id:
            return arm
    return {}


def propose_per_arm_candidate_designs(
    manifest_path: Path | None,
    campaign_state: dict[str, Any],
    out_dir: Path | None = None,
    run_budget: int | None = None,
) -> dict[str, Any]:
    """Generate one candidate-design set per campaign arm."""

    from .doe import infer_run_budget, propose_candidate_designs, write_design_artifacts

    per_arm: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    for arm in campaign_state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        projected = project_state_for_arm(campaign_state, arm_id)
        if not design_factors(projected.get("factors", [])):
            errors.append(f"arm {arm_id} has no executable design factors.")
            per_arm[arm_id] = {
                "schema_version": 1,
                "design_set_kind": "ferm_doe_candidate_designs",
                "campaign_id": campaign_state.get("campaign_id"),
                "arm_id": arm_id,
                "run_budget": 0,
                "candidate_count": 0,
                "candidates": [],
                "errors": [errors[-1]],
            }
            continue
        arm_budget = run_budget or _arm_run_budget(arm) or infer_run_budget(projected)
        designs = propose_candidate_designs(manifest_path, projected, None, arm_budget)
        namespaced = namespace_design_set_for_arm(designs, arm_id)
        per_arm[arm_id] = namespaced
        summaries.append(
            {
                "arm_id": arm_id,
                "candidate_count": namespaced.get("candidate_count", 0),
                "run_budget": namespaced.get("run_budget", arm_budget),
                "factor_ids": [factor.get("factor_id") for factor in projected.get("factors", []) if factor.get("factor_id")],
            }
        )
        if out_dir is not None:
            arm_dir = out_dir / arm_id
            write_design_artifacts(arm_dir, namespaced, projected.get("factors", []), projected.get("model_terms") or {})
    result = {
        "schema_version": 1,
        "design_set_kind": "ferm_doe_per_arm_candidate_designs",
        "campaign_id": campaign_state.get("campaign_id"),
        "arm_count": len(per_arm),
        "arms": summaries,
        "per_arm": per_arm,
        "errors": errors,
    }
    if out_dir is not None:
        write_json(out_dir / "per_arm_candidate_designs.json", result)
    return result


def namespace_design_set_for_arm(designs: dict[str, Any], arm_id: str) -> dict[str, Any]:
    namespaced = copy.deepcopy(designs)
    namespaced["arm_id"] = arm_id
    namespaced["design_set_kind"] = "ferm_doe_arm_candidate_designs"
    candidates = []
    for candidate in namespaced.get("candidates", []):
        candidates.append(namespace_candidate_for_arm(candidate, arm_id))
    namespaced["candidates"] = candidates
    namespaced["candidate_count"] = len(candidates)
    return namespaced


def namespace_candidate_for_arm(candidate: dict[str, Any], arm_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(candidate)
    source_design_id = str(updated.get("design_id") or "")
    updated["source_design_id"] = source_design_id
    updated["design_id"] = namespaced_id(arm_id, source_design_id)
    updated["arm_id"] = arm_id
    rows = []
    for row in updated.get("rows", []):
        source_run_id = str(row.get("run_id") or "").strip()
        item = dict(row)
        item["run_id"] = namespaced_id(arm_id, source_run_id)
        rows.append(item)
    updated["rows"] = rows
    return updated


def namespaced_id(arm_id: str, value: str) -> str:
    clean = str(value or "").strip()
    prefix = str(arm_id or "").strip()
    if not prefix:
        return clean
    if clean.startswith(prefix + ARM_RUN_ID_SEPARATOR):
        return clean
    return f"{prefix}{ARM_RUN_ID_SEPARATOR}{clean}"


def source_id_from_namespaced(arm_id: str, value: str) -> str:
    prefix = str(arm_id or "").strip() + ARM_RUN_ID_SEPARATOR
    text = str(value or "")
    return text[len(prefix) :] if prefix and text.startswith(prefix) else text


def selected_designs_by_arm(designs: dict[str, Any], tournament: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    per_arm_designs = designs.get("per_arm") if isinstance(designs.get("per_arm"), dict) else {}
    per_arm_tournaments = tournament.get("per_arm") if isinstance(tournament.get("per_arm"), dict) else {}
    for arm_id, arm_tournament in per_arm_tournaments.items():
        selected_id = str(arm_tournament.get("selected_design_id") or "")
        for candidate in per_arm_designs.get(arm_id, {}).get("candidates", []):
            if candidate.get("design_id") == selected_id:
                selected[arm_id] = candidate
                break
    return selected


def selected_design_index_rows(selected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm_id, design in sorted(selected.items()):
        for row in design.get("rows", []):
            rows.append(
                {
                    "run_id": row.get("run_id", ""),
                    "arm_id": arm_id,
                    "design_run_id": row.get("run_id", ""),
                    "source_run_id": source_id_from_namespaced(arm_id, str(row.get("run_id") or "")),
                    "selected_design_id": design.get("design_id", ""),
                    "source_design_id": design.get("source_design_id", ""),
                    "executable_artifact": f"selected_wave_1_design.{arm_id}.csv",
                    "planned_status": "per_arm_executable",
                }
            )
    return rows


def write_campaign_arm_artifacts(out_dir: Path, state: dict[str, Any], bridge_report: dict[str, Any] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "campaign_arms.json", {"schema_version": 1, "campaign_arms_kind": "ferm_doe_campaign_arms", "campaign_id": state.get("campaign_id"), "arms": state.get("campaign_arms", [])})
    bridge_policy = state.get("arm_bridge_policy") if isinstance(state.get("arm_bridge_policy"), dict) else {}
    write_json(out_dir / "arm_bridge_policy.json", bridge_policy)
    (out_dir / "arm_bridge_policy.md").write_text(render_arm_bridge_policy(bridge_policy, bridge_report))


def render_arm_bridge_policy(policy: dict[str, Any], bridge_report: dict[str, Any] | None = None) -> str:
    bridge_rows = []
    for bridge in policy.get("bridges", []) if isinstance(policy.get("bridges"), list) else []:
        bridge_rows.append(
            [
                bridge.get("source_arm_id", ""),
                bridge.get("target_arm_id", ""),
                bridge.get("bridge_kind", ""),
                bridge.get("decision_authority", ""),
                bridge.get("claim_boundary", ""),
            ]
        )
    report_lines = ""
    if bridge_report:
        report_lines = (
            "\n## Eligibility\n\n"
            f"- Status: {bridge_report.get('status')}\n"
            f"- Scale/downscale allowed: {bridge_report.get('scale_or_downscale_allowed')}\n"
        )
    return (
        "# Arm Bridge Policy\n\n"
        f"- Status: {policy.get('status', 'not_declared')}\n"
        f"- Description: {policy.get('description', '')}\n\n"
        + markdown_table(["Source", "Target", "Kind", "Decision authority", "Claim boundary"], bridge_rows)
        + report_lines
        + "\n"
    )


def evaluate_bridge_policy(state: dict[str, Any], result_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    policy = state.get("arm_bridge_policy") if isinstance(state.get("arm_bridge_policy"), dict) else {}
    bridges = policy.get("bridges") if isinstance(policy.get("bridges"), list) else []
    items: list[dict[str, Any]] = []
    for bridge in bridges:
        item = dict(bridge)
        evidence = bridge.get("minimum_evidence") if isinstance(bridge.get("minimum_evidence"), dict) else {}
        assay = bridge.get("assay_comparability") if isinstance(bridge.get("assay_comparability"), dict) else {}
        explicit = str(bridge.get("eligibility_status") or bridge.get("status") or "").strip().lower()
        evidence_ok = _status_passes(evidence.get("status")) or evidence.get("passed") is True
        assay_ok = _status_passes(assay.get("status")) or assay.get("passed") is True
        if explicit in {"pass", "passed", "eligible"}:
            eligible = True
            reason = "explicit bridge eligibility passed"
        elif explicit in {"fail", "failed", "blocked"}:
            eligible = False
            reason = "explicit bridge eligibility failed"
        else:
            eligible = bool(evidence_ok and assay_ok)
            reason = "minimum evidence and assay comparability passed" if eligible else "bridge lacks passing minimum evidence and assay comparability"
        item["eligible"] = eligible
        item["reason"] = reason
        items.append(item)
    allowed = any(item.get("eligible") for item in items)
    status = "PASS" if allowed else ("WARN" if policy.get("status") == "declared" else "NOT_DECLARED")
    if not bridges and policy.get("shared_concepts"):
        status = "WARN"
    return {
        "schema_version": 1,
        "bridge_report_kind": "ferm_doe_arm_bridge_eligibility",
        "campaign_id": state.get("campaign_id"),
        "status": status,
        "scale_or_downscale_allowed": allowed,
        "bridges": items,
        "issues": [] if allowed else ["No declared bridge currently permits scale_or_downscale."],
    }


def _normalize_arm(raw: dict[str, Any], source: str) -> dict[str, Any]:
    arm_id = _arm_id(raw)
    factor_ids = [str(item) for item in raw.get("factor_ids", [])] if isinstance(raw.get("factor_ids"), list) else []
    for factor in _dict_list(raw.get("factors")):
        _append_unique(factor_ids, str(factor.get("factor_id") or factor.get("id") or factor.get("name") or ""))
    response_ids = [str(item) for item in raw.get("response_ids", [])] if isinstance(raw.get("response_ids"), list) else []
    constraint_ids = [str(item) for item in raw.get("constraint_ids", [])] if isinstance(raw.get("constraint_ids"), list) else []
    return {
        "arm_id": arm_id,
        "name": str(raw.get("name") or arm_id),
        "kind": str(raw.get("kind") or raw.get("format") or raw.get("type") or ""),
        "purpose": str(raw.get("purpose") or raw.get("scope") or raw.get("description") or ""),
        "vessel": str(raw.get("vessel") or raw.get("format") or ""),
        "run_budget": _positive_int(raw.get("run_budget") or raw.get("runs") or raw.get("vessel_count") or raw.get("well_count")),
        "duration_h": raw.get("duration_h", ""),
        "working_volume_ml": raw.get("working_volume_ml", ""),
        "factor_ids": factor_ids,
        "response_ids": response_ids,
        "constraint_ids": constraint_ids,
        "design_policy": raw.get("design_policy") if isinstance(raw.get("design_policy"), dict) else {},
        "execution_policy": raw.get("execution_policy") if isinstance(raw.get("execution_policy"), dict) else {},
        "capacity": _capacity(raw),
        "source": source,
        "notes": raw.get("notes", []),
    }


def _merge_arm(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in ["kind", "purpose", "vessel", "duration_h", "working_volume_ml"]:
        if not merged.get(key) and right.get(key):
            merged[key] = right[key]
    for key in ["factor_ids", "response_ids", "constraint_ids"]:
        values = list(merged.get(key, []))
        for item in right.get(key, []):
            _append_unique(values, str(item))
        merged[key] = values
    if not merged.get("run_budget") and right.get("run_budget"):
        merged["run_budget"] = right["run_budget"]
    return merged


def _normalize_bridges(raw_policy: dict[str, Any]) -> list[dict[str, Any]]:
    raw_bridges = raw_policy.get("bridges")
    if raw_bridges is None:
        raw_bridges = raw_policy.get("bridge_rules")
    if isinstance(raw_bridges, dict):
        raw_bridges = [raw_bridges]
    bridges = []
    for raw in _dict_list(raw_bridges):
        bridges.append(
            {
                "source_arm_id": str(raw.get("source_arm_id") or raw.get("source") or ""),
                "target_arm_id": str(raw.get("target_arm_id") or raw.get("target") or ""),
                "bridge_kind": str(raw.get("bridge_kind") or raw.get("kind") or "prior_only"),
                "allowed_signal_map": raw.get("allowed_signal_map", raw.get("shared_concepts", [])),
                "forbidden_transfer": raw.get("forbidden_transfer", []),
                "minimum_evidence": raw.get("minimum_evidence", {}),
                "assay_comparability": raw.get("assay_comparability", {}),
                "decision_authority": str(raw.get("decision_authority") or "prior_only"),
                "claim_boundary": str(raw.get("claim_boundary") or "planned_prior"),
                "eligibility_status": raw.get("eligibility_status", raw.get("status", "")),
            }
        )
    return bridges


def _project_records_to_arm(records: list[dict[str, Any]], arm_id: str, explicit_ids: list[Any]) -> list[dict[str, Any]]:
    explicit = {str(item) for item in explicit_ids if item}
    projected = []
    for record in records:
        record_ids = _record_arm_ids(record)
        record_id = str(record.get("response_id") or record.get("constraint_id") or record.get("id") or "")
        if not record_ids or arm_id in record_ids or record_id in explicit:
            projected.append(record)
    return projected


def _record_arm_ids(record: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    if record.get("arm_id"):
        values.append(record.get("arm_id"))
    if isinstance(record.get("arm_ids"), list):
        values.extend(record.get("arm_ids"))
    return [str(value).strip() for value in values if str(value).strip()]


def _capacity(raw: dict[str, Any]) -> dict[str, Any]:
    keys = ["vessel_count", "well_count", "plate_count", "reserved_vessels", "reserved_wells"]
    return {key: raw[key] for key in keys if key in raw}


def _arm_run_budget(arm: dict[str, Any]) -> int | None:
    budget = arm.get("run_budget")
    return budget if isinstance(budget, int) and budget > 0 else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _status_passes(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "eligible", "ok", "true"}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _arm_id(raw: dict[str, Any]) -> str:
    for field in ARM_ID_FIELDS:
        value = str(raw.get(field) or "").strip()
        if value:
            return value
    return ""


def _append_unique(values: list[str], value: str) -> None:
    value = str(value or "").strip()
    if value and value not in values:
        values.append(value)


def _sorted_nonempty(values: list[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})
