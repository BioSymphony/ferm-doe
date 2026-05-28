"""Lightweight schema validators for engine artifacts."""

from __future__ import annotations

from typing import Any


REQUIRED_CAMPAIGN_STATE = {
    "schema_version",
    "state_kind",
    "campaign_id",
    "objective",
    "responses",
    "factors",
    "workflow_modes",
    "missing_info",
    "readiness_precheck",
}

REQUIRED_DESIGN = {"schema_version", "design_id", "lane", "backend", "rows", "diagnostics"}
REQUIRED_READINESS = {"schema_version", "scorecard_kind", "campaign_id", "status", "score", "gates"}
REQUIRED_TOURNAMENT = {"schema_version", "tournament_kind", "campaign_id", "selected_design_id", "candidates"}
REQUIRED_RESULT_INGESTION = {"schema_version", "result_ingestion_kind", "campaign_id", "recommended_action", "negative_result_memory"}

VERSIONED_ARTIFACTS = {
    "campaign_state.json": "ferm_doe_campaign_state",
    "candidate_designs.json": "ferm_doe_candidate_designs",
    "design_adjudication.json": "ferm_doe_design_tournament",
    "readiness_scorecard.json": "campaign_readiness",
    "dossier_manifest.json": "ferm_doe_dossier",
    "wave2_recommendation.json": "ferm_doe_wave_results",
    "adaptive_wave2_plan.json": "ferm_doe_adaptive_wave2_plan",
    "assay_power_results.json": "ferm_doe_assay_power",
    "result_ingestion_report.json": "ferm_doe_result_ingestion_report",
    "wave_2_decision_rules.json": "ferm_doe_wave2_decision_rules",
}


def validate_campaign_state(data: dict[str, Any]) -> list[str]:
    errors = _missing(data, REQUIRED_CAMPAIGN_STATE)
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("state_kind") != "ferm_doe_campaign_state":
        errors.append("state_kind must be ferm_doe_campaign_state")
    if not isinstance(data.get("factors"), list) or not data.get("factors"):
        errors.append("factors must be a non-empty list")
    if not isinstance(data.get("responses"), list) or not data.get("responses"):
        errors.append("responses must be a non-empty list")
    return errors


def validate_design(data: dict[str, Any]) -> list[str]:
    errors = _missing(data, REQUIRED_DESIGN)
    diagnostics = data.get("diagnostics")
    if not isinstance(diagnostics, dict):
        errors.append("diagnostics must be an object")
    elif "run_count" not in diagnostics:
        errors.append("diagnostics.run_count is required")
    elif "metric_labels" not in diagnostics and data.get("lane") != "skeptical_auditor":
        errors.append("diagnostics.metric_labels is required for executable designs")
    if not isinstance(data.get("rows"), list):
        errors.append("rows must be a list")
    return errors


def validate_readiness(data: dict[str, Any]) -> list[str]:
    errors = _missing(data, REQUIRED_READINESS)
    if data.get("status") not in {"GREEN", "YELLOW", "RED"}:
        errors.append("status must be GREEN, YELLOW, or RED")
    if not isinstance(data.get("gates"), list) or not data.get("gates"):
        errors.append("gates must be a non-empty list")
    return errors


def validate_tournament(data: dict[str, Any]) -> list[str]:
    errors = _missing(data, REQUIRED_TOURNAMENT)
    if not isinstance(data.get("candidates"), list) or not data.get("candidates"):
        errors.append("candidates must be a non-empty list")
    return errors


def validate_result_ingestion(data: dict[str, Any]) -> list[str]:
    errors = _missing(data, REQUIRED_RESULT_INGESTION)
    if data.get("recommended_action") not in {"confirm", "narrow", "expand", "pause", "stop", "scale_or_downscale"}:
        errors.append("recommended_action is invalid")
    if not isinstance(data.get("negative_result_memory"), list):
        errors.append("negative_result_memory must be a list")
    return errors


def _missing(data: dict[str, Any], required: set[str]) -> list[str]:
    return [f"missing required field: {field}" for field in sorted(required - set(data))]
