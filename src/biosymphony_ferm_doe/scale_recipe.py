"""Scale-bridge engineering recipe derivation.

Given a campaign manifest's ``scale_context`` block, derive runnable engineering
setpoints at both ``from_scale`` and ``to_scale``: agitation RPM, sparge / gas
flow rate, agitator power input, tip speed, mix time, and the resulting kLa.
Each derived line records which correlation drove it and which inputs were
declared vs. preset-defaulted vs. operator-overridden.

The output is a *planning recipe*, not a validated transfer. The skill labels
the result ``claim_level: engineering_recipe_planned`` so downstream tooling
knows to treat it as a starting point that must be qualified with vessel
characterization data before physical execution.

Public API: :func:`compute_scale_recipe`, :func:`render_recipe_markdown`.

Correlations:

- **kLa (Van't Riet 1979).** Coalescing systems (water-like): ``kLa [1/s] =
  0.026 * (P/V)^0.4 * v_s^0.5``. Non-coalescing systems (electrolyte / high-
  ionic media): ``kLa [1/s] = 0.002 * (P/V)^0.7 * v_s^0.2``. Coefficients
  are organism-class presets and can be overridden per scale endpoint.
- **Power input.** Turbulent stirred tank: ``P = N_p * rho * N^3 * D^5``.
  Power number ``N_p`` defaults to the impeller-type table below. Total
  power is divided across ``n_impellers`` per scale endpoint.
- **Tip speed.** ``v_tip = pi * D_imp * N``.
- **Mix time (Nienow).** ``t_m = c_m / N`` for a single Rushton; multi-impeller
  vessels are not corrected here, so the value is treated as a lower bound.
- **Geometric similarity.** Vessel diameter is solved from working volume
  and ``h_over_d``; impeller diameter from ``impeller_d_over_t``.

Power numbers (turbulent regime) and mix-time coefficients are tabulated for
common impellers below. Operators with vessel-specific data should override
via ``scale_context.correlation_overrides`` (per scale) or by setting
``engineering_targets.power_number`` / ``engineering_targets.mix_time_constant``
directly on the endpoint.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

CLAIM_LEVEL = "engineering_recipe_planned"
NON_CLAIM = (
    "Engineering recipe is a planning starting point. Vessel kLa-vs-RPM, "
    "power-number, and mix-time correlations must be qualified with characterization "
    "runs before this recipe drives physical execution."
)


# Power numbers in the turbulent regime per impeller type. Conservative published
# values; operators with rig-specific characterization should override.
_POWER_NUMBERS: dict[str, float] = {
    "rushton": 5.5,
    "rushton_disc": 5.5,
    "pitched_blade": 1.27,
    "pbt": 1.27,
    "marine": 0.35,
    "marine_propeller": 0.35,
    "lightnin_a310": 0.30,
    "lightnin_a315": 0.84,
    "elephant_ear": 0.50,
    "axial": 0.40,
    "default": 1.0,
}


# Mix-time constants (Nienow) — N * t_m for that impeller type.
_MIX_TIME_CONSTANTS: dict[str, float] = {
    "rushton": 5.4,
    "rushton_disc": 5.4,
    "pitched_blade": 4.0,
    "pbt": 4.0,
    "marine": 3.6,
    "marine_propeller": 3.6,
    "lightnin_a310": 3.5,
    "lightnin_a315": 3.5,
    "axial": 3.6,
    "default": 5.0,
}


# Van't Riet kLa correlation coefficients per organism-class preset.
# kLa [1/s] = c * (P/V [W/m^3])^a * (v_s [m/s])^b
_KLA_CORRELATIONS: dict[str, dict[str, float]] = {
    "microbial_coalescing": {"c": 0.026, "a": 0.4, "b": 0.5, "source": "vant_riet_1979_coalescing"},
    "microbial_non_coalescing": {"c": 0.002, "a": 0.7, "b": 0.2, "source": "vant_riet_1979_non_coalescing"},
    "yeast": {"c": 0.026, "a": 0.4, "b": 0.5, "source": "vant_riet_1979_coalescing"},
    "mammalian_shear_sensitive": {"c": 0.0018, "a": 0.5, "b": 0.3, "source": "literature_blend_for_low_shear_systems"},
    "default": {"c": 0.026, "a": 0.4, "b": 0.5, "source": "vant_riet_1979_coalescing"},
}


def compute_scale_recipe(manifest: dict[str, Any]) -> dict[str, Any]:
    """Derive engineering setpoints at from_scale and to_scale.

    Reads ``scale_context`` from the manifest. Picks an organism preset from
    ``scale_context.organism_class`` (falling back to ``manifest.system.organism_class``
    or a coalescing default). Solves for RPM, sparge rate, agitator power,
    tip speed, mix time, and kLa at both endpoints; records which correlation
    drove each line.
    """
    scale_context = manifest.get("scale_context") or {}
    if not scale_context:
        raise ValueError("manifest_missing_scale_context")
    from_scale = scale_context.get("from_scale") or {}
    to_scale = scale_context.get("to_scale") or {}
    if not from_scale or not to_scale:
        raise ValueError("scale_context_requires_from_scale_and_to_scale")

    bridge = scale_context.get("bridge_strategy") or {}
    primary_criterion = bridge.get("primary_criterion", "kLa")
    secondary_criteria = bridge.get("secondary_criteria") or []

    organism_class = (
        scale_context.get("organism_class")
        or (manifest.get("system") or {}).get("organism_class")
        or "microbial_coalescing"
    )
    correlation = dict(_KLA_CORRELATIONS.get(organism_class, _KLA_CORRELATIONS["default"]))
    correlation["organism_class"] = organism_class

    overrides = scale_context.get("correlation_overrides") or {}
    if isinstance(overrides.get("kla"), dict):
        for key in ("c", "a", "b"):
            if key in overrides["kla"]:
                correlation[key] = float(overrides["kla"][key])
                correlation["source"] = "operator_override"

    from_recipe = _derive_setpoints(from_scale, correlation, label="from_scale")
    to_recipe = _derive_setpoints(to_scale, correlation, label="to_scale")

    criterion_match = _criterion_match(from_recipe, to_recipe, primary_criterion)
    secondary_match = [
        _criterion_match(from_recipe, to_recipe, criterion) for criterion in secondary_criteria
    ]

    warnings: list[str] = []
    warnings.extend(from_recipe.get("warnings", []))
    warnings.extend(to_recipe.get("warnings", []))
    if criterion_match["status"] != "MATCH":
        warnings.append(
            f"primary_criterion_{primary_criterion}_off_by_{criterion_match['delta_pct']:.1f}_pct"
        )

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "primary_criterion": primary_criterion,
        "secondary_criteria": secondary_criteria,
        "organism_class": correlation["organism_class"],
        "kla_correlation": {k: correlation[k] for k in ("c", "a", "b", "source")},
        "from_scale": _public_endpoint(from_scale, from_recipe),
        "to_scale": _public_endpoint(to_scale, to_recipe),
        "criterion_match": criterion_match,
        "secondary_match": secondary_match,
        "warnings": warnings,
    }


def render_recipe_markdown(recipe: dict[str, Any]) -> str:
    """Render the recipe as a markdown document for run-packet handoff."""
    lines: list[str] = []
    lines.append("# Scale-bridge engineering recipe")
    lines.append("")
    lines.append(f"- Claim level: `{recipe['claim_level']}`")
    lines.append(f"- Primary criterion: `{recipe['primary_criterion']}`")
    lines.append(f"- Organism class: `{recipe['organism_class']}`")
    cor = recipe["kla_correlation"]
    lines.append(
        f"- kLa correlation: `c={cor['c']}, a={cor['a']}, b={cor['b']}` "
        f"(source: `{cor['source']}`)"
    )
    lines.append("")
    lines.append(f"> {recipe['non_claim']}")
    lines.append("")
    lines.append("## from_scale")
    lines.append("")
    lines.extend(_endpoint_markdown(recipe["from_scale"]))
    lines.append("")
    lines.append("## to_scale")
    lines.append("")
    lines.extend(_endpoint_markdown(recipe["to_scale"]))
    lines.append("")
    match = recipe["criterion_match"]
    lines.append("## Criterion match")
    lines.append("")
    lines.append(
        f"- `{match['criterion']}` from={match['from_value']:.4g} → "
        f"to={match['to_value']:.4g} (delta={match['delta_pct']:.1f} %, "
        f"status=**{match['status']}**)"
    )
    if recipe["secondary_match"]:
        lines.append("")
        lines.append("### Secondary criteria")
        lines.append("")
        for sub in recipe["secondary_match"]:
            lines.append(
                f"- `{sub['criterion']}` from={sub['from_value']:.4g} → "
                f"to={sub['to_value']:.4g} (delta={sub['delta_pct']:.1f} %, "
                f"status={sub['status']})"
            )
    if recipe["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for warn in recipe["warnings"]:
            lines.append(f"- `{warn}`")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Internals
# =====================================================================


def _derive_setpoints(
    scale: dict[str, Any], correlation: dict[str, Any], *, label: str
) -> dict[str, Any]:
    """Solve for RPM / sparge / power / kLa at one scale endpoint."""
    geometry = scale.get("geometry") or {}
    targets = scale.get("engineering_targets") or {}
    overrides = scale.get("correlation_overrides") or {}

    working_volume_l = float(scale["working_volume_l"])
    working_volume_m3 = working_volume_l / 1000.0
    h_over_d = float(geometry.get("h_over_d", 2.0))
    d_over_t = float(geometry.get("impeller_d_over_t", 0.4))
    n_impellers = int(geometry.get("n_impellers", 1))
    impeller_type = (geometry.get("impeller_type") or "default").lower()

    declared_power_number = overrides.get("power_number") or targets.get("power_number")
    if declared_power_number is not None:
        power_number = float(declared_power_number)
        power_number_source = "declared"
    else:
        power_number = _POWER_NUMBERS.get(impeller_type, _POWER_NUMBERS["default"])
        power_number_source = f"preset_{impeller_type}"

    declared_mix_constant = overrides.get("mix_time_constant") or targets.get("mix_time_constant")
    if declared_mix_constant is not None:
        mix_constant = float(declared_mix_constant)
        mix_constant_source = "declared"
    else:
        mix_constant = _MIX_TIME_CONSTANTS.get(impeller_type, _MIX_TIME_CONSTANTS["default"])
        mix_constant_source = f"preset_{impeller_type}"

    rho = float(overrides.get("liquid_density_kg_per_m3", 1000.0))

    tank_diameter_m = (4 * working_volume_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
    impeller_diameter_m = tank_diameter_m * d_over_t
    cross_section_m2 = math.pi * (tank_diameter_m / 2.0) ** 2

    vvm = float(targets.get("vvm", 1.0))
    gas_flow_m3_per_min = vvm * working_volume_m3
    gas_flow_l_per_min = gas_flow_m3_per_min * 1000.0
    superficial_gas_velocity_m_per_s = gas_flow_m3_per_min / 60.0 / cross_section_m2

    declared_kla = targets.get("kLa_per_hour")
    declared_p_per_v = targets.get("p_per_v_w_per_m3")

    warnings: list[str] = []

    if declared_kla is not None:
        kla_per_s = float(declared_kla) / 3600.0
        c, a, b = correlation["c"], correlation["a"], correlation["b"]
        if superficial_gas_velocity_m_per_s <= 0:
            raise ValueError(f"{label}_superficial_gas_velocity_must_be_positive")
        denom = c * (superficial_gas_velocity_m_per_s ** b)
        if denom <= 0:
            raise ValueError(f"{label}_kla_correlation_inputs_invalid")
        p_per_v = (kla_per_s / denom) ** (1.0 / a)
        p_per_v_source = f"solved_from_kLa_target_via_{correlation['source']}"
        kla_target_per_hour = float(declared_kla)
        if declared_p_per_v is not None:
            ratio = abs(p_per_v - float(declared_p_per_v)) / max(float(declared_p_per_v), 1e-9)
            if ratio > 0.2:
                warnings.append(
                    f"{label}_solved_p_per_v_{p_per_v:.0f}_disagrees_with_declared_{declared_p_per_v}_by_{ratio*100:.0f}_pct"
                )
    elif declared_p_per_v is not None:
        p_per_v = float(declared_p_per_v)
        p_per_v_source = "declared"
        c, a, b = correlation["c"], correlation["a"], correlation["b"]
        kla_per_s = c * (p_per_v ** a) * (superficial_gas_velocity_m_per_s ** b)
        kla_target_per_hour = kla_per_s * 3600.0
    else:
        raise ValueError(f"{label}_engineering_targets_must_declare_kLa_per_hour_or_p_per_v_w_per_m3")

    power_total_w = p_per_v * working_volume_m3
    power_per_impeller_w = power_total_w / max(n_impellers, 1)

    if power_per_impeller_w <= 0:
        raise ValueError(f"{label}_solved_negative_or_zero_power_check_targets")
    n_rev_per_s_cubed = power_per_impeller_w / (power_number * rho * impeller_diameter_m ** 5)
    if n_rev_per_s_cubed <= 0:
        raise ValueError(f"{label}_solved_negative_rotational_speed_cubed_check_inputs")
    n_rev_per_s = n_rev_per_s_cubed ** (1.0 / 3.0)
    rpm = n_rev_per_s * 60.0
    tip_speed_m_per_s = math.pi * impeller_diameter_m * n_rev_per_s
    mix_time_s = mix_constant / n_rev_per_s if n_rev_per_s > 0 else float("inf")

    declared_rpm = targets.get("rpm")
    if declared_rpm is not None:
        ratio = abs(rpm - float(declared_rpm)) / max(float(declared_rpm), 1e-9)
        if ratio > 0.2:
            warnings.append(
                f"{label}_solved_rpm_{rpm:.0f}_disagrees_with_declared_{declared_rpm}_by_{ratio*100:.0f}_pct"
            )

    declared_tip_speed = targets.get("tip_speed_m_per_s")
    if declared_tip_speed is not None:
        ratio = abs(tip_speed_m_per_s - float(declared_tip_speed)) / max(float(declared_tip_speed), 1e-9)
        if ratio > 0.25:
            warnings.append(
                f"{label}_solved_tip_speed_{tip_speed_m_per_s:.2f}_disagrees_with_declared_{declared_tip_speed}_by_{ratio*100:.0f}_pct"
            )

    return {
        "tank_diameter_m": round(tank_diameter_m, 4),
        "impeller_diameter_m": round(impeller_diameter_m, 4),
        "n_impellers": n_impellers,
        "impeller_type": impeller_type,
        "power_number": round(power_number, 3),
        "power_number_source": power_number_source,
        "mix_time_constant": round(mix_constant, 3),
        "mix_time_constant_source": mix_constant_source,
        "liquid_density_kg_per_m3": round(rho, 1),
        "vvm": round(vvm, 3),
        "gas_flow_l_per_min": round(gas_flow_l_per_min, 3),
        "superficial_gas_velocity_m_per_s": round(superficial_gas_velocity_m_per_s, 5),
        "agitation_rpm": round(rpm, 1),
        "tip_speed_m_per_s": round(tip_speed_m_per_s, 3),
        "mix_time_s": round(mix_time_s, 3),
        "agitator_power_total_w": round(power_total_w, 3),
        "agitator_power_per_impeller_w": round(power_per_impeller_w, 3),
        "p_per_v_w_per_m3": round(p_per_v, 1),
        "p_per_v_source": p_per_v_source,
        "kla_per_hour": round(kla_target_per_hour, 1),
        "warnings": warnings,
    }


def _public_endpoint(scale_input: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": scale_input.get("label"),
        "vessel": scale_input.get("vessel"),
        "working_volume_l": scale_input.get("working_volume_l"),
        "geometry": scale_input.get("geometry"),
        "declared_engineering_targets": scale_input.get("engineering_targets") or {},
        "derived_setpoints": {k: v for k, v in recipe.items() if k != "warnings"},
    }


def _criterion_match(
    from_recipe: dict[str, Any], to_recipe: dict[str, Any], criterion: str
) -> dict[str, Any]:
    key = _criterion_to_key(criterion)
    if key is None:
        return {
            "criterion": criterion,
            "status": "UNAVAILABLE",
            "from_value": float("nan"),
            "to_value": float("nan"),
            "delta_pct": float("nan"),
            "reason": f"criterion_{criterion}_not_in_recipe_output",
        }
    from_value = float(from_recipe[key])
    to_value = float(to_recipe[key])
    if from_value == 0:
        delta_pct = float("inf") if to_value != 0 else 0.0
    else:
        delta_pct = (to_value - from_value) / from_value * 100.0
    if abs(delta_pct) <= 5:
        status = "MATCH"
    elif abs(delta_pct) <= 20:
        status = "INFO"
    else:
        status = "OFF"
    return {
        "criterion": criterion,
        "status": status,
        "from_value": from_value,
        "to_value": to_value,
        "delta_pct": delta_pct,
    }


def _criterion_to_key(criterion: str) -> str | None:
    mapping = {
        "kla": "kla_per_hour",
        "kla_per_hour": "kla_per_hour",
        "p_per_v": "p_per_v_w_per_m3",
        "p_per_v_w_per_m3": "p_per_v_w_per_m3",
        "tip_speed": "tip_speed_m_per_s",
        "tip_speed_m_per_s": "tip_speed_m_per_s",
        "mix_time": "mix_time_s",
        "mix_time_s": "mix_time_s",
        "vvm": "vvm",
        "rpm": "agitation_rpm",
        "agitation_rpm": "agitation_rpm",
        "agitator_power": "agitator_power_total_w",
        "superficial_gas_velocity": "superficial_gas_velocity_m_per_s",
    }
    return mapping.get(criterion.lower())


def _endpoint_markdown(endpoint: dict[str, Any]) -> Iterable[str]:
    setpoints = endpoint["derived_setpoints"]
    yield f"- Label: `{endpoint['label']}`"
    yield f"- Vessel: `{endpoint['vessel']}`"
    yield f"- Working volume: `{endpoint['working_volume_l']} L`"
    geometry = endpoint.get("geometry") or {}
    if geometry:
        geom_str = ", ".join(f"{k}={v}" for k, v in geometry.items())
        yield f"- Geometry: `{geom_str}`"
    yield ""
    yield "Derived setpoints:"
    yield ""
    yield f"| Setpoint | Value | Source |"
    yield f"|---|---|---|"
    yield f"| Agitation | `{setpoints['agitation_rpm']} rpm` | derived |"
    yield f"| Tip speed | `{setpoints['tip_speed_m_per_s']} m/s` | derived |"
    yield f"| Mix time | `{setpoints['mix_time_s']} s` | Nienow `N*t_m={setpoints['mix_time_constant']}` ({setpoints['mix_time_constant_source']}) |"
    yield f"| Agitator power | `{setpoints['agitator_power_total_w']} W` total / `{setpoints['agitator_power_per_impeller_w']} W` per impeller | `N_p={setpoints['power_number']}` ({setpoints['power_number_source']}) |"
    yield f"| P/V | `{setpoints['p_per_v_w_per_m3']} W/m^3` | {setpoints['p_per_v_source']} |"
    yield f"| Sparge | `{setpoints['gas_flow_l_per_min']} L/min` (`vvm={setpoints['vvm']}`) | declared |"
    yield f"| Superficial gas velocity | `{setpoints['superficial_gas_velocity_m_per_s']} m/s` | derived |"
    yield f"| kLa | `{setpoints['kla_per_hour']} /h` | derived |"


__all__ = ["compute_scale_recipe", "render_recipe_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
