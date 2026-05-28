"""Workflow mode definitions and selection heuristics."""

from __future__ import annotations

import re
from typing import Any


MODE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "autonomous-multi-agent-doe-planner": {
        "description": "Default multi-lane DoE planning and adjudication.",
        "required_fields": ["objective", "responses", "factors"],
        "guardrails": [
            "generate competing design strategies",
            "include skeptical audit",
            "score feasibility before statistical optimality",
        ],
    },
    "reference-doe-engine": {
        "description": "Fast path for users who expect familiar commercial DOE mechanics plus Ferm DoE campaign intelligence.",
        "keywords": [
            "reference doe",
            "commercial doe",
            "custom design",
            "definitive screening",
            "dsd",
            "d-optimal",
            "i-optimal",
            "augment design",
            "bayesian optimization",
            "prediction profiler",
            "mixture design",
        ],
        "required_fields": ["factor_model", "model_terms", "design_policy", "constraints"],
        "guardrails": [
            "produce reference DOE diagnostics and a parity report",
            "explain when BioSymphony is not yet at commercial DOE statistical parity",
            "score fermentation readiness before selecting a statistically attractive design",
            "emit exportable design tables and reproducible seeds",
        ],
    },
    "shake-flask-to-bioreactor": {
        "description": "Translate flask process assumptions into controlled bioreactor runs.",
        "keywords": ["shake", "flask", "bioreactor", "reactor", "2l", "2 l", "benchtop"],
        "required_fields": ["vessel", "inoculum_basis", "oxygen_transfer", "pH_strategy"],
        "guardrails": [
            "pH drift removal",
            "oxygen transfer and DO control",
            "inoculum basis",
            "foam and antifoam policy",
            "response comparability",
        ],
    },
    "batch-to-fedbatch-production": {
        "description": "Separate growth and production phases with feed and induction policies.",
        "keywords": ["fed-batch", "fed batch", "induce", "induction", "production phase", " batch "],
        "required_fields": ["phase_plan", "feed_composition", "feed_rate_policy", "induction_policy"],
        "guardrails": [
            "separate growth and production factor spaces",
            "feed start trigger",
            "feed rate and profile bounds",
            "harvest timing",
        ],
    },
    "bioreactor-scale-up": {
        "description": "Plan transfer from one bioreactor scale to another.",
        "keywords": ["scale up", "scale-up", "larger scale", "pilot", "production scale"],
        "required_fields": ["source_vessel", "target_vessel", "mixing_proxy", "oxygen_transfer_proxy"],
        "guardrails": ["kLa/OTR proxy", "P/V", "tip speed", "mixing", "base demand", "foam"],
    },
    "bioreactor-to-plate-downscale": {
        "description": "Create a cheaper plate or deep-well scouting route from reactor behavior.",
        "keywords": ["downscale", "plate", "deep-well", "microplate", "96 well", "24 well"],
        "required_fields": ["reference_reactor_behavior", "plate_geometry", "evaporation_policy"],
        "guardrails": ["evaporation", "edge effects", "oxygen", "fill volume", "mixing", "scale relevance"],
    },
    "plate-to-flask": {
        "description": "Translate plate or deep-well winners into shake flask confirmation.",
        "keywords": ["plate to flask", "deep-well to flask", "plate winner"],
        "required_fields": ["plate_map", "flask_volume", "oxygen_transfer_assumption"],
        "guardrails": ["oxygen transfer", "evaporation", "inoculum normalization", "confirmation design"],
    },
    "cost-productivity-minimizer": {
        "description": "Optimize titer, productivity, time, and cost tradeoffs.",
        "keywords": ["cost", "$", "productivity", "yield", "shorter", "earlier", "per liter", "per l"],
        "required_fields": ["cost_limit", "run_duration_limit", "productivity_response"],
        "guardrails": ["cost per liter", "run duration", "sampling burden", "early harvest economics"],
    },
    "assay-product-class-planner": {
        "description": "Validate response semantics and product-class assay risks before DoE.",
        "keywords": [
            "assay",
            "titer",
            "hydrophobic",
            "intracellular",
            "extracellular",
            "pellet",
            "volatile",
            "activity",
            "quality",
        ],
        "required_fields": ["product_class", "assay_method", "sample_fraction", "standard_curve"],
        "guardrails": [
            "whole-broth vs supernatant vs pellet",
            "dynamic range",
            "matrix effects",
            "sample stability",
            "turnaround time",
        ],
    },
}


def manifest_text(manifest: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["name", "readiness_target"]:
        parts.append(str(manifest.get(key, "")))
    objective = manifest.get("objective")
    if isinstance(objective, dict):
        parts.extend(str(value) for value in objective.values())
    for section in ["constraints", "responses", "factors", "inputs", "sources"]:
        value = manifest.get(section, [])
        if isinstance(value, list):
            for item in value:
                parts.append(str(item))
    return " ".join(parts).lower()


def select_modes(manifest: dict[str, Any], requested: list[str] | None = None) -> dict[str, Any]:
    requested = requested or []
    text = manifest_text(manifest)
    selected = ["autonomous-multi-agent-doe-planner"]
    rationale: dict[str, str] = {
        "autonomous-multi-agent-doe-planner": "Default planner mode for every Ferm DoE campaign."
    }

    for mode, definition in MODE_DEFINITIONS.items():
        if mode == "autonomous-multi-agent-doe-planner":
            continue
        if mode in requested:
            selected.append(mode)
            rationale[mode] = "Requested explicitly."
            continue
        keywords = [str(item).lower() for item in definition.get("keywords", [])]
        if any(_keyword_matches(text, keyword) for keyword in keywords):
            selected.append(mode)
            rationale[mode] = "Selected from campaign text and input metadata."

    skipped = {
        mode: "No strong campaign signal and not explicitly requested."
        for mode in MODE_DEFINITIONS
        if mode not in selected
    }
    return {
        "selected": selected,
        "rationale": rationale,
        "skipped": skipped,
        "definitions": {mode: MODE_DEFINITIONS[mode] for mode in selected},
    }


def _keyword_matches(text: str, keyword: str) -> bool:
    keyword = keyword.strip()
    if not keyword:
        return False
    if " " in keyword or "-" in keyword:
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
