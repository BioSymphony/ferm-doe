"""DoE family taxonomy and minimum-runs guidance. Conservative; deeper analysis is a statistician's job."""

from __future__ import annotations

from typing import Any


FAMILY_REGISTRY: dict[str, dict[str, Any]] = {
    "definitive_screening": {
        "description": "Definitive Screening Design (Jones & Nachtsheim 2011). Active main effects + quadratic curvature in very few runs.",
        "min_runs_formula": "2*k + 1",
        "supports_quadratic": True,
        "supports_two_factor_interactions": "partial",
        "requires_resolution": False,
        "expects_center_points": False,
        "typical_use": "screening up to ~10 numeric factors when curvature is plausible",
    },
    "plackett_burman": {
        "description": "Plackett-Burman screening for main effects only.",
        "min_runs_formula": "next_multiple_of_4(k+1)",
        "supports_quadratic": False,
        "supports_two_factor_interactions": False,
        "requires_resolution": True,
        "expects_resolution": "III",
        "expects_center_points": False,
        "typical_use": "very-low-resource screening for main effects",
    },
    "fractional_factorial": {
        "description": "2-level fractional factorial. Resolution determines aliasing.",
        "min_runs_formula": "2**(k - p)",
        "supports_quadratic": False,
        "supports_two_factor_interactions": "depends_on_resolution",
        "requires_resolution": True,
        "expects_alias_structure": True,
        "expects_center_points": "advised",
        "typical_use": "screening to optimization handoff with k=4..8 factors",
    },
    "full_factorial": {
        "description": "All factor combinations.",
        "min_runs_formula": "product(levels_per_factor)",
        "supports_quadratic": "depends_on_levels",
        "supports_two_factor_interactions": True,
        "requires_resolution": False,
        "expects_center_points": "advised",
        "typical_use": "≤4 factors or categorical-heavy designs",
    },
    "central_composite": {
        "description": "CCD = factorial + axial + center points; full quadratic.",
        "min_runs_formula": "2**k + 2*k + n_center",
        "supports_quadratic": True,
        "supports_two_factor_interactions": True,
        "requires_resolution": False,
        "expects_center_points": True,
        "min_center_points": 3,
        "typical_use": "RSM optimization after screening",
    },
    "box_behnken": {
        "description": "BBD: rotatable, no axial points outside the cube; full quadratic.",
        "min_runs_formula": "2*k*(k-1) + n_center",
        "supports_quadratic": True,
        "supports_two_factor_interactions": True,
        "requires_resolution": False,
        "expects_center_points": True,
        "min_center_points": 3,
        "typical_use": "RSM when corner points are infeasible",
    },
    "optimal_d": {
        "description": "D-optimal computer-generated design.",
        "min_runs_formula": "model_terms + n_center",
        "supports_quadratic": "model_dependent",
        "supports_two_factor_interactions": "model_dependent",
        "requires_resolution": False,
        "expects_center_points": "advised",
        "typical_use": "constrained factor space, irregular regions, augmentation",
    },
    "optimal_i": {
        "description": "I-optimal computer-generated design (minimizes prediction variance).",
        "min_runs_formula": "model_terms + n_center",
        "supports_quadratic": "model_dependent",
        "supports_two_factor_interactions": "model_dependent",
        "requires_resolution": False,
        "expects_center_points": "advised",
        "typical_use": "RSM where prediction over the design region matters",
    },
    "scheffe_mixture": {
        "description": "Scheffé canonical mixture design.",
        "min_runs_formula": "C(q + m - 1, m)",
        "supports_quadratic": "depends_on_order",
        "supports_two_factor_interactions": "blend_terms",
        "requires_resolution": False,
        "requires_mixture_factors": True,
        "expects_center_points": "advised",
        "typical_use": "blend optimization where components sum to 1",
    },
    "extreme_vertices_mixture": {
        "description": "Extreme-vertices mixture for constrained component ranges.",
        "min_runs_formula": "vertex_count + edge_or_face_replicates",
        "requires_mixture_factors": True,
        "expects_constraints": True,
        "typical_use": "mixture with lower/upper bounds on each component",
    },
    "split_plot": {
        "description": "Split-plot for hard-to-change vs easy-to-change factors.",
        "min_runs_formula": "n_whole_plots * n_subplots_per_plot",
        "requires_hard_to_change_factors": True,
        "expects_whole_plot_replication": True,
        "typical_use": "fed-batch where temperature/feed/DO are hard-to-change and media composition is easy-to-change",
    },
    "custom_constrained": {
        "description": "Custom design honoring hard constraints. No standard formula.",
        "min_runs_formula": "user_declared",
        "expects_alias_structure": "advised",
        "typical_use": "irregular factor spaces, regulatory-bounded regions",
    },
    "sequential_augmentation": {
        "description": "Augmentation of a prior wave's design.",
        "min_runs_formula": "user_declared",
        "requires_previous_wave_ref": True,
        "typical_use": "follow-up after first-batch narrows or confirms",
    },
}


def list_families() -> list[str]:
    return sorted(FAMILY_REGISTRY.keys())


def family_info(name: str) -> dict[str, Any] | None:
    return FAMILY_REGISTRY.get(name)


def minimum_runs(family: str, k_factors: int, **kwargs: Any) -> int | None:
    """Conservative minimum-runs estimate, or None when it depends on user-declared parameters."""
    info = FAMILY_REGISTRY.get(family)
    if not info:
        return None
    if family == "definitive_screening":
        return 2 * k_factors + 1
    if family == "plackett_burman":
        n = k_factors + 1
        return n + (4 - n % 4) % 4 if n > 0 else 4
    if family == "fractional_factorial":
        p = kwargs.get("p", 0)
        return 2 ** (k_factors - p) if k_factors - p >= 1 else None
    if family == "full_factorial":
        levels = kwargs.get("levels_per_factor")
        if isinstance(levels, list) and levels:
            product = 1
            for level in levels:
                product *= int(level)
            return product
        return 2 ** k_factors
    if family == "central_composite":
        n_center = kwargs.get("n_center", 3)
        return (2 ** k_factors) + (2 * k_factors) + n_center
    if family == "box_behnken":
        n_center = kwargs.get("n_center", 3)
        if k_factors < 3:
            return None
        return 2 * k_factors * (k_factors - 1) + n_center
    return None
