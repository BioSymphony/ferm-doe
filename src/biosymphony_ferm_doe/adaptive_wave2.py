"""Adaptive follow-up planning orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assay_power import evaluate_assay_power
from .campaign_arms import campaign_arms_enabled, evaluate_bridge_policy
from .ingest import best_numeric, ingest_wave_results, objective_direction, recommend_action, result_ingestion_report
from .io_utils import load_json, parse_number, read_csv, write_csv, write_json
from .utilities.assay_power import render_assay_power_report
from .utilities.augment_design import run_augment_design_utility


DEFAULT_CLAIM_LEVEL = "planned_wave2_design"


def plan_adaptive_wave2(
    campaign_state_path: Path,
    results_csv: Path,
    out_dir: Path,
    selected_design_path: Path | None = None,
    remaining_budget: int | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    """Run the deterministic first-batch-result to follow-up-plan loop."""

    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_json(campaign_state_path)
    rows, result_headers = read_csv(results_csv)
    ingestion = ingest_wave_results(campaign_state_path, results_csv, out_dir, selected_design_path=selected_design_path)
    quality = result_ingestion_report(rows)
    usable_rows = quality["usable_rows"]
    assay_power = evaluate_assay_power(state, usable_rows)
    final_recommendation = _apply_assay_power_to_recommendation(ingestion, assay_power)
    per_arm = per_arm_wave2_recommendations(state, usable_rows)
    bridge = evaluate_bridge_policy(state, usable_rows)

    multi_arm_global = campaign_arms_enabled(state) and len(_observed_arms(usable_rows)) > 1
    if multi_arm_global:
        augment = _write_skipped_multi_arm_augment(out_dir, state, usable_rows, result_headers)
    else:
        augment_dir = out_dir / "utility_outputs" / "augment-design"
        augment = run_augment_design_utility(
            campaign_state_path,
            results_csv,
            augment_dir,
            remaining_budget=remaining_budget,
            backend=backend,
        )
        _materialize_top_level_augment_artifacts(out_dir, augment_dir, final_recommendation["recommended_action"])

    adaptive_trace = {
        "schema_version": 1,
        "trace_kind": "ferm_doe_adaptive_wave2_trace",
        "campaign_id": state.get("campaign_id"),
        "claim_level": DEFAULT_CLAIM_LEVEL,
        "steps": [
            {"step": "result_join_and_arm_scope", "status": "PASS" if not ingestion.get("execution_join_report", {}).get("errors") and not ingestion.get("arm_scope_report", {}).get("errors") else "WARN"},
            {"step": "trust_qc_filter", "usable_rows": quality["usable_row_count"], "input_rows": quality["input_row_count"]},
            {"step": "assay_power", "status": assay_power.get("status"), "primary_status": assay_power.get("primary_status")},
            {"step": "bridge_eligibility", "status": bridge.get("status"), "scale_or_downscale_allowed": bridge.get("scale_or_downscale_allowed")},
            {"step": "augment_design", "status": "SKIPPED" if multi_arm_global or final_recommendation["recommended_action"] in {"pause", "stop"} else "PLANNED", "rows": augment.get("augment_run_count", 0)},
        ],
        "determinism": {
            "stdlib_fallback": True,
            "backend_requested": backend or "auto",
            "no_bayesian_or_validated_transfer_claim": True,
        },
    }
    learning_rows = build_learning_ledger_rows(state, ingestion, quality, assay_power, bridge, final_recommendation)
    plan = {
        "schema_version": 1,
        "plan_kind": "ferm_doe_adaptive_wave2_plan",
        "campaign_id": state.get("campaign_id"),
        "claim_level": DEFAULT_CLAIM_LEVEL,
        "recommended_action": final_recommendation["recommended_action"],
        "response_id": state.get("objective", {}).get("response_id"),
        "result_rows": len(rows),
        "usable_result_rows": quality["usable_row_count"],
        "assay_power_status": assay_power.get("status"),
        "primary_assay_power_status": assay_power.get("primary_status"),
        "bridge_eligibility_status": bridge.get("status"),
        "per_arm_recommendations": per_arm,
        "artifacts": [
            "adaptive_wave2_plan.json",
            "result_ingestion_report.json",
            "wave2_recommendation.json",
            "wave2_recommendation.md",
            "locked_prior_runs.csv",
            "augment_design.csv",
            "adaptive_trace.json",
            "learning_ledger.csv",
            "hiccup_review.md",
            "negative_result_memory.json",
            "wave2_manifest.patch.json",
            "assay_power_results.json",
            "assay_power_report.md",
        ],
        "caveats": [
            "Follow-up rows are planned candidates only.",
            "Do not claim optimized, validated, production-ready, or scale-transfer success from this packet.",
            "Scale/downscale actions require bridge eligibility and later executed confirmation evidence.",
        ],
    }
    manifest_patch = {
        "schema_version": 1,
        "patch_kind": "ferm_doe_wave2_manifest_patch",
        "claim_level": DEFAULT_CLAIM_LEVEL,
        "design_policy": {
            "design_intent": "augmentation",
            "wave": 2,
            "locked_prior_runs": "locked_prior_runs.csv",
            "augment_design": "augment_design.csv",
            "recommended_action": final_recommendation["recommended_action"],
        },
    }

    write_json(out_dir / "result_ingestion_report.json", {key: value for key, value in quality.items() if key != "usable_rows"})
    write_json(out_dir / "wave2_recommendation.json", final_recommendation)
    (out_dir / "wave2_recommendation.md").write_text(_render_wave2_recommendation(final_recommendation))
    write_json(out_dir / "assay_power_results.json", assay_power)
    (out_dir / "assay_power_report.md").write_text(render_assay_power_report(assay_power))
    write_csv(out_dir / "learning_ledger.csv", learning_rows, LEARNING_LEDGER_HEADERS)
    (out_dir / "hiccup_review.md").write_text(render_hiccup_review(state, learning_rows, final_recommendation))
    write_json(out_dir / "adaptive_trace.json", adaptive_trace)
    write_json(out_dir / "wave2_manifest.patch.json", manifest_patch)
    write_json(out_dir / "adaptive_wave2_plan.json", plan)
    return plan


LEARNING_LEDGER_HEADERS = [
    "learning_id",
    "campaign_id",
    "wave",
    "arm_id",
    "event_type",
    "severity",
    "source_artifact",
    "symptom",
    "root_cause_hypothesis",
    "design_implication",
    "assay_power_implication",
    "bridge_implication",
    "recommended_follow_up",
    "status",
    "claim_boundary",
]


def build_learning_ledger_rows(
    state: dict[str, Any],
    ingestion: dict[str, Any],
    quality: dict[str, Any],
    assay_power: dict[str, Any],
    bridge: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(event_type: str, severity: str, source_artifact: str, symptom: str, follow_up: str, *, arm_id: str = "", root: str = "", design: str = "", assay: str = "", bridge_text: str = "") -> None:
        rows.append(
            {
                "learning_id": f"L{len(rows) + 1:03d}",
                "campaign_id": state.get("campaign_id", ""),
                "wave": "wave2_planning",
                "arm_id": arm_id,
                "event_type": event_type,
                "severity": severity,
                "source_artifact": source_artifact,
                "symptom": symptom,
                "root_cause_hypothesis": root,
                "design_implication": design,
                "assay_power_implication": assay,
                "bridge_implication": bridge_text,
                "recommended_follow_up": follow_up,
                "status": "open" if severity in {"blocker", "warning"} else "recorded",
                "claim_boundary": "planned_wave2_design_only",
            }
        )

    join = ingestion.get("execution_join_report") if isinstance(ingestion.get("execution_join_report"), dict) else {}
    for error in join.get("errors", []) or []:
        add("result_join_hiccup", "blocker", "execution_join_report.json", str(error), "Repair result run IDs or selected-design path before follow-up planning.", design="Do not augment from unjoined rows.")
    arm_scope = ingestion.get("arm_scope_report") if isinstance(ingestion.get("arm_scope_report"), dict) else {}
    for error in arm_scope.get("errors", []) or []:
        add("arm_scope_hiccup", "blocker", "wave2_recommendation.json", str(error), "Fix arm_id or cross-arm factor leakage before any per-arm narrowing.", design="Mixed-arm rows cannot narrow a single executable factor space.")
    if quality.get("excluded_row_count"):
        add("excluded_rows", "warning", "result_ingestion_report.json", f"{quality.get('excluded_row_count')} rows excluded by inclusion_status.", "Review exclusion reasons and decide whether any rows should be repaired or kept provenance-only.", design="Excluded rows are not locked prior runs.")
    if quality.get("qc_failed_row_count"):
        add("qc_failed_rows", "warning", "result_ingestion_report.json", f"{quality.get('qc_failed_row_count')} rows failed QC.", "Open an assay/process hiccup review before using those rows.", assay="QC-failed rows cannot support assay-power or optimization claims.")
    if quality.get("low_trust_row_count"):
        add("low_trust_rows", "warning", "result_ingestion_report.json", f"{quality.get('low_trust_row_count')} rows were low trust.", "Rescue provenance or keep rows excluded from recommendation logic.", design="Low-trust rows cannot drive narrowing.")
    if assay_power.get("primary_status") in {"FAIL", "WARN"}:
        add(
            "assay_power_hiccup",
            "blocker" if assay_power.get("primary_status") == "FAIL" else "warning",
            "assay_power_results.json",
            f"Primary assay power status is {assay_power.get('primary_status')}.",
            "Update assay_power_policy, replicate plan, LOQ/dynamic range, or assay recovery before fitted/confirmatory claims.",
            assay="Primary response assay power is not clean enough for strong DOE claims.",
        )
    if bridge.get("scale_or_downscale_allowed") is False and recommendation.get("recommended_action") == "pause":
        issues = "; ".join(str(item) for item in bridge.get("issues", []) or [])
        add(
            "bridge_hiccup",
            "warning",
            "wave2_recommendation.json",
            issues or "Bridge policy does not permit scale_or_downscale.",
            "Add bridge controls, assay comparability, and minimum evidence before next-arm planning.",
            bridge_text="Scale/downscale remains blocked.",
        )
    if recommendation.get("recommended_action") in {"pause", "stop"}:
        add(
            "adaptive_stop_or_pause",
            "warning",
            "wave2_recommendation.json",
            f"Follow-up recommendation is {recommendation.get('recommended_action')}.",
            "Do not plan additional lab work until the recorded reason is resolved or the objective changes.",
            design="Next design is intentionally withheld or empty.",
        )
    if not rows:
        add(
            "clean_adaptive_handoff",
            "info",
            "adaptive_wave2_plan.json",
            "No blocking adaptive-planning hiccups were detected.",
            "Proceed with planned follow-up review under the claim boundary.",
        )
    return rows


def _apply_assay_power_to_recommendation(ingestion: dict[str, Any], assay_power: dict[str, Any]) -> dict[str, Any]:
    recommendation = dict(ingestion)
    issues = list(recommendation.get("issues", []))
    primary_status = str(assay_power.get("primary_status") or assay_power.get("status") or "")
    if primary_status == "FAIL" and recommendation.get("recommended_action") not in {"pause", "stop"}:
        recommendation["recommended_action"] = "pause"
        issues.append("Primary-response assay power failed; pause follow-up design changes until assay power is repaired.")
    elif primary_status == "WARN":
        issues.append("Primary-response assay power has caveats; treat follow-up rows as planned candidates only.")
    recommendation["claim_level"] = DEFAULT_CLAIM_LEVEL
    recommendation["assay_power_report"] = {
        "status": assay_power.get("status"),
        "score": assay_power.get("score"),
        "primary_status": assay_power.get("primary_status"),
        "primary_score": assay_power.get("primary_score"),
    }
    recommendation["issues"] = issues
    return recommendation


def per_arm_wave2_recommendations(state: dict[str, Any], usable_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not campaign_arms_enabled(state):
        return []
    response_id = state.get("objective", {}).get("response_id")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in usable_rows:
        arm_id = str(row.get("arm_id") or "").strip()
        if arm_id:
            grouped.setdefault(arm_id, []).append(row)
    items = []
    for arm_id, rows in sorted(grouped.items()):
        numeric = [(parse_number(row.get(response_id)), row) for row in rows] if response_id else []
        numeric = [(value, row) for value, row in numeric if value is not None]
        if numeric:
            action, issues = recommend_action(state, numeric)
            best_value, best_row = best_numeric(state, numeric)
        else:
            action, issues = "pause", [f"No numeric response values found for {response_id} in arm {arm_id}."]
            best_value, best_row = None, {}
        items.append(
            {
                "arm_id": arm_id,
                "recommended_action": action,
                "row_count": len(rows),
                "numeric_row_count": len(numeric),
                "best_run_id": best_row.get("run_id", ""),
                "best_response": best_value,
                "objective_direction": objective_direction(state),
                "issues": issues,
            }
        )
    return items


def _materialize_top_level_augment_artifacts(out_dir: Path, augment_dir: Path, action: str) -> None:
    locked_rows, locked_headers = read_csv(augment_dir / "locked_prior_runs.csv")
    augment_rows, augment_headers = read_csv(augment_dir / "augment_design.csv")
    write_csv(out_dir / "locked_prior_runs.csv", locked_rows, locked_headers)
    if action in {"pause", "stop"}:
        write_csv(out_dir / "augment_design.csv", [], augment_headers)
    else:
        write_csv(out_dir / "augment_design.csv", augment_rows, augment_headers)


def _write_skipped_multi_arm_augment(
    out_dir: Path,
    state: dict[str, Any],
    usable_rows: list[dict[str, str]],
    result_headers: list[str],
) -> dict[str, Any]:
    utility_dir = out_dir / "utility_outputs" / "augment-design"
    utility_dir.mkdir(parents=True, exist_ok=True)
    factor_headers = [str(factor.get("factor_id") or "") for factor in state.get("factors", []) if factor.get("factor_id")]
    augment_headers = ["arm_id", "run_id"] + factor_headers
    write_csv(out_dir / "locked_prior_runs.csv", usable_rows, result_headers)
    write_csv(out_dir / "augment_design.csv", [], augment_headers)
    recommendation = {
        "schema_version": 1,
        "utility_result_kind": "augment_design",
        "campaign_id": state.get("campaign_id"),
        "recommended_action": "per_arm_required",
        "augment_run_count": 0,
        "issues": ["Global multi-arm augmentation skipped to avoid chimeric cross-arm rows; plan follow-up rows per arm."],
    }
    write_json(utility_dir / "augment_design_recommendation.json", recommendation)
    write_json(
        utility_dir / "utility_manifest.json",
        {
            "schema_version": 1,
            "manifest_kind": "ferm_doe_utility_manifest",
            "utility": "augment-design",
            "backend": {"requested": "auto", "selected": "none", "status": "skipped", "fallback": "per_arm_required", "adapter_executed": False},
            "artifacts": [],
            "caveats": recommendation["issues"],
        },
    )
    return recommendation


def _observed_arms(rows: list[dict[str, str]]) -> set[str]:
    return {str(row.get("arm_id") or "").strip() for row in rows if str(row.get("arm_id") or "").strip()}


def _render_wave2_recommendation(recommendation: dict[str, Any]) -> str:
    return (
        "# Adaptive Follow-Up Recommendation\n\n"
        f"- Campaign: {recommendation.get('campaign_id')}\n"
        f"- Claim level: {recommendation.get('claim_level')}\n"
        f"- Recommended action: {recommendation.get('recommended_action')}\n"
        f"- Best run: {recommendation.get('best_run_id')}\n"
        f"- Best response: {recommendation.get('best_response')}\n"
        f"- Assay power: {recommendation.get('assay_power_report', {}).get('primary_status')}\n\n"
        "## Issues\n\n"
        + ("\n".join(f"- {item}" for item in recommendation.get("issues", [])) or "- None")
        + "\n\n## Claim Boundary\n\n"
        "- This is a planned follow-up decision packet, not optimized or validated experimental evidence.\n"
    )


def render_hiccup_review(state: dict[str, Any], learning_rows: list[dict[str, Any]], recommendation: dict[str, Any]) -> str:
    blockers = [row for row in learning_rows if row.get("severity") == "blocker"]
    warnings = [row for row in learning_rows if row.get("severity") == "warning"]
    lines = [
        "# Adaptive Follow-Up Hiccup Review",
        "",
        f"- Campaign: {state.get('campaign_id')}",
        f"- Recommended action: {recommendation.get('recommended_action')}",
        f"- Learning events: {len(learning_rows)}",
        f"- Blockers: {len(blockers)}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Learning Ledger",
        "",
        "| ID | Type | Severity | Symptom | Follow-up |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in learning_rows:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "/")
                for key in ["learning_id", "event_type", "severity", "symptom", "recommended_follow_up"]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Self-Learning Rule",
            "",
            "Future agents should treat this ledger as campaign memory, not proof of success. Resolve open blockers or warnings before tightening factor ranges, strengthening claims, or planning scale/downscale branches.",
            "",
        ]
    )
    return "\n".join(lines)
