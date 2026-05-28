"""One-document run-packet composer.

Public API: :func:`compose_run_packet`, :func:`render_run_packet_markdown`.

Stitches together every artifact the skill produces — manifest, readiness
verdict, optimization goals, scale-bridge engineering recipe, first-batch design,
first-batch results, first-batch OLS analysis, follow-up plan — into one shippable
document the lab can consume without an agent in the loop.

Each section degrades gracefully when its inputs are missing (no
scale_context, no first-batch results yet, etc.) and records *why* it was
skipped. Every section carries the originating module's claim level so a
reviewer sees what level of evidence drove what.

The output is labeled ``claim_level: run_packet_planning_compose``: it is
a composition of planning artifacts, not new analysis. The packet does not
itself emit new claims beyond what its constituent artifacts already carry.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .adaptive import evaluate_assay_power, load_manifest
from .analysis import analyze_results
from .bridge import compute_bridge_qualification
from .doe_generators import generate_design
from .family_recommender import recommend_family
from .goals import formulate_goals
from .sampling import compute_sampling_plan
from .scale_recipe import compute_scale_recipe
from .validators import summarize, validate_campaign

CLAIM_LEVEL = "run_packet_planning_compose"
NON_CLAIM = (
    "Run packet is a composition of planning artifacts. It does not produce "
    "new analytical claims; each section's claim level is inherited from the "
    "module that produced it. Treat the packet as a handoff document, not a "
    "validated batch record."
)


def compose_run_packet(
    campaign_dir: Path,
    *,
    results_path: Path | None = None,
    response_id: str | None = None,
    seed: int = 0,
    n_permutations: int = 500,
    n_bootstrap: int = 200,
) -> dict[str, Any]:
    """Build one packet dict pulling together every available artifact.

    ``results_path`` is optional. When provided, first-batch analysis runs against
    the result rows (after QC/trust filtering matches the manifest's policy)
    and the analysis section is included.
    """
    campaign_dir = Path(campaign_dir)
    manifest = load_manifest(campaign_dir)

    sections: dict[str, Any] = {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "campaign_id": manifest.get("campaign_id"),
        "manifest_claim_level": manifest.get("claim_level"),
        "profiles": manifest.get("profiles") or [],
        "objective": manifest.get("objective"),
    }

    sections["readiness"] = _readiness_section(campaign_dir)
    sections["family_recommendation"] = _family_recommendation_section(manifest)
    sections["goals"] = _goals_section(manifest)
    sections["scale_recipe"] = _scale_recipe_section(manifest)
    sections["bridge_qualification"] = _bridge_qualification_section(manifest)
    sections["assay_power"] = _assay_power_section(manifest)
    sections["sampling_plan"] = _sampling_plan_section(manifest)
    sections["wave1_design"] = _wave1_design_section(manifest)
    sections["wave1_results"] = _wave1_results_section(manifest, results_path)
    sections["wave1_analysis"] = _wave1_analysis_section(
        manifest,
        results_path,
        response_id=response_id,
        seed=seed,
        n_permutations=n_permutations,
        n_bootstrap=n_bootstrap,
    )
    sections["wave2_plan"] = _wave2_plan_section(campaign_dir)
    sections["risks"] = _risks_section(manifest)
    sections["stop_rules"] = manifest.get("stop_rules") or []
    sections["assumptions"] = manifest.get("assumptions") or []
    sections["biosafety"] = _biosafety_section(manifest)

    return sections


def render_run_packet_markdown(packet: dict[str, Any]) -> str:
    """Render the packet as a single markdown document."""
    lines: list[str] = []
    lines.extend(_header(packet))
    lines.extend(_render_section_header("Readiness", packet["readiness"]))
    lines.extend(_render_readiness(packet["readiness"]))
    if packet["family_recommendation"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("DoE family recommendation", packet["family_recommendation"]))
        lines.extend(_render_family_recommendation(packet["family_recommendation"]))
    if packet["goals"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("Optimization goals", packet["goals"]))
        lines.extend(_render_goals(packet["goals"]))
    if packet["scale_recipe"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("Scale-bridge engineering recipe", packet["scale_recipe"]))
        lines.extend(_render_scale_recipe(packet["scale_recipe"]))
    if packet["bridge_qualification"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("Bridge qualification design", packet["bridge_qualification"]))
        lines.extend(_render_bridge_qualification(packet["bridge_qualification"]))
    if packet["assay_power"]["status"] != "SKIPPED":
        lines.extend(_render_section_header("Assay-power readiness", packet["assay_power"]))
        lines.extend(_render_assay_power(packet["assay_power"]))
    if packet["sampling_plan"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("Sampling plan", packet["sampling_plan"]))
        lines.extend(_render_sampling_plan(packet["sampling_plan"]))
    if packet["wave1_design"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("first-batch design", packet["wave1_design"]))
        lines.extend(_render_wave1_design(packet["wave1_design"]))
    if packet["wave1_results"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("first-batch results", packet["wave1_results"]))
        lines.extend(_render_wave1_results(packet["wave1_results"]))
    if packet["wave1_analysis"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("first-batch analysis", packet["wave1_analysis"]))
        lines.extend(_render_wave1_analysis(packet["wave1_analysis"]))
    if packet["wave2_plan"]["status"] == "AVAILABLE":
        lines.extend(_render_section_header("Follow-up plan", packet["wave2_plan"]))
        lines.extend(_render_wave2_plan(packet["wave2_plan"]))
    lines.extend(_render_section_header("Risks", {"claim_level": "manifest_declared"}))
    lines.extend(_render_risks(packet["risks"]))
    lines.extend(_render_section_header("Stop rules", {"claim_level": "manifest_declared"}))
    lines.extend(_render_stop_rules(packet["stop_rules"]))
    lines.extend(_render_section_header("Assumptions", {"claim_level": "manifest_declared"}))
    lines.extend(_render_assumptions(packet["assumptions"]))
    if packet["biosafety"]["status"] != "NOT_TRIGGERED":
        lines.extend(_render_section_header("Biosafety", {"claim_level": "guidance_only"}))
        lines.extend(_render_biosafety(packet["biosafety"]))
    lines.append("")
    lines.append(f"> {packet['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Section builders
# =====================================================================


def _readiness_section(campaign_dir: Path) -> dict[str, Any]:
    full = validate_campaign(campaign_dir)
    return {
        "status": "AVAILABLE",
        "claim_level": "validation_planning",
        "summary": summarize(full),
        "failed_checks": full.get("failed_check_ids") or [],
        "error_count": full.get("error_count", 0),
        "warning_count": full.get("warning_count", 0),
    }


def _goals_section(manifest: dict[str, Any]) -> dict[str, Any]:
    goals = formulate_goals(manifest)
    if goals is None:
        return {"status": "NOT_AVAILABLE", "reason": "no_objective_bounds_declarable"}
    return {
        "status": "AVAILABLE",
        "claim_level": goals["claim_level"],
        "objectives": goals["objectives"],
        "constraints": goals["constraints"],
        "composite": goals["composite"],
    }


def _family_recommendation_section(manifest: dict[str, Any]) -> dict[str, Any]:
    rec = recommend_family(manifest)
    if not rec.get("recommended_family"):
        return {"status": "NOT_AVAILABLE", "reason": "no_family_could_be_recommended"}
    return {
        "status": "AVAILABLE",
        "claim_level": rec["claim_level"],
        "recommended_family": rec["recommended_family"],
        "candidates": rec["candidates"],
        "decision_path": rec["decision_path"],
        "factor_summary": rec["factor_summary"],
        "goal": rec["goal"],
    }


def _bridge_qualification_section(manifest: dict[str, Any]) -> dict[str, Any]:
    if not manifest.get("arms"):
        return {"status": "NOT_AVAILABLE", "reason": "no_arms_declared"}
    if not manifest.get("scale_context"):
        return {"status": "NOT_AVAILABLE", "reason": "no_scale_context_declared"}
    has_bridge = any(
        isinstance(arm, dict) and isinstance(arm.get("bridge_to"), dict) and arm["bridge_to"].get("arm_id")
        for arm in manifest.get("arms") or []
    )
    if not has_bridge:
        return {"status": "NOT_AVAILABLE", "reason": "no_arm_declares_bridge_to"}
    try:
        plan = compute_bridge_qualification(manifest)
    except ValueError as exc:
        return {"status": "FAILED", "reason": str(exc)}
    return {
        "status": "AVAILABLE",
        "claim_level": plan["claim_level"],
        "from_arm": plan["from_arm"]["arm_id"],
        "to_arm": plan["to_arm"]["arm_id"],
        "criterion": plan["criterion"],
        "n_runs": plan["n_runs"],
        "n_replicates": plan["n_replicates"],
        "transferable_factors": plan["transferable_factors"],
        "needs_retuning_factors": plan["needs_retuning_factors"],
        "qualification_design_preview": plan["qualification_design"][:5],
        "recapitulation_criterion": plan["recapitulation_criterion"],
    }


def _sampling_plan_section(manifest: dict[str, Any]) -> dict[str, Any]:
    plan = compute_sampling_plan(manifest)
    if not plan["samples"]:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "no_assayed_or_instrument_responses_to_schedule",
        }
    return {
        "status": "AVAILABLE",
        "claim_level": plan["claim_level"],
        "run_duration_h": plan["run_duration_h"],
        "n_samples": plan["totals"]["n_samples"],
        "total_volume_ml": plan["totals"]["total_volume_ml"],
        "samples_per_response": plan["totals"]["samples_per_response"],
        "samples_per_phase": plan["totals"]["samples_per_phase"],
        "phases": plan["phases"],
        "schedule_preview": plan["samples"][:10],
    }


def _scale_recipe_section(manifest: dict[str, Any]) -> dict[str, Any]:
    if not manifest.get("scale_context"):
        return {"status": "NOT_AVAILABLE", "reason": "no_scale_context_declared"}
    try:
        recipe = compute_scale_recipe(manifest)
    except ValueError as exc:
        return {"status": "FAILED", "reason": str(exc)}
    return {
        "status": "AVAILABLE",
        "claim_level": recipe["claim_level"],
        "primary_criterion": recipe["primary_criterion"],
        "from_scale": recipe["from_scale"],
        "to_scale": recipe["to_scale"],
        "criterion_match": recipe["criterion_match"],
        "secondary_match": recipe["secondary_match"],
        "warnings": recipe["warnings"],
    }


def _assay_power_section(manifest: dict[str, Any]) -> dict[str, Any]:
    has_assayed = any(
        r.get("assay_required") for r in (manifest.get("responses") or []) if isinstance(r, dict)
    )
    if not has_assayed:
        return {"status": "SKIPPED", "reason": "no_assay_required_responses"}
    result = evaluate_assay_power(manifest, strict=False)
    return {
        "status": "AVAILABLE",
        "claim_level": "assay_power_planning",
        "summary_status": result.get("status"),
        "response_results": result.get("response_results") or [],
    }


def _wave1_design_section(manifest: dict[str, Any]) -> dict[str, Any]:
    doe = manifest.get("doe") or {}
    family = doe.get("family")
    if not family:
        return {"status": "NOT_AVAILABLE", "reason": "no_doe_family_declared"}
    try:
        design = generate_design(manifest, seed=0)
    except ValueError as exc:
        return {"status": "FAILED", "reason": str(exc), "family": family}
    return {
        "status": "AVAILABLE",
        "claim_level": design["claim_level"],
        "family": design["family"],
        "n_runs": design["n_runs"],
        "factors": design["factors"],
        "metadata": design["metadata"],
        "preview_rows": design["rows"][:5],
        "warnings": design["warnings"],
    }


def _wave1_results_section(manifest: dict[str, Any], results_path: Path | None) -> dict[str, Any]:
    if results_path is None:
        return {"status": "NOT_AVAILABLE", "reason": "no_results_csv_provided"}
    if not results_path.is_file():
        return {"status": "NOT_AVAILABLE", "reason": "results_csv_missing"}
    rows = _read_csv(results_path)
    qc_pass = sum(1 for row in rows if str(row.get("qc_status", "")).lower() in {"pass", "passed", ""})
    return {
        "status": "AVAILABLE",
        "claim_level": "wave1_results_observed",
        "n_rows": len(rows),
        "n_qc_pass": qc_pass,
        "responses_observed": _responses_observed(manifest, rows),
        "results_csv_path": str(results_path),
    }


def _wave1_analysis_section(
    manifest: dict[str, Any],
    results_path: Path | None,
    *,
    response_id: str | None,
    seed: int,
    n_permutations: int,
    n_bootstrap: int,
) -> dict[str, Any]:
    if results_path is None or not results_path.is_file():
        return {"status": "NOT_AVAILABLE", "reason": "no_results_csv_provided"}
    rows = _read_csv(results_path)
    usable_rows = [row for row in rows if str(row.get("qc_status", "")).lower() in {"pass", "passed", ""}]
    if len(usable_rows) < 4:
        return {"status": "NOT_AVAILABLE", "reason": f"only_{len(usable_rows)}_usable_rows"}
    analysis = analyze_results(
        manifest,
        usable_rows,
        response_id=response_id,
        seed=seed,
        n_permutations=n_permutations,
        n_bootstrap=n_bootstrap,
    )
    if analysis.get("short_circuit_reason"):
        return {"status": "NOT_AVAILABLE", "reason": analysis["short_circuit_reason"]}
    return {
        "status": "AVAILABLE",
        "claim_level": analysis["claim_level"],
        "response_id": analysis["response_id"],
        "n_runs_used": analysis["n_runs_used"],
        "active_factor_ids": analysis["active_factor_ids"],
        "diagnostics": analysis["diagnostics"],
        "coefficients": analysis["coefficients"],
        "wave2_signal": analysis["wave2_signal"],
        "warnings": analysis["warnings"],
    }


def _wave2_plan_section(campaign_dir: Path) -> dict[str, Any]:
    """Read pre-existing follow-up artifacts if the operator has already run plan-wave2."""
    candidates = [
        campaign_dir / "wave2" / "wave2_recommendation.json",
        campaign_dir / "expected" / "wave2_recommendation.json",
    ]
    for path in candidates:
        if path.is_file():
            recommendation = json.loads(path.read_text())
            return {
                "status": "AVAILABLE",
                "claim_level": recommendation.get("claim_level"),
                "recommendation": recommendation,
                "source_path": str(path),
            }
    return {"status": "NOT_AVAILABLE", "reason": "no_wave2_recommendation_artifact_present"}


def _risks_section(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    risks = manifest.get("risk_register") or []
    return [risk for risk in risks if isinstance(risk, dict)]


def _biosafety_section(manifest: dict[str, Any]) -> dict[str, Any]:
    """Surface biosafety prompt only when a biorisk-relevant signal is present."""
    triggers: list[str] = []
    system = manifest.get("system") or {}
    label = str(system.get("organism_label", "")).lower()
    if any(token in label for token in ["recombinant", "gmm", "select_agent", "bsl3", "bsl4"]):
        triggers.append(f"organism_label={system.get('organism_label')}")
    scale_label = str(system.get("scale", "")).lower()
    if any(token in scale_label for token in ["pilot", "manufacturing", "200", "500", "1000", "2000"]):
        triggers.append(f"scale_signal={system.get('scale')}")
    objective = str(manifest.get("objective", "")).lower()
    if any(token in objective for token in ["recombinant dna", "high-containment", "dual-use"]):
        triggers.append(f"objective_signal={manifest.get('objective')}")
    if not triggers:
        return {"status": "NOT_TRIGGERED", "triggers": []}
    return {
        "status": "TRIGGERED",
        "triggers": triggers,
        "non_claim": "Biosafety triggers indicate the operator should consult their IBC and the frameworks in BIOSAFETY.md before execution.",
        "framework_references": [
            "WHO Laboratory Biosafety Manual 4th ed.",
            "NIH Guidelines for Research Involving Recombinant or Synthetic Nucleic Acid Molecules",
            "CDC/NIH Biosafety in Microbiological and Biomedical Laboratories (BMBL)",
            "NIH Dual Use Research of Concern Policy 2024",
        ],
    }


def _responses_observed(manifest: dict[str, Any], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for response in manifest.get("responses") or []:
        rid = response.get("response_id")
        if not rid:
            continue
        values = []
        for row in rows:
            try:
                values.append(float(row.get(rid, "")))
            except (TypeError, ValueError):
                continue
        if not values:
            out.append({"response_id": rid, "n_observed": 0})
            continue
        out.append(
            {
                "response_id": rid,
                "n_observed": len(values),
                "min": round(min(values), 6),
                "max": round(max(values), 6),
                "mean": round(sum(values) / len(values), 6),
            }
        )
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# =====================================================================
# Markdown rendering helpers
# =====================================================================


def _header(packet: dict[str, Any]) -> Iterable[str]:
    yield "# Run packet"
    yield ""
    yield f"- Campaign id: `{packet['campaign_id']}`"
    yield f"- Manifest claim level: `{packet['manifest_claim_level']}`"
    yield f"- Profiles: `{', '.join(packet['profiles']) if packet['profiles'] else '(none declared)'}`"
    if packet.get("objective"):
        yield f"- Objective: {packet['objective']}"
    yield ""


def _render_section_header(title: str, section: dict[str, Any]) -> Iterable[str]:
    yield f"## {title}"
    yield ""
    claim = section.get("claim_level")
    if claim:
        yield f"_Claim level: `{claim}`_"
        yield ""


def _render_readiness(section: dict[str, Any]) -> Iterable[str]:
    summary = section["summary"]
    yield f"- Verdict: **{summary['status']}**"
    yield f"- Errors: `{summary['error_count']}`, warnings: `{summary['warning_count']}`"
    if summary.get("worst_axis"):
        yield f"- Worst axis: `{summary['worst_axis']}`"
    if section["failed_checks"]:
        yield ""
        yield "Failed check ids:"
        yield ""
        for check_id in section["failed_checks"][:25]:
            yield f"- `{check_id}`"
        if len(section["failed_checks"]) > 25:
            yield f"- ... and {len(section['failed_checks']) - 25} more"
    yield ""


def _render_family_recommendation(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Recommended: **`{section['recommended_family']}`** (goal: `{section['goal']}`)"
    yield ""
    yield "| Family | Reason | Expected runs |"
    yield "|---|---|---|"
    for cand in section["candidates"]:
        yield f"| `{cand['family']}` | {cand['reason']} | `{cand['expected_runs']}` |"
    yield ""
    yield f"Decision path: `{', '.join(section['decision_path'])}`"
    yield ""


def _render_bridge_qualification(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Bridge: `{section['from_arm']}` → `{section['to_arm']}` under `{section['criterion']}`"
    yield f"- Runs: `{section['n_runs']}` ({section['n_replicates']} matched-center replicates)"
    yield f"- Transferable factors: `{', '.join(section['transferable_factors']) or '(none)'}`"
    yield f"- Needs retuning: `{', '.join(section['needs_retuning_factors']) or '(none)'}`"
    if section.get("recapitulation_criterion"):
        rc = section["recapitulation_criterion"]
        yield f"- Recapitulation criterion: `{rc.get('metric', '?')}` ≥ `{rc.get('tolerance', '?')}` (status: `{rc.get('status', '?')}`)"
    yield ""


def _render_sampling_plan(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Run duration: `{section['run_duration_h']} h`"
    yield f"- Total samples: `{section['n_samples']}`, total volume: `{section['total_volume_ml']} mL`"
    yield ""
    yield "Samples per response:"
    yield ""
    for rid, count in section["samples_per_response"].items():
        yield f"- `{rid}`: {count}"
    yield ""
    yield "Samples per phase:"
    yield ""
    for phase, count in section["samples_per_phase"].items():
        yield f"- `{phase}`: {count}"
    yield ""


def _render_goals(section: dict[str, Any]) -> Iterable[str]:
    yield "| Response | Direction | Lower | Upper | Target | Shape | Weight | Source |"
    yield "|---|---|---|---|---|---|---|---|"
    for obj in section["objectives"]:
        target = "-" if obj.get("target") is None else f"{obj['target']}"
        yield (
            f"| `{obj['response_id']}` | {obj['direction']} | {obj['lower']} | {obj['upper']} | "
            f"{target} | {obj['shape']} | {obj['weight']} | `{obj['source']}` |"
        )
    yield ""
    yield f"Composite form: `{section['composite']['form']}` over `{section['composite']['n_objectives']}` objectives."
    yield ""


def _render_scale_recipe(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Primary criterion: `{section['primary_criterion']}`"
    match = section["criterion_match"]
    yield (
        f"- Match: from=`{match['from_value']:.4g}` → to=`{match['to_value']:.4g}` "
        f"(delta=`{match['delta_pct']:.1f}%`, status=**{match['status']}**)"
    )
    yield ""
    for label_key, name in (("from_scale", "from_scale"), ("to_scale", "to_scale")):
        endpoint = section[label_key]
        setpoints = endpoint["derived_setpoints"]
        yield f"### {name}: `{endpoint['label']}` ({endpoint['working_volume_l']} L)"
        yield ""
        yield "| Setpoint | Value |"
        yield "|---|---|"
        yield f"| Agitation | `{setpoints['agitation_rpm']} rpm` |"
        yield f"| Tip speed | `{setpoints['tip_speed_m_per_s']} m/s` |"
        yield f"| Mix time | `{setpoints['mix_time_s']} s` |"
        yield f"| Agitator power | `{setpoints['agitator_power_total_w']} W` total / `{setpoints['agitator_power_per_impeller_w']} W` per impeller |"
        yield f"| P/V | `{setpoints['p_per_v_w_per_m3']} W/m^3` ({setpoints['p_per_v_source']}) |"
        yield f"| Sparge | `{setpoints['gas_flow_l_per_min']} L/min` (`vvm={setpoints['vvm']}`) |"
        yield f"| kLa | `{setpoints['kla_per_hour']} /h` |"
        yield ""
    if section["warnings"]:
        yield "Warnings:"
        yield ""
        for warn in section["warnings"]:
            yield f"- `{warn}`"
        yield ""


def _render_assay_power(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Status: **{section['summary_status']}**"
    yield ""
    yield "| Response | Status | Failures |"
    yield "|---|---|---|"
    for response in section["response_results"]:
        failures = response.get("failures") or []
        warnings = response.get("warnings") or []
        notes = ", ".join(failures + warnings) or "-"
        yield f"| `{response.get('response_id')}` | {response.get('status')} | {notes} |"
    yield ""


def _render_wave1_design(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Family: `{section['family']}`, runs: `{section['n_runs']}`, factors: `{', '.join(section['factors'])}`"
    if section["warnings"]:
        yield "- Warnings:"
        for warn in section["warnings"]:
            yield f"  - `{warn}`"
    yield ""
    yield "Preview (first 5 rows):"
    yield ""
    if not section["preview_rows"]:
        yield "_no rows_"
        yield ""
        return
    headers = ["design_run_id"] + section["factors"] + ["center_point"]
    yield "| " + " | ".join(headers) + " |"
    yield "|" + "|".join(["---"] * len(headers)) + "|"
    for row in section["preview_rows"]:
        yield "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
    yield ""


def _render_wave1_results(section: dict[str, Any]) -> Iterable[str]:
    yield f"- Rows ingested: `{section['n_rows']}` (QC-pass: `{section['n_qc_pass']}`)"
    yield f"- Source: `{section['results_csv_path']}`"
    yield ""
    yield "Per-response observed range:"
    yield ""
    yield "| Response | n | min | mean | max |"
    yield "|---|---|---|---|---|"
    for entry in section["responses_observed"]:
        if entry["n_observed"] == 0:
            yield f"| `{entry['response_id']}` | 0 | - | - | - |"
        else:
            yield (
                f"| `{entry['response_id']}` | {entry['n_observed']} | "
                f"{entry.get('min')} | {entry.get('mean')} | {entry.get('max')} |"
            )
    yield ""


def _render_wave1_analysis(section: dict[str, Any]) -> Iterable[str]:
    diag = section["diagnostics"]
    yield f"- Response: `{section['response_id']}`, runs used: `{section['n_runs_used']}`"
    yield f"- R^2: `{diag['r_squared']}`, adjusted R^2: `{diag['adjusted_r_squared']}`, RMSE: `{diag['rmse']}`"
    lof = diag.get("lack_of_fit") or {}
    if lof.get("status") == "AVAILABLE":
        yield f"- Lack-of-fit: F = `{lof['f_stat']}` on `{lof['df_lof']}` and `{lof['df_pure_error']}` df"
    else:
        yield f"- Lack-of-fit: `{lof.get('status', 'NOT_AVAILABLE')}`"
    yield ""
    yield "| Term | Estimate | SE | t | perm p | Active |"
    yield "|---|---|---|---|---|---|"
    for coef in section["coefficients"]:
        active = "**yes**" if coef["active"] else "no"
        t_str = "n/a" if coef["t_stat"] is None else f"{coef['t_stat']:.3f}"
        yield (
            f"| `{coef['term']}` | {coef['estimate']:.4f} | {coef['std_error']:.4f} | "
            f"{t_str} | {coef['permutation_p']:.3f} | {active} |"
        )
    yield ""
    if section["active_factor_ids"]:
        yield f"Active factors: `{', '.join(section['active_factor_ids'])}`"
    else:
        yield "No factors crossed the significance threshold."
    yield ""


def _render_wave2_plan(section: dict[str, Any]) -> Iterable[str]:
    rec = section["recommendation"]
    yield f"- Recommended action: **{rec.get('recommended_action')}**"
    yield f"- Best run id: `{rec.get('best_run_id', '-')}`"
    if rec.get("scoring_mode"):
        yield f"- Scoring mode: `{rec['scoring_mode']}`"
    if rec.get("reason"):
        yield f"- Reason: `{rec['reason']}`"
    if rec.get("boundary_factor_ids"):
        yield f"- Boundary factors: `{', '.join(rec['boundary_factor_ids'])}`"
    yield f"- Source artifact: `{section['source_path']}`"
    yield ""


def _render_risks(risks: list[dict[str, Any]]) -> Iterable[str]:
    if not risks:
        yield "_no risks declared_"
        yield ""
        return
    yield "| Id | Category | Likelihood | Impact | Status | Mitigation |"
    yield "|---|---|---|---|---|---|"
    for risk in risks:
        yield (
            f"| `{risk.get('risk_id', '-')}` | {risk.get('category', '-')} | "
            f"{risk.get('likelihood', '-')} | {risk.get('impact', '-')} | "
            f"{risk.get('status', '-')} | {risk.get('mitigation', '-')} |"
        )
    yield ""


def _render_stop_rules(rules: list[dict[str, Any]]) -> Iterable[str]:
    if not rules:
        yield "_no stop rules declared_"
        yield ""
        return
    for rule in rules:
        yield f"- `{rule.get('rule_id', '?')}`: {rule.get('condition', '?')} → action `{rule.get('action', '?')}`"
    yield ""


def _render_assumptions(assumptions: list[dict[str, Any]]) -> Iterable[str]:
    if not assumptions:
        yield "_no assumptions recorded_"
        yield ""
        return
    for assumption in assumptions:
        yield (
            f"- `{assumption.get('assumption_id', '?')}` "
            f"(status: `{assumption.get('status', '?')}`): {assumption.get('statement', '?')}"
        )
    yield ""


def _render_biosafety(section: dict[str, Any]) -> Iterable[str]:
    yield "Biorisk-relevant signals detected. Operator should consult their IBC and the frameworks listed below before execution."
    yield ""
    yield "Triggers:"
    yield ""
    for trigger in section["triggers"]:
        yield f"- `{trigger}`"
    yield ""
    yield "Frameworks to consult:"
    yield ""
    for framework in section["framework_references"]:
        yield f"- {framework}"
    yield ""


__all__ = ["compose_run_packet", "render_run_packet_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
