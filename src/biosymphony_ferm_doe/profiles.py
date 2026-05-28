"""Profile registry. Profiles are composable; advised items emit warnings, required_blocks emit errors."""

from __future__ import annotations

from typing import Any


PROFILE_REGISTRY: dict[str, dict[str, Any]] = {
    "screening": {
        "description": "First-pass DoE to identify active factors. Permissive on responses and factor count.",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["selected_wave_1_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "decision_rules", "stop_rules"],
        "required_blocks": [],
        "advised_doe_families": ["definitive_screening", "plackett_burman", "fractional_factorial"],
        "minimum_factor_count": 2,
    },
    "optimization_rsm": {
        "description": "Response surface to locate an optimum after screening identifies active factors.",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["selected_wave_1_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "decision_rules"],
        "required_blocks": ["responses", "factors"],
        "advised_doe_families": ["central_composite", "box_behnken", "optimal_i"],
        "minimum_factor_count": 2,
    },
    "mixture": {
        "description": "Mixture / blend optimization. Components sum to 1.0.",
        "advised_inputs": ["evidence_table"],
        "advised_expected": ["selected_wave_1_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors"],
        "required_blocks": ["factors"],
        "advised_doe_families": ["scheffe_mixture", "extreme_vertices_mixture"],
        "factor_type_required_at_least_one": "mixture",
    },
    "split_plot_fed_batch": {
        "description": "Fed-batch with hard-to-change setpoints (whole-plot) and easy-to-change media (sub-plot).",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["selected_wave_1_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "decision_rules", "risk_register"],
        "required_blocks": ["responses", "factors"],
        "advised_doe_families": ["split_plot"],
        "factor_hard_to_change_required": True,
    },
    "scale_up_bridge": {
        "description": "Plan a scale-up. scale_context is required; two-arm structure (reference + target) is strongly advised.",
        "advised_inputs": ["historical_run_ledger", "equipment_inventory", "evidence_table"],
        "advised_expected": ["run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "arms", "decision_rules", "risk_register"],
        "required_blocks": ["scale_context"],
        "advised_doe_families": ["definitive_screening", "central_composite", "box_behnken"],
        "scale_direction_required": "scale_up",
    },
    "scale_down_qualification": {
        "description": "Build a small-scale model that recapitulates a larger scale. recapitulation_criterion is required.",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "scale_context", "arms", "risk_register"],
        "required_blocks": ["scale_context"],
        "advised_doe_families": ["full_factorial", "definitive_screening"],
        "scale_direction_required": "scale_down",
        "recapitulation_criterion_required": True,
    },
    "confirmation": {
        "description": "Confirmation runs after optimization to verify the predicted optimum.",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["selected_wave_1_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "decision_rules"],
        "required_blocks": [],
        "advised_doe_families": ["custom_constrained", "full_factorial"],
    },
    "sequential_augmentation": {
        "description": "Augment a prior wave's design with new runs informed by prior results.",
        "advised_inputs": ["historical_run_ledger", "evidence_table"],
        "advised_expected": ["selected_wave_2_design.csv", "run_packet.md", "AGENTS.md"],
        "advised_blocks": ["responses", "factors", "doe", "waves", "decision_rules"],
        "required_blocks": ["doe"],
        "advised_doe_families": ["sequential_augmentation", "optimal_d", "optimal_i"],
        "previous_wave_ref_required": True,
    },
    "custom": {
        "description": "Free-form. No structural requirements; agent fills the right slots for the situation.",
        "advised_inputs": [],
        "advised_expected": ["AGENTS.md"],
        "advised_blocks": ["responses"],
        "required_blocks": [],
        "advised_doe_families": [],
    },
}


DEFAULT_PROFILE = "custom"


PUBLIC_SAFETY_RULES: dict[str, Any] = {
    "claim_level_value": "public_synthetic_demo",
    "privacy_value": "synthetic_or_public_only",
    "required_inputs": ["historical_run_ledger", "evidence_table"],
    "advised_inputs": ["equipment_inventory", "reagent_inventory"],
    "required_expected": ["readiness_summary.json", "AGENTS.md"],
    "advised_expected": ["selected_wave_1_design.csv", "run_packet.md"],
    "public_source_types": {
        "public_literature",
        "public_literature_placeholder",
        "paper_numeric",
        "public_database",
        "synthetic_demo",
        "synthetic_demo_note",
    },
}


def resolve_profiles(declared: list[str] | None) -> list[str]:
    """Return profile names to evaluate. Falls back to DEFAULT_PROFILE."""
    if not declared:
        return [DEFAULT_PROFILE]
    resolved = [name for name in declared if name in PROFILE_REGISTRY]
    return resolved or [DEFAULT_PROFILE]


def merge_advised_inputs(profiles: list[str]) -> list[str]:
    """Union the advised inputs across the given profiles."""
    out: list[str] = []
    for name in profiles:
        for item in PROFILE_REGISTRY[name].get("advised_inputs", []):
            if item not in out:
                out.append(item)
    return out


def merge_advised_expected(profiles: list[str]) -> list[str]:
    """Union the advised expected artifacts across the given profiles."""
    out: list[str] = []
    for name in profiles:
        for item in PROFILE_REGISTRY[name].get("advised_expected", []):
            if item not in out:
                out.append(item)
    return out


def merge_required_blocks(profiles: list[str]) -> list[str]:
    """Union the required manifest blocks across the given profiles."""
    out: list[str] = []
    for name in profiles:
        for item in PROFILE_REGISTRY[name].get("required_blocks", []):
            if item not in out:
                out.append(item)
    return out


def merge_advised_blocks(profiles: list[str]) -> list[str]:
    """Union the advised manifest blocks across the given profiles."""
    out: list[str] = []
    for name in profiles:
        for item in PROFILE_REGISTRY[name].get("advised_blocks", []):
            if item not in out:
                out.append(item)
    return out
