"""Multi-arm bridge qualification design.

Public API: :func:`compute_bridge_qualification`, :func:`render_bridge_markdown`.

Builds the qualification design at ``to_arm`` that bridges from a reference
``from_arm`` under a declared scale criterion (kLa, P/V, tip speed, etc.).
The qualification design holds the criterion target fixed at the engineering
recipe values and emits center-point replicates (and optionally factor
perturbations) so the operator can compare recapitulation against the
from_arm reference.

Inputs from manifest:

- ``arms[]`` with ``arm_id``, ``scale_tier``, optional ``bridge_to``
- ``scale_context`` with ``from_scale`` / ``to_scale`` engineering targets,
  ``bridge_strategy.primary_criterion``, and
  ``bridge_factors.{transferable, needs_retuning, not_applicable}``

The function delegates the engineering math to :func:`scale_recipe.compute_scale_recipe`
so the criterion-matched setpoints are derived consistently with what the
``ferm-doe scale-recipe`` subcommand produces.

Output is labeled ``claim_level: bridge_qualification_planning``. The
qualification design is *planning support* only; the recapitulation
criterion in the manifest determines whether the from_arm → to_arm bridge
is later considered qualified.
"""

from __future__ import annotations

from typing import Any, Iterable

from .scale_recipe import compute_scale_recipe

CLAIM_LEVEL = "bridge_qualification_planning"
NON_CLAIM = (
    "Bridge qualification is a planned design at the target scale. It does "
    "not establish that the small or large scale recapitulates the other "
    "until executed runs satisfy the manifest's recapitulation_criterion "
    "with provenance."
)


def compute_bridge_qualification(
    manifest: dict[str, Any],
    *,
    from_arm_id: str | None = None,
    to_arm_id: str | None = None,
    n_replicates: int = 3,
    perturbation_pct: float | None = None,
) -> dict[str, Any]:
    """Compute qualification design rows at ``to_arm`` matched to ``from_arm``.

    ``n_replicates`` is the number of recipe-matched center-point rows to emit.
    ``perturbation_pct`` is optional: when set (e.g. ``10`` for ±10 %), the
    function additionally emits one perturbed row per transferable factor at
    +pct and another at -pct of the factor's declared midpoint. Set to
    ``None`` to emit only center-point replicates.
    """
    arms = manifest.get("arms") or manifest.get("campaign_arms") or []
    if not arms:
        raise ValueError("manifest_has_no_arms_declared")
    arm_index = {arm.get("arm_id"): arm for arm in arms if isinstance(arm, dict) and arm.get("arm_id")}

    if to_arm_id is None:
        to_arm_id, from_arm_id = _infer_arm_pair(arms)
    if to_arm_id is None or to_arm_id not in arm_index:
        raise ValueError(f"to_arm_id_{to_arm_id}_not_declared_in_manifest_arms")

    to_arm = arm_index[to_arm_id]
    bridge_to = to_arm.get("bridge_to") if isinstance(to_arm.get("bridge_to"), dict) else {}
    if from_arm_id is None:
        from_arm_id = bridge_to.get("arm_id")
    if from_arm_id is None or from_arm_id not in arm_index:
        raise ValueError(f"from_arm_id_{from_arm_id}_not_declared_or_bridge_to_missing")
    from_arm = arm_index[from_arm_id]

    criterion = bridge_to.get("criterion") or _scale_strategy_criterion(manifest)
    recipe = compute_scale_recipe(manifest)
    to_setpoints = recipe["to_scale"]["derived_setpoints"]
    from_setpoints = recipe["from_scale"]["derived_setpoints"]

    bridge_factors = (manifest.get("scale_context") or {}).get("bridge_factors") or {}
    transferable_ids = list(bridge_factors.get("transferable") or [])
    needs_retuning_ids = list(bridge_factors.get("needs_retuning") or [])
    not_applicable_ids = list(bridge_factors.get("not_applicable") or [])

    factor_lookup = _factor_lookup(manifest)

    matched_factor_values: dict[str, Any] = {}
    for fid in transferable_ids:
        factor = factor_lookup.get(fid)
        if factor is None:
            matched_factor_values[fid] = ""
            continue
        matched_factor_values[fid] = _midpoint(factor)
    retuned_setpoints: dict[str, Any] = {}
    for fid in needs_retuning_ids:
        if fid in to_setpoints:
            retuned_setpoints[fid] = to_setpoints[fid]
        else:
            retuned_setpoints[fid] = "operator_to_supply_at_run_time"

    qualification_rows: list[dict[str, Any]] = []
    for index in range(n_replicates):
        row: dict[str, Any] = {
            "design_run_id": f"BQ-CTR-{index + 1:02d}",
            "arm_id": to_arm_id,
            "row_kind": "matched_center",
            "replicate_group": "matched_center",
            "criterion": criterion,
            "criterion_target": _criterion_target_value(recipe, criterion),
            "non_claim": "Recipe-matched center-point replicate; measures recapitulation noise vs from_arm reference.",
        }
        for fid, value in matched_factor_values.items():
            row[fid] = value
        for fid, value in retuned_setpoints.items():
            row[fid] = value
        qualification_rows.append(row)

    if perturbation_pct is not None and transferable_ids:
        pct = float(perturbation_pct) / 100.0
        for fid in transferable_ids:
            factor = factor_lookup.get(fid)
            if factor is None:
                continue
            mid = _midpoint(factor)
            half = _half_range(factor)
            if mid is None or half is None:
                continue
            for sign, label in ((-1, "neg"), (1, "pos")):
                value = mid + sign * pct * 2 * half
                low = factor.get("low")
                high = factor.get("high")
                if low is not None:
                    value = max(value, float(low))
                if high is not None:
                    value = min(value, float(high))
                value = round(value, 6)
                row = {
                    "design_run_id": f"BQ-PRT-{fid}-{label}",
                    "arm_id": to_arm_id,
                    "row_kind": "perturbation",
                    "replicate_group": fid,
                    "criterion": criterion,
                    "criterion_target": _criterion_target_value(recipe, criterion),
                    "non_claim": f"Perturbation of `{fid}` by {sign * perturbation_pct:.1f}% around midpoint.",
                }
                for other_fid, other_value in matched_factor_values.items():
                    row[other_fid] = other_value if other_fid != fid else value
                for other_fid, other_value in retuned_setpoints.items():
                    row[other_fid] = other_value
                qualification_rows.append(row)

    recapitulation = (manifest.get("scale_context") or {}).get("recapitulation_criterion") or {}

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "from_arm": {
            "arm_id": from_arm.get("arm_id"),
            "scale_tier": from_arm.get("scale_tier"),
            "purpose": from_arm.get("purpose"),
            "derived_setpoints": from_setpoints,
        },
        "to_arm": {
            "arm_id": to_arm.get("arm_id"),
            "scale_tier": to_arm.get("scale_tier"),
            "purpose": to_arm.get("purpose"),
            "derived_setpoints": to_setpoints,
        },
        "criterion": criterion,
        "criterion_match": recipe["criterion_match"],
        "transferable_factors": transferable_ids,
        "needs_retuning_factors": needs_retuning_ids,
        "not_applicable_factors": not_applicable_ids,
        "matched_factor_values": matched_factor_values,
        "retuned_setpoints": retuned_setpoints,
        "qualification_design": qualification_rows,
        "n_runs": len(qualification_rows),
        "n_replicates": n_replicates,
        "perturbation_pct": perturbation_pct,
        "recapitulation_criterion": recapitulation,
    }


def render_bridge_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Bridge qualification plan")
    lines.append("")
    lines.append(f"- Claim level: `{plan['claim_level']}`")
    lines.append(f"- Bridge criterion: `{plan['criterion']}`")
    match = plan.get("criterion_match", {})
    if match:
        lines.append(
            f"- Criterion match: from=`{match.get('from_value', '?')}` → to=`{match.get('to_value', '?')}` "
            f"(delta=`{match.get('delta_pct', '?')}%`, status=**{match.get('status', '?')}**)"
        )
    lines.append("")
    lines.append("## Arms")
    lines.append("")
    for label, arm in (("from_arm", plan["from_arm"]), ("to_arm", plan["to_arm"])):
        lines.append(f"### {label}: `{arm['arm_id']}`")
        lines.append("")
        lines.append(f"- Scale tier: `{arm.get('scale_tier', '-')}`")
        lines.append(f"- Purpose: `{arm.get('purpose', '-')}`")
        setpoints = arm.get("derived_setpoints", {}) or {}
        if setpoints:
            lines.append(f"- Recipe RPM: `{setpoints.get('agitation_rpm', '-')}`")
            lines.append(f"- Recipe sparge: `{setpoints.get('gas_flow_l_per_min', '-')} L/min`")
            lines.append(f"- Recipe kLa: `{setpoints.get('kla_per_hour', '-')} /h`")
        lines.append("")
    lines.append("## Bridge factors")
    lines.append("")
    lines.append(f"- Transferable: `{', '.join(plan['transferable_factors']) or '(none)'}`")
    lines.append(f"- Needs retuning: `{', '.join(plan['needs_retuning_factors']) or '(none)'}`")
    lines.append(f"- Not applicable: `{', '.join(plan['not_applicable_factors']) or '(none)'}`")
    lines.append("")
    lines.append("## Qualification design")
    lines.append("")
    lines.append(
        f"- Run count: `{plan['n_runs']}` ({plan['n_replicates']} matched-center replicates"
        + (f" + {len(plan['qualification_design']) - plan['n_replicates']} perturbations" if plan["perturbation_pct"] else "")
        + ")"
    )
    if plan["matched_factor_values"]:
        lines.append("- Transferable factor values held at midpoint:")
        for fid, value in plan["matched_factor_values"].items():
            lines.append(f"  - `{fid}` = `{value}`")
    if plan["retuned_setpoints"]:
        lines.append("- Retuned setpoints (from to_arm scale recipe):")
        for fid, value in plan["retuned_setpoints"].items():
            lines.append(f"  - `{fid}` = `{value}`")
    lines.append("")
    if plan.get("recapitulation_criterion"):
        rc = plan["recapitulation_criterion"]
        lines.append("## Recapitulation criterion")
        lines.append("")
        lines.append(f"- Metric: `{rc.get('metric', '?')}`")
        lines.append(f"- Tolerance: `{rc.get('tolerance', '?')}`")
        lines.append(f"- Status: `{rc.get('status', '?')}`")
        lines.append("")
    lines.append(f"> {plan['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Helpers
# =====================================================================


def _infer_arm_pair(arms: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Pick to_arm = first arm whose ``bridge_to`` points at another arm."""
    for arm in arms:
        if not isinstance(arm, dict):
            continue
        bridge_to = arm.get("bridge_to")
        if isinstance(bridge_to, dict) and bridge_to.get("arm_id"):
            return arm.get("arm_id"), bridge_to["arm_id"]
    return None, None


def _scale_strategy_criterion(manifest: dict[str, Any]) -> str:
    return ((manifest.get("scale_context") or {}).get("bridge_strategy") or {}).get("primary_criterion", "kLa")


def _factor_lookup(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["factor_id"]: f for f in manifest.get("factors") or [] if isinstance(f, dict) and f.get("factor_id")}


def _midpoint(factor: dict[str, Any]) -> Any:
    low = factor.get("low")
    high = factor.get("high")
    try:
        return round((float(low) + float(high)) / 2.0, 6) if low is not None and high is not None else ""
    except (TypeError, ValueError):
        return ""


def _half_range(factor: dict[str, Any]) -> float | None:
    low = factor.get("low")
    high = factor.get("high")
    try:
        if low is None or high is None:
            return None
        return (float(high) - float(low)) / 2.0
    except (TypeError, ValueError):
        return None


def _criterion_target_value(recipe: dict[str, Any], criterion: str) -> Any:
    setpoints = recipe["to_scale"]["derived_setpoints"]
    mapping = {
        "kla": "kla_per_hour",
        "kla_per_hour": "kla_per_hour",
        "p_per_v": "p_per_v_w_per_m3",
        "tip_speed": "tip_speed_m_per_s",
        "mix_time": "mix_time_s",
        "vvm": "vvm",
    }
    key = mapping.get(criterion.lower())
    return setpoints.get(key, "operator_to_supply")


__all__ = ["compute_bridge_qualification", "render_bridge_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
