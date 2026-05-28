"""Campaign state compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import load_json, parse_number, resolve_path, write_json
from .campaign_arms import (
    apply_active_arm_projection,
    build_arm_bridge_policy,
    build_campaign_arms,
    campaign_arms_enabled,
)
from .materialization import (
    materialization_missing_info,
    materialize_manifest_inputs,
    merge_materialized_records,
)
from .modes import MODE_DEFINITIONS, select_modes
from .schemas import validate_campaign_state
from .workflow_modes import response_has_lab_assay_method, response_requires_assay


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalize_factor(raw: dict[str, Any]) -> dict[str, Any]:
    factor_id = str(raw.get("factor_id") or raw.get("id") or raw.get("name") or "").strip()
    factor_type = str(raw.get("type") or "continuous").lower()
    levels = raw.get("levels")
    if not isinstance(levels, list):
        levels = []
    normalized = {
        "factor_id": factor_id,
        "name": str(raw.get("name") or factor_id),
        "unit": str(raw.get("unit") or ""),
        "type": factor_type,
        "min": parse_number(raw.get("min")),
        "max": parse_number(raw.get("max")),
        "levels": [str(level) for level in levels],
        "role": str(raw.get("role") or "candidate"),
        "phase": str(raw.get("phase") or "unspecified"),
        "controllable": bool(raw.get("controllable", True)),
        "source": str(raw.get("source") or "manifest"),
    }
    for optional in [
        "mixture_group",
        "mixture_sum",
        "fixed_value",
        "hard_to_change",
        "block",
        "candidate_values",
        "cost_per_unit",
        "sampling_burden",
        "arm_id",
        "default",
    ]:
        if optional in raw:
            normalized[optional] = raw[optional]
    return normalized


def normalize_response(raw: dict[str, Any]) -> dict[str, Any]:
    response_id = str(raw.get("response_id") or raw.get("id") or raw.get("name") or "").strip()
    response_class = str(raw.get("class") or _infer_response_class(raw, response_id) or "unknown")
    assay_method = str(raw.get("assay_method") or _default_assay_method(response_class) or "unknown")
    sample_fraction = str(raw.get("sample_fraction") or _default_sample_fraction(response_class) or "unknown")
    normalized = {
        "response_id": response_id,
        "name": str(raw.get("name") or response_id),
        "unit": str(raw.get("unit") or ""),
        "direction": str(raw.get("direction") or "maximize").lower(),
        "class": response_class,
        "sample_fraction": sample_fraction,
        "assay_method": assay_method,
    }
    for optional in [
        "assay_time_h",
        "quality_attribute",
        "calibration",
        "standard_curve",
        "matrix_effects_policy",
        "measurement_type",
        "assay_required",
        "derived_from",
        "primary",
        "definition",
        "notes",
        "assay_power_policy",
        "minimum_detectable_effect",
        "expected_effect_size",
        "noise_sd",
        "cv_percent",
        "replicate_count",
        "target_power",
        "lod",
        "loq",
        "dynamic_range",
        "matrix_recovery_min",
        "turnaround_h",
    ]:
        if optional in raw:
            normalized[optional] = raw[optional]
    return normalized


def _infer_response_class(raw: dict[str, Any], response_id: str) -> str:
    haystack = " ".join(str(raw.get(key, "")) for key in ["response_id", "id", "name", "unit", "definition", "notes"])
    haystack = f"{response_id} {haystack}".lower()
    if "cost" in haystack or "usd" in haystack or "$" in haystack:
        return "cost"
    if "duration" in haystack or "run_time" in haystack or "runtime" in haystack or haystack.endswith("_h"):
        return "run_duration"
    if "acetate" in haystack or "lactate" in haystack or "byproduct" in haystack:
        return "byproduct"
    if "productivity" in haystack:
        return "productivity"
    if "titer" in haystack or "mg/l" in haystack or "mg_l" in haystack:
        return "titer"
    if "yield" in haystack:
        return "yield"
    if "activity" in haystack:
        return "activity"
    if "quality" in haystack or "aggregate" in haystack or "purity" in haystack:
        return "quality"
    if "od600" in haystack or "biomass" in haystack or "dcw" in haystack:
        return "growth"
    return "unknown"


def _default_assay_method(response_class: str) -> str:
    if response_class == "cost":
        return "calculated"
    if response_class in {"duration", "run_duration", "time"}:
        return "clock"
    if response_class == "derived":
        return "derived"
    return "unknown"


def _default_sample_fraction(response_class: str) -> str:
    if response_class in {"cost", "duration", "run_duration", "time", "derived"}:
        return "not_applicable"
    return "unknown"


def _find_input(inputs: list[dict[str, Any]], tokens: list[str]) -> dict[str, Any] | None:
    for item in inputs:
        haystack = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower()
        if any(token in haystack for token in tokens):
            return item
    return None


def _input_exists(item: dict[str, Any] | None, manifest_path: Path) -> bool:
    if not item:
        return False
    path = resolve_path(str(item.get("path") or ""), manifest_path.parent)
    return bool(path and path.exists())


def compile_campaign_state(
    manifest_path: Path,
    out_dir: Path | None = None,
    requested_modes: list[str] | None = None,
    enable_swarm: bool = False,
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    inputs = _as_list(manifest.get("inputs"))
    materialization = materialize_manifest_inputs(manifest, manifest_path)
    input_conflicts = materialization["input_conflicts"]
    raw_factors = merge_materialized_records("factors", materialization["factors"], _as_list(manifest.get("factors")), input_conflicts)
    raw_responses = merge_materialized_records("responses", materialization["responses"], _as_list(manifest.get("responses")), input_conflicts)
    raw_constraints = merge_materialized_records("constraints", materialization["constraints"], _as_list(manifest.get("constraints")), input_conflicts)

    factors = [normalize_factor(item) for item in raw_factors]
    factors = [factor for factor in factors if factor["factor_id"]]
    responses = [normalize_response(item) for item in raw_responses]
    design_policy = manifest.get("design_policy") if isinstance(manifest.get("design_policy"), dict) else {}
    factors = apply_active_arm_projection(factors, design_policy)
    campaign_arms = build_campaign_arms(manifest, materialization, factors, responses, raw_constraints)
    arm_bridge_policy = build_arm_bridge_policy(manifest, materialization, campaign_arms)
    modes = select_modes(manifest, requested_modes)

    objective = manifest.get("objective") if isinstance(manifest.get("objective"), dict) else {}
    primary_response_id = str(objective.get("response_id") or (responses[0]["response_id"] if responses else ""))

    missing_info = missing_information(manifest, factors, responses, inputs, modes, manifest_path)
    missing_info.extend(materialization_missing_info(materialization))
    assumptions = default_assumptions(manifest, factors, responses, modes)
    precheck = {
        "status": "RED" if any(item["severity"] == "blocker" for item in missing_info) else "YELLOW",
        "blocker_count": sum(1 for item in missing_info if item["severity"] == "blocker"),
        "warning_count": sum(1 for item in missing_info if item["severity"] == "warning"),
    }

    state = {
        "schema_version": 1,
        "state_kind": "ferm_doe_campaign_state",
        "campaign_id": str(manifest.get("campaign_id") or manifest_path.stem),
        "name": str(manifest.get("name") or manifest_path.stem),
        "source_manifest": str(manifest_path),
        "manifest_fields": sorted(str(key) for key in manifest),
        "readiness_target": str(manifest.get("readiness_target") or "YELLOW"),
        "campaign_context": extract_campaign_context(manifest),
        "objective": {
            "primary": str(objective.get("primary") or ""),
            "direction": str(objective.get("direction") or "maximize").lower(),
            "response_id": primary_response_id,
            "secondary": objective.get("secondary", []),
        },
        "responses": responses,
        "factors": factors,
        "constraints": raw_constraints,
        "factor_model": manifest.get("factor_model") if isinstance(manifest.get("factor_model"), dict) else {},
        "model_terms": manifest.get("model_terms") if isinstance(manifest.get("model_terms"), dict) else {},
        "design_policy": design_policy,
        "campaign_arms": campaign_arms,
        "campaign_arms_mode": "per_arm" if len(campaign_arms) > 1 and not design_policy.get("active_factor_space") else "single_arm",
        "arm_bridge_policy": arm_bridge_policy,
        "compute_policy": normalize_compute_policy(manifest.get("compute_policy")),
        "swarm_policy": normalize_swarm_policy(manifest.get("swarm_policy"), enable_swarm),
        "sources": _as_list(manifest.get("sources")),
        "inputs": inputs,
        "materialized_inputs": materialization["materialized_inputs"],
        "input_conflicts": input_conflicts,
        "workflow_modes": modes,
        "missing_info": missing_info,
        "assumptions": assumptions,
        "readiness_precheck": precheck,
        "mode_requirements": {
            mode: MODE_DEFINITIONS[mode].get("required_fields", []) for mode in modes["selected"]
        },
    }

    schema_errors = validate_campaign_state(state)
    if campaign_arms_enabled(state):
        state["readiness_precheck"] = {
            "status": "RED",
            "blocker_count": int(precheck["blocker_count"]) + 1,
            "warning_count": int(precheck["warning_count"]),
        }
        missing_info.append(
            {
                "field": "design_policy.active_factor_space",
                "severity": "blocker",
                "code": "active_factor_space_required",
                "reason": "Multi-arm campaign is preserved for per-arm DOE generation; flat executable DOE generation requires an active arm.",
            }
        )
    if schema_errors:
        if _is_materialization_blocked_state(schema_errors, materialization):
            state["schema_errors"] = schema_errors
        else:
            raise ValueError("invalid compiled campaign state: " + "; ".join(schema_errors))

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "campaign_state.json", state)
        write_json(out_dir / "missing_info.json", {"schema_version": 1, "items": missing_info})
    return state


def _is_materialization_blocked_state(schema_errors: list[str], materialization: dict[str, Any]) -> bool:
    allowed_errors = {"factors must be a non-empty list", "responses must be a non-empty list"}
    if any(error not in allowed_errors for error in schema_errors):
        return False
    issues = materialization.get("input_conflicts", [])
    if not issues:
        return False
    return any(
        issue.get("severity") == "blocker"
        or issue.get("code") in {"yaml_parser_unavailable", "unsupported_format", "parse_failed"}
        for issue in issues
    )


def extract_campaign_context(manifest: dict[str, Any]) -> dict[str, Any]:
    context_keys = [
        "current_format",
        "current_scale",
        "source_format",
        "source_scale",
        "target_format",
        "target_scale",
        "desired_format",
        "desired_scale",
        "scale_direction",
        "scale_transfer_direction",
        "experimental_setup",
        "setup_plan",
        "optimization_goals",
        "vessel",
        "working_volume_ml",
        "duration_h",
        "inoculum_basis",
        "oxygen_transfer",
        "pH_strategy",
        "foam_policy",
        "response_comparability",
        "phase_plan",
        "feed_composition",
        "feed_rate_policy",
        "induction_policy",
        "harvest_policy",
        "cost_limit",
        "run_duration_limit",
        "productivity_response",
        "sampling_burden_policy",
        "product_class",
        "assay_method",
        "sample_fraction",
        "standard_curve",
        "matrix_effects_policy",
    ]
    return {key: manifest[key] for key in context_keys if key in manifest}


def normalize_swarm_policy(raw: Any, enable_swarm: bool = False) -> dict[str, Any]:
    policy = raw if isinstance(raw, dict) else {}
    enabled = bool(policy.get("enabled", False) or enable_swarm)
    lanes = policy.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        lanes = [
            "literature_prior",
            "prior_data_source_trust",
            "protocol_vendor_methods",
            "assay_product_class_skeptic",
            "process_engineering_scale_transfer",
            "cost_runability_schedule",
        ]
    evidence_tables = policy.get("evidence_tables")
    if not isinstance(evidence_tables, list):
        evidence_tables = []
    control_fraction = parse_number(policy.get("control_row_max_fraction"))
    if control_fraction is None:
        control_fraction = 0.35
    control_fraction = max(0.0, min(0.75, float(control_fraction)))
    quality_minimum = parse_number(policy.get("evidence_quality_minimum"))
    if quality_minimum is None:
        quality_minimum = 0.7
    quality_minimum = max(0.0, min(1.0, float(quality_minimum)))
    return {
        "schema_version": 1,
        "policy_kind": "scientific_swarm_policy",
        "enabled": enabled,
        "dry_run_only": True,
        "max_parallel_w1_agents": int(policy.get("max_parallel_w1_agents") or 5),
        "max_parallel_w2_agents": int(policy.get("max_parallel_w2_agents") or 3),
        "lanes": [str(lane) for lane in lanes],
        "evidence_tables": [str(path) for path in evidence_tables],
        "apply_factor_universe_to_design": bool(policy.get("apply_factor_universe_to_design", enabled)),
        "use_swarm_for_tournament": bool(policy.get("use_swarm_for_tournament", enabled)),
        "control_row_augmentation": bool(policy.get("control_row_augmentation", enabled)),
        "control_row_max_fraction": control_fraction,
        "evidence_quality_minimum": quality_minimum,
        "activation": str(policy.get("activation") or ("cli_or_manifest" if enabled else "off_by_default")),
    }


def normalize_compute_policy(raw: Any) -> dict[str, Any]:
    policy = raw if isinstance(raw, dict) else {}
    default_profile = str(policy.get("default_profile") or "local-stdlib")
    approved_remote = str(policy.get("approved_remote_provider") or policy.get("blessed_remote_provider") or "external_adapter")
    profiles = policy.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        profiles = [
            {
                "profile_id": "local-stdlib",
                "provider": "local",
                "mode": "stdlib",
                "enabled": True,
                "launch_allowed": True,
            },
            {
                "profile_id": "approved-remote-dry-run",
                "provider": "external_adapter",
                "mode": "dry_run",
                "enabled": False,
                "launch_allowed": False,
            },
        ]
    normalized_profiles = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        normalized_profiles.append(
            {
                "profile_id": str(profile.get("profile_id") or profile.get("id") or ""),
                "provider": str(profile.get("provider") or "local"),
                "mode": str(profile.get("mode") or "stdlib"),
                "enabled": bool(profile.get("enabled", False)),
                "launch_allowed": bool(profile.get("launch_allowed", False)),
                "intended_jobs": profile.get("intended_jobs", []),
            }
        )
    if not any(profile["provider"] == "local" for profile in normalized_profiles):
        normalized_profiles.insert(
            0,
            {
                "profile_id": "local-stdlib",
                "provider": "local",
                "mode": "stdlib",
                "enabled": True,
                "launch_allowed": True,
                "intended_jobs": [],
            },
        )
    if not any(profile["provider"] != "local" for profile in normalized_profiles):
        normalized_profiles.append(
            {
                "profile_id": "approved-remote-dry-run",
                "provider": "external_adapter",
                "mode": "dry_run",
                "enabled": False,
                "launch_allowed": False,
                "intended_jobs": [],
            }
        )
    if not any(profile["profile_id"] == default_profile for profile in normalized_profiles):
        default_profile = "local-stdlib"
    return {
        "schema_version": 1,
        "policy_kind": "ferm_doe_compute_policy",
        "default_profile": default_profile,
        "approved_remote_provider": approved_remote,
        "remote_launch_policy": str(policy.get("remote_launch_policy") or "requires_explicit_operator_approval"),
        "profiles": normalized_profiles,
    }


def missing_information(
    manifest: dict[str, Any],
    factors: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    modes: dict[str, Any],
    manifest_path: Path,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not factors:
        items.append({"field": "factors", "severity": "blocker", "reason": "No controllable factors are defined."})
    if not responses:
        items.append({"field": "responses", "severity": "blocker", "reason": "No response is defined."})
    if not _input_exists(_find_input(inputs, ["ledger", "run"]), manifest_path):
        items.append({"field": "historical_run_ledger", "severity": "warning", "reason": "No historical run ledger was found."})
    if not _input_exists(_find_input(inputs, ["reagent"]), manifest_path):
        items.append({"field": "reagent_inventory", "severity": "warning", "reason": "No reagent inventory was found."})
    if not _input_exists(_find_input(inputs, ["equipment", "capacity"]), manifest_path):
        items.append({"field": "equipment_capacity", "severity": "warning", "reason": "No equipment capacity file was found."})

    for response in responses:
        if response_requires_assay(response) and response["sample_fraction"] == "unknown":
            items.append({
                "field": f"response:{response['response_id']}:sample_fraction",
                "severity": "warning",
                "reason": "Response sample fraction is not defined.",
            })
        if response_requires_assay(response) and response["assay_method"] == "unknown":
            items.append({
                "field": f"response:{response['response_id']}:assay_method",
                "severity": "warning",
                "reason": "Assay method is not defined.",
            })
        if not response_requires_assay(response) and response_has_lab_assay_method(response):
            items.append({
                "field": f"response:{response['response_id']}:assay_method",
                "severity": "warning",
                "reason": "Non-assay response has a lab assay method; use calculated, clock, schedule, derived, or not_applicable.",
            })

    selected = set(modes.get("selected", []))
    if "batch-to-fedbatch-production" in selected:
        for field in ["feed_composition", "feed_rate_policy", "induction_policy"]:
            if field not in manifest:
                items.append({"field": field, "severity": "warning", "reason": "Fed-batch mode needs this policy."})
    if "shake-flask-to-bioreactor" in selected:
        for field in ["vessel", "oxygen_transfer", "pH_strategy"]:
            if field not in manifest:
                items.append({"field": field, "severity": "warning", "reason": "Flask-to-bioreactor mode needs this transfer detail."})
    if "cost-productivity-minimizer" in selected and "cost_limit" not in manifest:
        items.append({"field": "cost_limit", "severity": "warning", "reason": "Cost/productivity mode needs a cost limit or cost model."})
    return items


def default_assumptions(
    manifest: dict[str, Any],
    factors: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    modes: dict[str, Any],
) -> list[str]:
    assumptions = [
        "Remote compute and Linear execution are dry-run only until explicitly requested.",
        "Remote compute providers are explicit adapters, not default execution paths.",
        "DOE recommendations require human scientific review before physical setup.",
    ]
    if factors:
        assumptions.append("Continuous factors without explicit levels use low/center/high values from manifest bounds.")
    if responses:
        assumptions.append("Primary response direction follows the campaign objective unless a response override is present.")
    if "assay-product-class-planner" in modes.get("selected", []):
        assumptions.append("Unknown product sample fraction is treated as a readiness caveat, not a safe default.")
    return assumptions
