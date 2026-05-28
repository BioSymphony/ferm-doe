"""Design tournament adjudication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .campaign_arms import campaign_arms_enabled, project_state_for_arm, propose_per_arm_candidate_designs
from .compiler import compile_campaign_state
from .doe import EXACTNESS_ORDER, normalize_design_intent, propose_candidate_designs
from .io_utils import parse_number, write_json
from .readiness import score_campaign_readiness
from .swarm import ensure_swarm_review, swarm_enabled, swarm_tournament_enabled


def run_design_tournament(
    manifest_path: Path | None = None,
    campaign_state: dict[str, Any] | None = None,
    out_dir: Path | None = None,
    run_budget: int | None = None,
) -> dict[str, Any]:
    if campaign_state is None:
        if manifest_path is None:
            raise ValueError("manifest_path or campaign_state is required")
        campaign_state = compile_campaign_state(manifest_path)
    if swarm_enabled(campaign_state):
        campaign_state = ensure_swarm_review(manifest_path, campaign_state)
    if campaign_arms_enabled(campaign_state):
        return run_per_arm_design_tournament(manifest_path, campaign_state, out_dir, run_budget)
    readiness = score_campaign_readiness(manifest_path, campaign_state)
    designs = propose_candidate_designs(manifest_path, campaign_state, out_dir / "design_candidates" if out_dir else None, run_budget)

    adjudicated = []
    for candidate in designs["candidates"]:
        adjudicated.append(score_candidate(candidate, campaign_state, readiness))
    accepted = [item for item in adjudicated if item["accepted"]]
    selected = max(accepted, key=lambda item: item["total_score"]) if accepted else max(adjudicated, key=lambda item: item["total_score"])
    verdict = "accepted" if selected["accepted"] else "no_accepted_design"
    result = {
        "schema_version": 1,
        "tournament_kind": "ferm_doe_design_tournament",
        "campaign_id": campaign_state.get("campaign_id"),
        "readiness_status": readiness["status"],
        "verdict": verdict,
        "selected_design_id": selected["design_id"],
        "selected": selected,
        "candidates": adjudicated,
        "swarm_review_applied": swarm_tournament_enabled(campaign_state),
        "adjudication_policy": [
            "Do not select skeptical audit lane as an executable design.",
            "Reject executable designs when readiness is RED.",
            "Prefer feasible, assay-ready, mode-aware designs over statistical score alone.",
            "When Scientific Swarm is enabled, prefer designs that align with evidence-backed factor roles, assumption safety, observability, and control strategy.",
        ],
    }
    if out_dir is not None:
        write_json(out_dir / "design_adjudication.json", result)
        write_json(out_dir / "design_comparison.json", design_comparison(result))
    return result


def run_per_arm_design_tournament(
    manifest_path: Path | None,
    campaign_state: dict[str, Any],
    out_dir: Path | None = None,
    run_budget: int | None = None,
    designs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if designs is None:
        designs = propose_per_arm_candidate_designs(manifest_path, campaign_state, out_dir / "design_candidates" if out_dir else None, run_budget)
    flattened: list[dict[str, Any]] = []
    per_arm: dict[str, dict[str, Any]] = {}
    selected_ids: dict[str, str] = {}
    for arm in campaign_state.get("campaign_arms", []) or []:
        arm_id = str(arm.get("arm_id") or "").strip()
        if not arm_id:
            continue
        projected = project_state_for_arm(campaign_state, arm_id)
        readiness = score_campaign_readiness(manifest_path, projected)
        arm_designs = designs.get("per_arm", {}).get(arm_id, {})
        adjudicated = [score_candidate(candidate, projected, readiness) for candidate in arm_designs.get("candidates", [])]
        if not adjudicated:
            arm_result = {
                "schema_version": 1,
                "tournament_kind": "ferm_doe_arm_design_tournament",
                "campaign_id": campaign_state.get("campaign_id"),
                "arm_id": arm_id,
                "readiness_status": readiness["status"],
                "verdict": "no_accepted_design",
                "selected_design_id": "",
                "selected": None,
                "candidates": [],
            }
        else:
            accepted = [item for item in adjudicated if item["accepted"]]
            selected = max(accepted, key=lambda item: item["total_score"]) if accepted else max(adjudicated, key=lambda item: item["total_score"])
            arm_result = {
                "schema_version": 1,
                "tournament_kind": "ferm_doe_arm_design_tournament",
                "campaign_id": campaign_state.get("campaign_id"),
                "arm_id": arm_id,
                "readiness_status": readiness["status"],
                "verdict": "accepted" if selected["accepted"] else "no_accepted_design",
                "selected_design_id": selected["design_id"],
                "selected": selected,
                "candidates": adjudicated,
            }
            selected_ids[arm_id] = selected["design_id"]
        per_arm[arm_id] = arm_result
        for item in adjudicated:
            flattened.append({"arm_id": arm_id, **item})
        if out_dir is not None:
            arm_dir = out_dir / "campaign_arms" / arm_id
            arm_dir.mkdir(parents=True, exist_ok=True)
            write_json(arm_dir / "design_adjudication.json", arm_result)
            write_json(arm_dir / "design_comparison.json", design_comparison(arm_result))
    accepted_arms = [item for item in per_arm.values() if item.get("verdict") == "accepted"]
    result = {
        "schema_version": 1,
        "tournament_kind": "ferm_doe_per_arm_design_tournament",
        "campaign_id": campaign_state.get("campaign_id"),
        "readiness_status": "MIXED",
        "verdict": "accepted" if accepted_arms else "no_accepted_design",
        "selected_design_id": "per_arm:" + ",".join(f"{arm_id}={design_id}" for arm_id, design_id in sorted(selected_ids.items())),
        "selected": {"per_arm_selected_design_ids": selected_ids},
        "candidates": flattened,
        "per_arm": per_arm,
        "swarm_review_applied": swarm_tournament_enabled(campaign_state),
        "adjudication_policy": [
            "Generate and score each campaign arm independently.",
            "Never select a cross-arm/chimeric executable design.",
            "Cross-arm claims are limited by arm_bridge_policy and executed evidence joins.",
        ],
    }
    if out_dir is not None:
        write_json(out_dir / "design_adjudication.json", result)
        write_json(out_dir / "per_arm_design_adjudication.json", result)
        write_json(out_dir / "design_comparison.json", design_comparison(result))
        write_json(out_dir / "per_arm_design_comparison.json", design_comparison(result))
    return result


def score_candidate(candidate: dict[str, Any], state: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    diagnostics = candidate.get("diagnostics", {})
    if candidate.get("lane") == "skeptical_auditor":
        return {
            "design_id": candidate["design_id"],
            "lane": candidate["lane"],
            "accepted": False,
            "total_score": 0.0,
            "rejection_reasons": ["Skeptical audit is not an executable design."],
            "component_scores": {"skeptical_pressure": diagnostics.get("rejection_pressure", 0.0)},
        }

    rejection_reasons = []
    if readiness["status"] == "RED":
        rejection_reasons.append("Campaign readiness is RED.")
    if diagnostics.get("run_count", 0) < 3:
        rejection_reasons.append("Design has too few runs to execute.")
    if diagnostics.get("constraint_violations"):
        rejection_reasons.append("Design has constraint violations.")
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    intent = normalize_design_intent(policy.get("design_intent"))
    exactness = str(candidate.get("exactness") or "heuristic")
    if exactness not in EXACTNESS_ORDER:
        exactness = "heuristic"
    minimum_exactness = str(policy.get("minimum_exactness") or policy.get("required_exactness") or "").lower()
    if bool(policy.get("require_adapter_backed")):
        minimum_exactness = "adapter_backed"
    if minimum_exactness in EXACTNESS_ORDER and EXACTNESS_ORDER[exactness] < EXACTNESS_ORDER[minimum_exactness]:
        rejection_reasons.append(f"Design exactness {exactness} is below required {minimum_exactness}.")
    estimability = diagnostics.get("estimability") if isinstance(diagnostics.get("estimability"), dict) else {}
    rank_deficient = estimability.get("status") == "aliased_or_underpowered"
    if intent in {"rsm_fit", "confirmatory"} and rank_deficient:
        rejection_reasons.append(f"Design intent {intent} requires a full-rank model matrix.")
    if intent == "mixture" and candidate.get("method_family") != "mixture":
        rejection_reasons.append("Design intent mixture requires a mixture-family candidate.")
    if intent == "custom_constrained" and candidate.get("method_family") not in {"custom_optimal", "space_filling"}:
        rejection_reasons.append("Design intent custom_constrained requires a custom-optimal or candidate-set design.")
    if intent == "user_supplied_design" and candidate.get("method_family") != "user_supplied_design":
        rejection_reasons.append("Design intent user_supplied_design requires the imported user-supplied table.")

    statistical = float(diagnostics.get("statistical_quality", 0.0))
    feasibility = _gate_score(readiness, "equipment_reagent_feasibility")
    assay = _gate_score(readiness, "assay_readiness")
    assay_power = _gate_score(readiness, "assay_power")
    response = _gate_score(readiness, "response_semantics")
    mode = _gate_score(readiness, "mode_transfer")
    cost = _gate_score(readiness, "cost_time")
    wave2 = _wave2_value(candidate, state)
    robustness = 0.85 if candidate.get("lane") == "robustness" else 0.65
    if assay < 0.45:
        rejection_reasons.append("Assay readiness is too weak for DOE execution.")
    assay_power_gate = _gate(readiness, "assay_power")
    assay_power_has_blocker = any(issue.get("severity") == "blocker" for issue in assay_power_gate.get("issues", []))
    if intent in {"rsm_fit", "confirmatory", "user_supplied_design"} and assay_power_has_blocker:
        rejection_reasons.append(f"Design intent {intent} requires primary-response assay power to pass before claiming fitted or confirmatory DOE readiness.")
    if bool(policy.get("require_assay_power")) and assay_power < 0.7:
        rejection_reasons.append("Assay-power policy is required but below threshold for DOE execution.")
    if feasibility < 0.45:
        rejection_reasons.append("Equipment/reagent feasibility is too weak for DOE execution.")
    if response < 0.45:
        rejection_reasons.append("Response semantics are too weak for DOE execution.")
    if mode < 0.35:
        rejection_reasons.append("Mode-transfer risk is too high for DOE execution.")
    if cost < 0.35:
        rejection_reasons.append("Cost/time readiness is too weak for DOE execution.")

    swarm_scores = swarm_candidate_scores(candidate, state)
    rejection_reasons.extend(swarm_scores.pop("rejection_reasons", []))
    if swarm_tournament_enabled(state):
        total = (
            0.15 * statistical
            + 0.12 * feasibility
            + 0.11 * assay
            + 0.08 * assay_power
            + 0.09 * response
            + 0.08 * mode
            + 0.05 * cost
            + 0.04 * wave2
            + 0.03 * robustness
            + 0.10 * swarm_scores["factor_universe_alignment"]
            + 0.07 * swarm_scores["assumption_safety"]
            + 0.05 * swarm_scores["observability_coverage"]
            + 0.03 * swarm_scores["control_strategy_fit"]
        )
    else:
        total = (
            0.22 * statistical
            + 0.16 * feasibility
            + 0.13 * assay
            + 0.10 * assay_power
            + 0.13 * response
            + 0.11 * mode
            + 0.07 * cost
            + 0.05 * wave2
            + 0.03 * robustness
        )
        swarm_scores = {}
    return {
        "design_id": candidate["design_id"],
        "lane": candidate["lane"],
        "accepted": not rejection_reasons,
        "total_score": round(total, 4),
        "rejection_reasons": rejection_reasons,
        "component_scores": {
            "statistical_quality": round(statistical, 4),
            "feasibility": round(feasibility, 4),
            "assay": round(assay, 4),
            "assay_power": round(assay_power, 4),
            "response_semantics": round(response, 4),
            "mode_transfer": round(mode, 4),
            "cost_time": round(cost, 4),
            "wave2_value": round(wave2, 4),
            "robustness": round(robustness, 4),
            **{key: round(value, 4) for key, value in swarm_scores.items()},
        },
        "diagnostics": diagnostics,
        "claim_level": scored_claim_level(candidate, intent, rank_deficient),
        "exactness": exactness,
        "method_family": candidate.get("method_family", candidate.get("lane")),
        "backend_used": candidate.get("backend_used", candidate.get("backend")),
    }


def scored_claim_level(candidate: dict[str, Any], intent: str, rank_deficient: bool) -> str:
    if rank_deficient and intent in {"screening", "space_filling_scout", "custom_constrained"}:
        return "planned_scouting_design"
    return str(candidate.get("claim_level") or "planned_heuristic_design")


def design_comparison(tournament: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for candidate in tournament.get("candidates", []):
        diagnostics = candidate.get("diagnostics", {})
        rows.append(
            {
                "design_id": candidate["design_id"],
                "lane": candidate["lane"],
                "accepted": candidate["accepted"],
                "total_score": candidate["total_score"],
                "run_count": diagnostics.get("run_count"),
                "rank": diagnostics.get("rank"),
                "model_term_count": diagnostics.get("model_term_count"),
                "d_efficiency": diagnostics.get("d_efficiency"),
                "i_efficiency": diagnostics.get("i_efficiency"),
                "g_efficiency": diagnostics.get("g_efficiency"),
                "exactness": candidate.get("exactness"),
                "claim_level": candidate.get("claim_level"),
                "method_family": candidate.get("method_family"),
                "backend_used": candidate.get("backend_used"),
                "diagnostic_verdict": diagnostics.get("diagnostic_verdict", {}).get("status") if isinstance(diagnostics.get("diagnostic_verdict"), dict) else None,
                "swarm_factor_universe_alignment": candidate.get("component_scores", {}).get("factor_universe_alignment"),
                "swarm_assumption_safety": candidate.get("component_scores", {}).get("assumption_safety"),
                "swarm_observability_coverage": candidate.get("component_scores", {}).get("observability_coverage"),
                "swarm_control_strategy_fit": candidate.get("component_scores", {}).get("control_strategy_fit"),
                "constraint_violations": len(diagnostics.get("constraint_violations", [])),
                "rejection_reasons": candidate.get("rejection_reasons", []),
            }
        )
    return {
        "schema_version": 1,
        "comparison_kind": "ferm_doe_design_comparison",
        "campaign_id": tournament.get("campaign_id"),
        "selected_design_id": tournament.get("selected_design_id"),
        "rows": rows,
    }


def _gate_score(readiness: dict[str, Any], gate_name: str) -> float:
    gate = _gate(readiness, gate_name)
    if gate:
        return float(gate.get("score", 0.0))
    return 0.5


def _gate(readiness: dict[str, Any], gate_name: str) -> dict[str, Any]:
    for gate in readiness.get("gates", []):
        if gate.get("gate") == gate_name:
            return gate
    return {}


def _wave2_value(candidate: dict[str, Any], state: dict[str, Any]) -> float:
    selected_modes = set(state.get("workflow_modes", {}).get("selected", []))
    lane = candidate.get("lane")
    if lane == "space_filling" and "autonomous-multi-agent-doe-planner" in selected_modes:
        return 0.85
    if lane == "response_surface" and len(state.get("factors", [])) <= 6:
        return 0.8
    if lane == "scouting" and "cost-productivity-minimizer" in selected_modes:
        return 0.8
    return 0.65


def swarm_candidate_scores(candidate: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if not swarm_tournament_enabled(state):
        return {"rejection_reasons": []}
    review = state.get("swarm_review") if isinstance(state.get("swarm_review"), dict) else {}
    factor_universe = review.get("factor_universe") if isinstance(review.get("factor_universe"), dict) else {}
    attack = review.get("assumption_attack") if isinstance(review.get("assumption_attack"), dict) else {}
    observability = review.get("observability_plan") if isinstance(review.get("observability_plan"), dict) else {}
    controls = review.get("control_run_strategy") if isinstance(review.get("control_run_strategy"), dict) else {}
    factor_score, factor_rejections = factor_universe_alignment(candidate, factor_universe)
    assumption_score, assumption_rejections = assumption_safety(candidate, attack)
    return {
        "factor_universe_alignment": factor_score,
        "assumption_safety": assumption_score,
        "observability_coverage": observability_coverage(observability),
        "control_strategy_fit": control_strategy_fit(candidate, controls),
        "rejection_reasons": factor_rejections + assumption_rejections,
    }


def factor_universe_alignment(candidate: dict[str, Any], factor_universe: dict[str, Any]) -> tuple[float, list[str]]:
    items = factor_universe.get("factors", []) if isinstance(factor_universe, dict) else []
    by_id = {item.get("factor_id"): item for item in items}
    values = row_values(candidate.get("rows", []))
    rejections: list[str] = []
    penalties = 0.0
    for factor_id, factor_values in values.items():
        item = by_id.get(factor_id)
        if not item:
            continue
        final_class = str(item.get("final_classification") or item.get("classification") or "")
        varied = len(factor_values) > 1
        if final_class in {"exclude", "fixed_control", "monitor_only"} and varied:
            rejections.append(f"Design varies {factor_id}, but Scientific Swarm classified it as {final_class}.")
            penalties += 0.55
        elif final_class == "wave2_candidate" and varied:
            penalties += 0.25
        recommendation = item.get("range_recommendation") if isinstance(item.get("range_recommendation"), dict) else {}
        for value in factor_values:
            if value_outside_recommended_range(value, recommendation):
                rejections.append(f"Design violates evidence-backed range for {factor_id}.")
                penalties += 0.45
                break
        if item.get("conflicts") and varied:
            penalties += 0.2
    conflict_penalty = min(0.25, 0.05 * int(factor_universe.get("conflict_count", 0) or 0))
    return max(0.0, round(1.0 - penalties - conflict_penalty, 4)), rejections


def assumption_safety(candidate: dict[str, Any], attack: dict[str, Any]) -> tuple[float, list[str]]:
    challenges = attack.get("challenges", []) if isinstance(attack, dict) else []
    candidate_factors = set(row_values(candidate.get("rows", [])).keys())
    rejections: list[str] = []
    penalties = 0.0
    for item in challenges:
        severity = str(item.get("severity") or "").lower()
        affected = {str(value) for value in item.get("affected_items", []) if value}
        hits_candidate = not affected or bool(affected & candidate_factors)
        if severity in {"blocker", "critical"} and hits_candidate:
            rejections.append(f"Design hits blocker-level swarm assumption attack {item.get('challenge_id')}.")
            penalties += 0.6
        elif severity in {"blocker", "critical"}:
            penalties += 0.2
        elif severity == "warning" and hits_candidate:
            penalties += 0.04
    return max(0.0, round(1.0 - min(0.85, penalties), 4)), rejections


def observability_coverage(observability: dict[str, Any]) -> float:
    if not observability:
        return 0.65
    if observability.get("coverage_score") is not None:
        return float(observability.get("coverage_score") or 0.0)
    measurements = observability.get("measurements", [])
    unobservable = observability.get("unobservable_risks", [])
    online = 1.0 if any(item.get("kind") == "online" for item in measurements) else 0.0
    offline = 1.0 if any(item.get("kind") == "offline" for item in measurements) else 0.0
    return max(0.0, min(1.0, 0.45 + 0.2 * online + 0.2 * offline - 0.04 * len(unobservable)))


def control_strategy_fit(candidate: dict[str, Any], controls: dict[str, Any]) -> float:
    if not controls:
        return 0.65
    diagnostics = candidate.get("diagnostics", {})
    center_required = int(controls.get("required_center_points") or 0)
    repeat_required = int(controls.get("required_repeats") or 0)
    center_score = min(1.0, float(diagnostics.get("center_points", 0)) / center_required) if center_required else 1.0
    repeat_score = min(1.0, float(diagnostics.get("replicate_count", 0)) / repeat_required) if repeat_required else 1.0
    run_ids = " ".join(str(row.get("run_id", "")).lower() for row in candidate.get("rows", []))
    special_required = [item for item in controls.get("controls", []) if item.get("control_type") in {"baseline", "bridge", "assay_control", "phase_switch_control"}]
    special_hits = sum(1 for item in special_required if str(item.get("control_type", "")).lower() in run_ids or str(item.get("placement", "")).lower() in run_ids)
    special_score = min(1.0, special_hits / len(special_required)) if special_required else 1.0
    return round(0.55 * center_score + 0.25 * repeat_score + 0.20 * special_score, 4)


def row_values(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for row in rows:
        for key, value in row.items():
            if key == "run_id" or value in {None, ""}:
                continue
            values.setdefault(key, set()).add(str(value))
    return values


def value_outside_recommended_range(value: Any, recommendation: dict[str, Any]) -> bool:
    if not recommendation or not recommendation.get("changed"):
        return False
    numeric = parse_number(value)
    if numeric is None:
        return False
    low = parse_number(recommendation.get("final_min"))
    high = parse_number(recommendation.get("final_max"))
    if low is not None and numeric < low - 1e-9:
        return True
    if high is not None and numeric > high + 1e-9:
        return True
    return False
