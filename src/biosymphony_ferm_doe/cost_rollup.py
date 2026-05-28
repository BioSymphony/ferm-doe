"""Planning cost / resource rollup across the campaign.

Public API: :func:`compute_cost_rollup`, :func:`render_cost_rollup_markdown`.

Aggregates run counts, sample counts, sample volume, and run-duration
estimates from what the skill already produces (the design matrix, the
sampling plan, the manifest's declared run duration), and combines them
with operator-supplied per-resource unit costs to emit a planning
budget. Strictly a *rollup*: every number traces back either to an
artifact-derived count or to a unit cost the operator declared. The
module does not estimate yields, throughput contention, or robotics
queueing — those live with the lab's planning system.

Output is labeled ``claim_level: cost_rollup_planning``. The non_claim
spells out what the rollup does and does not represent.

Per-resource unit costs come from the manifest's optional ``resource_costs``
block, which has shape::

    "resource_costs": {
        "currency": "USD",
        "per_run_cost": 200,
        "per_sample_cost": 5,
        "per_volume_ml_cost": 0.50,
        "per_run_duration_h_cost": 25,
        "wave2_runs_estimate": 3
    }

Any field can be omitted; missing fields contribute zero to the total.
The optional ``--per-run-cost`` etc. CLI flags override these on a
per-invocation basis without mutating the manifest.
"""

from __future__ import annotations

from typing import Any

from .doe_generators import generate_design
from .sampling import compute_sampling_plan

CLAIM_LEVEL = "cost_rollup_planning"
NON_CLAIM = (
    "Cost rollup multiplies operator-declared unit costs against artifact-"
    "derived counts (runs, samples, volume, run-duration). It does not "
    "estimate yields, throughput contention, robotics queueing, or staff "
    "time. Use it as a budgeting input, not as a quote."
)


def compute_cost_rollup(
    manifest: dict[str, Any],
    *,
    per_run_cost: float | None = None,
    per_sample_cost: float | None = None,
    per_volume_ml_cost: float | None = None,
    per_run_duration_h_cost: float | None = None,
    wave2_runs_estimate: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Roll up first-batch + sampling + follow-up estimate into a planning budget."""
    declared = manifest.get("resource_costs") if isinstance(manifest.get("resource_costs"), dict) else {}
    currency = declared.get("currency", "USD")

    cost_run = _coalesce(per_run_cost, declared.get("per_run_cost"), 0.0)
    cost_sample = _coalesce(per_sample_cost, declared.get("per_sample_cost"), 0.0)
    cost_volume = _coalesce(per_volume_ml_cost, declared.get("per_volume_ml_cost"), 0.0)
    cost_duration = _coalesce(per_run_duration_h_cost, declared.get("per_run_duration_h_cost"), 0.0)
    wave2_estimate = int(_coalesce(wave2_runs_estimate, declared.get("wave2_runs_estimate"), 0))

    wave1_n_runs = _wave1_run_count(manifest, seed=seed)
    sampling = _sampling_summary(manifest)
    run_duration_h = sampling.get("run_duration_h") or _default_run_duration(manifest)

    wave1_run_cost = wave1_n_runs * cost_run
    wave1_duration_cost = wave1_n_runs * (run_duration_h or 0.0) * cost_duration
    sample_cost = sampling.get("n_samples", 0) * cost_sample
    volume_cost = sampling.get("total_volume_ml", 0.0) * cost_volume
    wave2_run_cost = wave2_estimate * cost_run
    wave2_duration_cost = wave2_estimate * (run_duration_h or 0.0) * cost_duration

    breakdown = [
        {"line_item": "wave1_runs", "count": wave1_n_runs, "unit_cost": cost_run, "total": round(wave1_run_cost, 4)},
        {
            "line_item": "wave1_run_duration",
            "count": wave1_n_runs * (run_duration_h or 0.0),
            "unit_cost": cost_duration,
            "total": round(wave1_duration_cost, 4),
        },
        {"line_item": "samples", "count": sampling.get("n_samples", 0), "unit_cost": cost_sample, "total": round(sample_cost, 4)},
        {"line_item": "sample_volume_ml", "count": sampling.get("total_volume_ml", 0.0), "unit_cost": cost_volume, "total": round(volume_cost, 4)},
        {"line_item": "wave2_runs_estimate", "count": wave2_estimate, "unit_cost": cost_run, "total": round(wave2_run_cost, 4)},
        {
            "line_item": "wave2_run_duration_estimate",
            "count": wave2_estimate * (run_duration_h or 0.0),
            "unit_cost": cost_duration,
            "total": round(wave2_duration_cost, 4),
        },
    ]
    total = sum(item["total"] for item in breakdown)
    wave1_total = round(wave1_run_cost + wave1_duration_cost + sample_cost + volume_cost, 4)
    wave2_total = round(wave2_run_cost + wave2_duration_cost, 4)

    warnings: list[str] = []
    if cost_run == 0 and cost_sample == 0 and cost_volume == 0 and cost_duration == 0:
        warnings.append("no_unit_costs_declared_total_will_be_zero")
    if wave1_n_runs == 0:
        warnings.append("wave1_run_count_zero_check_doe_family_or_results")

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "currency": currency,
        "wave1_n_runs": wave1_n_runs,
        "wave2_runs_estimate": wave2_estimate,
        "samples_total": sampling.get("n_samples", 0),
        "sample_volume_total_ml": sampling.get("total_volume_ml", 0.0),
        "run_duration_h": run_duration_h,
        "unit_costs": {
            "per_run": cost_run,
            "per_sample": cost_sample,
            "per_volume_ml": cost_volume,
            "per_run_duration_h": cost_duration,
        },
        "breakdown": breakdown,
        "wave1_total": wave1_total,
        "wave2_total": wave2_total,
        "campaign_total": round(total, 4),
        "warnings": warnings,
    }


def render_cost_rollup_markdown(rollup: dict[str, Any]) -> str:
    lines = ["# Cost rollup", ""]
    lines.append(f"- Claim level: `{rollup['claim_level']}`")
    lines.append(f"- Currency: `{rollup['currency']}`")
    lines.append(f"- first-batch runs: `{rollup['wave1_n_runs']}`, follow-up estimate: `{rollup['wave2_runs_estimate']}`")
    lines.append(f"- Samples: `{rollup['samples_total']}`, sample volume: `{rollup['sample_volume_total_ml']} mL`")
    lines.append(f"- Run duration assumed: `{rollup['run_duration_h']} h`")
    lines.append("")
    unit = rollup["unit_costs"]
    lines.append(f"Unit costs ({rollup['currency']}): per run = `{unit['per_run']}`, per sample = `{unit['per_sample']}`, per mL = `{unit['per_volume_ml']}`, per run-hour = `{unit['per_run_duration_h']}`")
    lines.append("")
    lines.append("| Line item | Count | Unit cost | Total |")
    lines.append("|---|---|---|---|")
    for item in rollup["breakdown"]:
        lines.append(f"| `{item['line_item']}` | {item['count']} | {item['unit_cost']} | {item['total']} |")
    lines.append("")
    lines.append(f"- **first-batch subtotal: `{rollup['wave1_total']}` {rollup['currency']}**")
    lines.append(f"- **follow-up subtotal: `{rollup['wave2_total']}` {rollup['currency']}**")
    lines.append(f"- **Campaign total: `{rollup['campaign_total']}` {rollup['currency']}**")
    lines.append("")
    if rollup["warnings"]:
        lines.append("Warnings:")
        lines.append("")
        for warn in rollup["warnings"]:
            lines.append(f"- `{warn}`")
        lines.append("")
    lines.append(f"> {rollup['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Helpers
# =====================================================================


def _coalesce(*values: Any) -> float:
    for value in values:
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def _wave1_run_count(manifest: dict[str, Any], *, seed: int) -> int:
    declared = (manifest.get("doe") or {}).get("n_runs")
    try:
        if declared is not None:
            return int(declared)
    except (TypeError, ValueError):
        pass
    try:
        design = generate_design(manifest, seed=seed)
    except ValueError:
        return 0
    return int(design.get("n_runs", 0))


def _sampling_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    plan = compute_sampling_plan(manifest)
    return {
        "n_samples": plan["totals"]["n_samples"],
        "total_volume_ml": plan["totals"]["total_volume_ml"],
        "run_duration_h": plan["run_duration_h"],
    }


def _default_run_duration(manifest: dict[str, Any]) -> float | None:
    policy = manifest.get("sampling_policy") if isinstance(manifest.get("sampling_policy"), dict) else {}
    if policy.get("run_duration_h") is not None:
        try:
            return float(policy["run_duration_h"])
        except (TypeError, ValueError):
            return None
    return None


__all__ = ["compute_cost_rollup", "render_cost_rollup_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
