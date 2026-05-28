"""Executable fermentation workflow-mode checks and objective hints."""

from __future__ import annotations

from typing import Any


MODE_CHECKS: dict[str, list[dict[str, Any]]] = {
    "shake-flask-to-bioreactor": [
        {"check": "controlled_ph_strategy", "fields": ["pH_strategy"], "risk": "pH drift removal is not captured."},
        {"check": "oxygen_transfer_basis", "fields": ["oxygen_transfer", "vessel"], "risk": "Oxygen transfer and DO control basis is incomplete."},
        {"check": "inoculum_basis", "fields": ["inoculum_basis"], "risk": "Inoculum normalization basis is missing."},
        {"check": "foam_policy", "fields": ["foam_policy", "antifoam_policy"], "risk": "Foam and antifoam policy is not defined."},
        {"check": "response_comparability", "fields": ["response_comparability"], "risk": "Flask and reactor response comparability is not documented."},
    ],
    "batch-to-fedbatch-production": [
        {"check": "phase_plan", "fields": ["phase_plan"], "risk": "Growth and production phases are not separated."},
        {"check": "feed_policy", "fields": ["feed_composition", "feed_rate_policy"], "risk": "Feed composition or feed-rate policy is missing."},
        {"check": "induction_policy", "fields": ["induction_policy"], "risk": "Induction or switch policy is missing."},
        {"check": "harvest_policy", "fields": ["harvest_policy"], "risk": "Harvest timing policy is missing."},
    ],
    "bioreactor-scale-up": [
        {"check": "oxygen_transfer_proxy", "fields": ["oxygen_transfer_proxy", "oxygen_transfer"], "risk": "kLa/OTR proxy is missing."},
        {"check": "mixing_proxy", "fields": ["mixing_proxy"], "risk": "Mixing or P/V proxy is missing."},
        {"check": "base_demand", "fields": ["base_demand_policy", "pH_strategy"], "risk": "pH/base demand policy is incomplete."},
        {"check": "foam_policy", "fields": ["foam_policy", "antifoam_policy"], "risk": "Foam policy is missing for scale transfer."},
    ],
    "bioreactor-to-plate-downscale": [
        {"check": "reference_behavior", "fields": ["reference_reactor_behavior"], "risk": "Reference reactor behavior is not defined."},
        {"check": "plate_geometry", "fields": ["plate_geometry"], "risk": "Plate geometry or fill-volume basis is missing."},
        {"check": "evaporation_policy", "fields": ["evaporation_policy"], "risk": "Evaporation and edge-effect policy is missing."},
        {"check": "scale_relevance", "fields": ["scale_relevance_score", "scale_relevance_policy"], "risk": "Scale relevance is not scored."},
    ],
    "plate-to-flask": [
        {"check": "plate_map", "fields": ["plate_map"], "risk": "Plate winner map is missing."},
        {"check": "flask_basis", "fields": ["flask_volume", "oxygen_transfer_assumption"], "risk": "Flask transfer basis is incomplete."},
        {"check": "confirmation_design", "fields": ["confirmation_design"], "risk": "Plate-to-flask confirmation design is missing."},
    ],
    "cost-productivity-minimizer": [
        {"check": "cost_limit", "fields": ["cost_limit"], "risk": "Cost limit or cost model is missing."},
        {"check": "duration_limit", "fields": ["run_duration_limit"], "risk": "Run-duration limit is missing."},
        {"check": "productivity_response", "fields": ["productivity_response"], "risk": "Productivity response is not explicitly defined."},
        {"check": "sampling_burden", "fields": ["sampling_burden_policy"], "risk": "Sampling burden is not priced or bounded."},
    ],
    "assay-product-class-planner": [
        {"check": "product_class", "fields": ["product_class"], "risk": "Product class is missing."},
        {"check": "assay_method", "fields": ["assay_method"], "risk": "Assay method is missing."},
        {"check": "sample_fraction", "fields": ["sample_fraction"], "risk": "Sample fraction is missing."},
        {"check": "standard_curve", "fields": ["standard_curve"], "risk": "Standard curve or calibration basis is missing."},
        {"check": "matrix_effects", "fields": ["matrix_effects_policy"], "risk": "Matrix-effects policy is missing."},
    ],
}


RESPONSE_CLASSES = {
    "titer",
    "productivity",
    "yield",
    "product_per_biomass",
    "quality",
    "activity",
    "cost",
    "duration",
    "run_duration",
    "time",
    "derived",
    "byproduct",
    "metabolite",
    "impurity",
    "growth",
}

SAMPLE_FRACTIONS = {
    "whole_broth",
    "whole_broth_or_pellet",
    "supernatant",
    "pellet",
    "intracellular",
    "intracellular_soluble",
    "clarified_lysate",
    "clarified_supernatant",
    "extracellular",
    "gas_phase",
    "volatile_capture",
    "not_applicable",
    "unknown",
}

NON_ASSAY_RESPONSE_CLASSES = {"cost", "duration", "run_duration", "time", "derived"}
NON_ASSAY_MEASUREMENT_TYPES = {"calculated", "computed", "derived", "schedule", "clock", "not_applicable"}
NON_ASSAY_METHODS = {
    "calculated",
    "computed",
    "derived",
    "derived_from_titer_time",
    "clock",
    "schedule",
    "not_applicable",
    "none",
    "null",
}
LAB_ASSAY_TOKENS = {
    "assay",
    "hplc",
    "lc",
    "gc",
    "elisa",
    "enzymatic",
    "uv",
    "ri",
    "ms",
    "spectro",
    "plate_reader",
}


def response_requires_assay(response: dict[str, Any]) -> bool:
    explicit = response.get("assay_required")
    if isinstance(explicit, bool):
        return explicit
    if isinstance(explicit, str) and explicit.strip().lower() in {"true", "false"}:
        return explicit.strip().lower() == "true"

    response_class = str(response.get("class") or "unknown").strip().lower()
    measurement_type = str(response.get("measurement_type") or "").strip().lower()
    assay_method = str(response.get("assay_method") or "unknown").strip().lower()

    if response_class in NON_ASSAY_RESPONSE_CLASSES:
        return False
    if measurement_type in NON_ASSAY_MEASUREMENT_TYPES:
        return False
    if assay_method in NON_ASSAY_METHODS:
        return False
    return True


def response_has_lab_assay_method(response: dict[str, Any]) -> bool:
    assay_method = str(response.get("assay_method") or "").strip().lower()
    if not assay_method or assay_method == "unknown" or assay_method in NON_ASSAY_METHODS:
        return False
    return any(token in assay_method for token in LAB_ASSAY_TOKENS)


def evaluate_workflow_modes(state: dict[str, Any]) -> dict[str, Any]:
    selected = state.get("workflow_modes", {}).get("selected", [])
    manifest_fields = set(state.get("manifest_fields", [])) | set(state)
    checks: list[dict[str, Any]] = []
    for mode in selected:
        for check in MODE_CHECKS.get(mode, []):
            present = [field for field in check["fields"] if field in manifest_fields]
            status = "PASS" if present else "WARN"
            checks.append(
                {
                    "mode": mode,
                    "check": check["check"],
                    "status": status,
                    "satisfied_by": present,
                    "risk": check["risk"] if status == "WARN" else "",
                }
            )
    objective_transforms = objective_hints(state)
    warnings = [item for item in checks if item["status"] != "PASS"]
    return {
        "schema_version": 1,
        "workflow_check_kind": "ferm_doe_workflow_mode_checks",
        "campaign_id": state.get("campaign_id"),
        "checks": checks,
        "warning_count": len(warnings),
        "objective_transforms": objective_transforms,
    }


def response_semantics_warnings(state: dict[str, Any]) -> list[dict[str, str]]:
    warnings = []
    for response in state.get("responses", []):
        response_id = response.get("response_id", "")
        response_class = str(response.get("class") or "unknown").lower()
        sample_fraction = str(response.get("sample_fraction") or "unknown").lower()
        if response_class not in RESPONSE_CLASSES and response_class != "unknown":
            warnings.append({"field": f"response:{response_id}:class", "message": f"Unrecognized response class {response_class}."})
        if sample_fraction not in SAMPLE_FRACTIONS:
            warnings.append({"field": f"response:{response_id}:sample_fraction", "message": f"Unrecognized sample fraction {sample_fraction}."})
        if not response_requires_assay(response) and response_has_lab_assay_method(response):
            warnings.append({"field": f"response:{response_id}:assay_method", "message": "Non-assay response is assigned a lab assay method; use calculated, clock, schedule, or not_applicable semantics instead."})
        if response_requires_assay(response) and sample_fraction == "not_applicable":
            warnings.append({"field": f"response:{response_id}:sample_fraction", "message": "Assayed response cannot use not_applicable sample fraction."})
        if "hydrophobic" in " ".join(str(value) for value in [state.get("objective"), response]).lower() and sample_fraction == "supernatant":
            warnings.append({"field": f"response:{response_id}:sample_fraction", "message": "Hydrophobic product may be pellet/cell-associated; supernatant-only response is risky."})
    return warnings


def objective_hints(state: dict[str, Any]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    selected = set(state.get("workflow_modes", {}).get("selected", []))
    if "cost-productivity-minimizer" in selected:
        hints.append({"objective": "productivity_cost_tradeoff", "transform": "score titer against run time, media/control cost, and sampling burden"})
    if "batch-to-fedbatch-production" in selected:
        hints.append({"objective": "phase_aware_design", "transform": "keep growth, switch, feed, production, and harvest factors phase-labeled"})
    if "assay-product-class-planner" in selected:
        hints.append({"objective": "response_semantics_gate", "transform": "block optimization if sample fraction, assay method, or calibration is unresolved"})
    if "bioreactor-to-plate-downscale" in selected:
        hints.append({"objective": "scale_relevance", "transform": "score cheaper scouting against representativeness of oxygen, evaporation, and mixing"})
    return hints
