"""Task request contract validation and deterministic routing.

The helpers here intentionally avoid third-party JSON Schema dependencies.
They validate the local contract fields that matter for routing and data
safety, then produce a deterministic route summary for Symphony/Linear intake.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TASK_REQUEST_KIND = "ferm_doe_task_request"
TASK_ROUTE_KIND = "ferm_doe_task_request_route"

DATA_CLASSIFICATIONS = {"public", "synthetic", "sanitized", "private_reference", "confidential"}
TASK_INTENTS = {
    "campaign_intake",
    "readiness_audit",
    "historical_data_rescue",
    "assay_readiness",
    "factor_universe",
    "feasibility_audit",
    "design_tournament",
    "dossier_compile",
    "wave2_planning",
    "evidence_execution",
    "issue_pack",
    "compute_handoff",
    "repo_maintenance",
    "unknown",
}
INPUT_KINDS = {
    "campaign_manifest",
    "run_ledger",
    "factor_space",
    "reagent_inventory",
    "equipment_inventory",
    "assay_protocol",
    "evidence_table",
    "issue_pack",
    "compute_policy",
    "results_table",
    "dossier",
    "operator_note",
    "other",
}
ISSUE_PACKS = {
    "fermentation-readiness-v0",
    "scientific-swarm-v0",
    "evidence-executor-v0",
    "doe-parity-v1",
    "adaptive-wave2-assay-power-v0",
    "campaign-arms-v1",
    "none",
}
LANES = {"codex", "symphony", "claude", "human_review", "external"}
PRIORITIES = {"high", "medium", "low"}
PRIVATE_DATA_HANDLING = {"not_applicable", "sanitized_summary_only", "secure_reference_only"}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "request_kind",
    "request_id",
    "title",
    "summary",
    "data_classification",
    "campaign",
    "task",
    "inputs",
    "routing",
    "safety",
    "provenance",
    "notes",
}

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


ROUTE_DEFAULTS: dict[str, dict[str, Any]] = {
    "campaign_intake": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["campaign_manifest.draft.json", "missing_operator_items.json"],
        "requires_operator_review": True,
    },
    "readiness_audit": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["readiness_scorecard.json", "readiness_verdict.md"],
        "requires_operator_review": False,
    },
    "historical_data_rescue": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["historical_run_ledger.csv", "data_trust_report.md"],
        "requires_operator_review": False,
    },
    "assay_readiness": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["assay_readiness_report.md", "assay_power_results.json"],
        "requires_operator_review": True,
    },
    "factor_universe": {
        "issue_pack": "scientific-swarm-v0",
        "lane": "symphony",
        "active_wave": "wave0",
        "expected_artifacts": ["factor_universe.json", "factor_universe.md"],
        "requires_operator_review": False,
    },
    "feasibility_audit": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["readiness_scorecard.json", "constraints.tsv"],
        "requires_operator_review": False,
    },
    "design_tournament": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave1",
        "expected_artifacts": ["candidate_designs.json", "design_adjudication.json"],
        "requires_operator_review": False,
    },
    "dossier_compile": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave1",
        "expected_artifacts": ["ferm-doe-dossier/"],
        "requires_operator_review": False,
    },
    "wave2_planning": {
        "issue_pack": "adaptive-wave2-assay-power-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["adaptive_wave2_plan.json", "result_ingestion_report.json", "assay_power_results.json"],
        "requires_operator_review": False,
    },
    "evidence_execution": {
        "issue_pack": "evidence-executor-v0",
        "lane": "symphony",
        "active_wave": "wave0",
        "expected_artifacts": ["evidence_table.csv", "source_ledger.md", "search_log.md"],
        "requires_operator_review": False,
    },
    "issue_pack": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "codex",
        "active_wave": "wave0",
        "expected_artifacts": ["generated-issues/", "linear-map.json"],
        "requires_operator_review": False,
    },
    "compute_handoff": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "external",
        "active_wave": "wave0",
        "expected_artifacts": ["remote_compute_handoff.json", "launch-plan.json"],
        "requires_operator_review": True,
    },
    "repo_maintenance": {
        "issue_pack": "none",
        "lane": "codex",
        "active_wave": "none",
        "expected_artifacts": [],
        "requires_operator_review": False,
    },
    "unknown": {
        "issue_pack": "fermentation-readiness-v0",
        "lane": "human_review",
        "active_wave": "intake",
        "expected_artifacts": ["operator_intake.md", "missing_operator_items.json"],
        "requires_operator_review": True,
    },
}


KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "compute_handoff",
        (
            "runpod",
            "provider handoff",
            "launch bundle",
            "pod smoke",
            "remote compute",
            "container smoke",
        ),
    ),
    (
        "wave2_planning",
        (
            "follow-up",
            "wave2",
            "adaptive",
            "augment design",
            "result ingestion",
            "negative-result",
            "negative result",
        ),
    ),
    (
        "evidence_execution",
        (
            "pubmed",
            "biorxiv",
            "scholar",
            "literature",
            "vendor protocol",
            "evidence table",
            "source ledger",
        ),
    ),
    (
        "assay_readiness",
        (
            "assay",
            "hplc",
            "elisa",
            "calibration",
            "standard curve",
            "matrix effect",
            "sample stability",
        ),
    ),
    (
        "historical_data_rescue",
        (
            "historical",
            "prior run",
            "run ledger",
            "data rescue",
            "normalize runs",
            "trust audit",
        ),
    ),
    (
        "factor_universe",
        (
            "factor universe",
            "candidate factors",
            "factor range",
            "factor-space",
            "factor space",
            "fixed control",
        ),
    ),
    (
        "feasibility_audit",
        (
            "feasibility",
            "equipment",
            "reagent",
            "capacity",
            "runability",
            "sampling burden",
            "forbidden combination",
        ),
    ),
    (
        "design_tournament",
        (
            "design tournament",
            "candidate designs",
            "compare designs",
            "custom optimal",
            "d-optimal",
            "doe parity",
            "first batch design",
        ),
    ),
    (
        "dossier_compile",
        (
            "dossier",
            "run packet",
            "lab-ready packet",
            "run sheet",
            "result capture template",
        ),
    ),
    (
        "issue_pack",
        (
            "linear issue",
            "issue pack",
            "symphony dispatch",
            "work graph",
            "ticket",
        ),
    ),
    (
        "readiness_audit",
        (
            "readiness",
            "red",
            "yellow",
            "green",
            "do not run",
            "gate",
            "preflight",
        ),
    ),
    (
        "repo_maintenance",
        (
            "test",
            "schema",
            "cli",
            "module",
            "refactor",
            "repo",
            "implementation",
        ),
    ),
]


def schema_path() -> Path:
    """Return the repository-local task request schema path when available."""

    return Path(__file__).resolve().parents[2] / "schemas" / "task_request.schema.json"


def load_task_request(path: str | Path) -> dict[str, Any]:
    """Load a task request JSON object from disk."""

    request_path = Path(path)
    try:
        data = json.loads(request_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {request_path}")
    return data


def validate_task_request(data: dict[str, Any]) -> list[str]:
    """Validate the stdlib task request contract and policy-critical fields."""

    errors: list[str] = []
    missing = _missing(data, {"schema_version", "request_kind", "request_id", "title", "summary", "data_classification", "task", "safety"})
    errors.extend(missing)
    errors.extend(f"unknown top-level field: {field}" for field in sorted(set(data) - TOP_LEVEL_FIELDS))

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if data.get("request_kind") != TASK_REQUEST_KIND:
        errors.append(f"request_kind must be {TASK_REQUEST_KIND}")

    request_id = data.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        errors.append("request_id must be a non-empty string")
    elif not _REQUEST_ID_RE.match(request_id):
        errors.append("request_id contains unsupported characters")

    _require_non_empty_string(data, "title", errors)
    _require_non_empty_string(data, "summary", errors)
    _validate_enum_field(data, "data_classification", DATA_CLASSIFICATIONS, errors)

    task = data.get("task")
    if isinstance(task, dict):
        _validate_task(task, errors)
    elif "task" in data:
        errors.append("task must be an object")

    inputs = data.get("inputs")
    if inputs is not None:
        _validate_inputs(inputs, errors)

    campaign = data.get("campaign")
    if campaign is not None:
        _validate_campaign(campaign, errors)

    routing = data.get("routing")
    if routing is not None:
        _validate_routing(routing, errors)

    safety = data.get("safety")
    if isinstance(safety, dict):
        _validate_safety(data, safety, errors)
    elif "safety" in data:
        errors.append("safety must be an object")

    return errors


def classify_task_request(data: dict[str, Any]) -> dict[str, Any]:
    """Classify the request intent using explicit intent first, then keywords."""

    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    explicit = task.get("intent")
    if explicit in TASK_INTENTS and explicit != "unknown":
        return {
            "task_class": explicit,
            "confidence": 1.0,
            "matched_signals": [f"task.intent:{explicit}"],
        }

    text = _classification_text(data)
    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}
    for task_class, keywords in KEYWORD_RULES:
        for keyword in keywords:
            if keyword in text:
                scores[task_class] = scores.get(task_class, 0) + 1
                matches.setdefault(task_class, []).append(keyword)

    if not scores:
        return {"task_class": "unknown", "confidence": 0.0, "matched_signals": []}

    best_class = sorted(scores, key=lambda item: (-scores[item], item))[0]
    confidence = min(0.95, 0.45 + (scores[best_class] * 0.15))
    return {
        "task_class": best_class,
        "confidence": round(confidence, 2),
        "matched_signals": matches[best_class],
    }


def route_task_request(data: dict[str, Any]) -> dict[str, Any]:
    """Validate, classify, and return the deterministic route contract."""

    errors = validate_task_request(data)
    classification = classify_task_request(data)
    task_class = classification["task_class"]
    defaults = ROUTE_DEFAULTS[task_class]
    routing_request = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    requested_outputs = _requested_outputs(data)
    expected_artifacts = requested_outputs or list(defaults["expected_artifacts"])
    remote_allowed = routing_request.get("remote_compute_allowed") is True
    preferred_lane = routing_request.get("preferred_lane")
    preferred_issue_pack = routing_request.get("preferred_issue_pack")
    recommended_lane = preferred_lane if isinstance(preferred_lane, str) and preferred_lane in LANES else defaults["lane"]
    recommended_issue_pack = (
        preferred_issue_pack
        if isinstance(preferred_issue_pack, str) and preferred_issue_pack in ISSUE_PACKS
        else defaults["issue_pack"]
    )

    requires_remote_compute = task_class == "compute_handoff" or recommended_lane == "external"
    requires_evidence_executor = task_class == "evidence_execution" or _has_input_kind(data, "evidence_table")

    if requires_remote_compute and not remote_allowed:
        errors.append("routing.remote_compute_allowed must be true for external compute handoff routes")

    route = {
        "schema_version": SCHEMA_VERSION,
        "route_kind": TASK_ROUTE_KIND,
        "request_id": data.get("request_id", ""),
        "status": "FAIL" if errors else "OK",
        "errors": errors,
        "classification": classification,
        "routing": {
            "recommended_issue_pack": recommended_issue_pack,
            "recommended_lane": recommended_lane,
            "active_wave": defaults["active_wave"],
            "activate_first_wave_only": routing_request.get("activate_first_wave_only") is not False,
            "requires_operator_review": bool(defaults["requires_operator_review"] or safety.get("contains_private_process_data")),
            "requires_evidence_executor": requires_evidence_executor,
            "requires_remote_compute": requires_remote_compute,
        },
        "expected_artifacts": expected_artifacts,
        "safety_status": "BLOCKED" if any(error.startswith("safety.") for error in errors) else "OK",
    }
    return route


def validate_task_request_file(path: str | Path) -> list[str]:
    """Load and validate a task request file."""

    return validate_task_request(load_task_request(path))


def _validate_task(task: dict[str, Any], errors: list[str]) -> None:
    allowed = {"intent", "priority", "requested_outputs", "constraints", "notes"}
    errors.extend(f"unknown task field: {field}" for field in sorted(set(task) - allowed))
    if "intent" not in task:
        errors.append("task.intent is required")
    else:
        _validate_enum_field(task, "intent", TASK_INTENTS, errors, prefix="task.")
    if "priority" in task:
        _validate_enum_field(task, "priority", PRIORITIES, errors, prefix="task.")
    outputs = task.get("requested_outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("task.requested_outputs must be a non-empty list")
    elif not all(isinstance(item, str) and item.strip() for item in outputs):
        errors.append("task.requested_outputs entries must be non-empty strings")
    constraints = task.get("constraints")
    if constraints is not None and (not isinstance(constraints, list) or not all(isinstance(item, str) for item in constraints)):
        errors.append("task.constraints must be a list of strings")


def _validate_inputs(inputs: Any, errors: list[str]) -> None:
    if not isinstance(inputs, list):
        errors.append("inputs must be a list")
        return
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            errors.append(f"inputs[{index}] must be an object")
            continue
        allowed = {"kind", "path", "required", "data_classification", "notes"}
        errors.extend(f"unknown inputs[{index}] field: {field}" for field in sorted(set(item) - allowed))
        if "kind" not in item:
            errors.append(f"inputs[{index}].kind is required")
        else:
            _validate_enum_field(item, "kind", INPUT_KINDS, errors, prefix=f"inputs[{index}].")
        if not isinstance(item.get("path"), str) or not item.get("path", "").strip():
            errors.append(f"inputs[{index}].path must be a non-empty string")
        if "required" in item and not isinstance(item.get("required"), bool):
            errors.append(f"inputs[{index}].required must be a boolean")
        if "data_classification" in item:
            _validate_enum_field(item, "data_classification", DATA_CLASSIFICATIONS, errors, prefix=f"inputs[{index}].")


def _validate_campaign(campaign: Any, errors: list[str]) -> None:
    if not isinstance(campaign, dict):
        errors.append("campaign must be an object")
        return
    allowed = {"campaign_id", "objective", "organism_or_host", "product_or_response", "current_format", "target_format"}
    errors.extend(f"unknown campaign field: {field}" for field in sorted(set(campaign) - allowed))
    if "campaign_id" in campaign and (not isinstance(campaign.get("campaign_id"), str) or not campaign.get("campaign_id", "").strip()):
        errors.append("campaign.campaign_id must be a non-empty string when provided")


def _validate_routing(routing: Any, errors: list[str]) -> None:
    if not isinstance(routing, dict):
        errors.append("routing must be an object")
        return
    allowed = {"preferred_lane", "preferred_issue_pack", "activate_first_wave_only", "remote_compute_allowed", "linear_project_hint"}
    errors.extend(f"unknown routing field: {field}" for field in sorted(set(routing) - allowed))
    if "preferred_lane" in routing:
        _validate_enum_field(routing, "preferred_lane", LANES, errors, prefix="routing.")
    if "preferred_issue_pack" in routing:
        _validate_enum_field(routing, "preferred_issue_pack", ISSUE_PACKS, errors, prefix="routing.")
    for field in ["activate_first_wave_only", "remote_compute_allowed"]:
        if field in routing and not isinstance(routing.get(field), bool):
            errors.append(f"routing.{field} must be a boolean")


def _validate_safety(data: dict[str, Any], safety: dict[str, Any], errors: list[str]) -> None:
    allowed = {"contains_secrets", "contains_private_process_data", "private_data_handling", "private_data_ref"}
    errors.extend(f"unknown safety field: {field}" for field in sorted(set(safety) - allowed))
    if safety.get("contains_secrets") is not False:
        errors.append("safety.contains_secrets must be false for repository-stored task requests")
    if not isinstance(safety.get("contains_private_process_data"), bool):
        errors.append("safety.contains_private_process_data must be a boolean")
    handling = safety.get("private_data_handling", "not_applicable")
    if handling not in PRIVATE_DATA_HANDLING:
        errors.append("safety.private_data_handling is invalid")
    if data.get("data_classification") == "confidential" and handling != "secure_reference_only":
        errors.append("safety.private_data_handling must be secure_reference_only for confidential requests")
    if safety.get("contains_private_process_data") and handling == "not_applicable":
        errors.append("safety.private_data_handling must describe sensitive process-data handling")
    if handling == "secure_reference_only" and not str(safety.get("private_data_ref", "")).strip():
        errors.append("safety.private_data_ref is required for secure_reference_only handling")


def _missing(data: dict[str, Any], required: set[str]) -> list[str]:
    return [f"missing required field: {field}" for field in sorted(required - set(data))]


def _require_non_empty_string(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(data.get(field), str) or not data.get(field, "").strip():
        errors.append(f"{field} must be a non-empty string")


def _validate_enum_field(data: dict[str, Any], field: str, allowed: set[str], errors: list[str], prefix: str = "") -> None:
    value = data.get(field)
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{prefix}{field} is invalid")


def _classification_text(data: dict[str, Any]) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), list) else []
    pieces = [
        str(data.get("title", "")),
        str(data.get("summary", "")),
        str(task.get("notes", "")),
        " ".join(str(item) for item in task.get("requested_outputs", []) if isinstance(item, str)),
        " ".join(str(item.get("kind", "")) for item in inputs if isinstance(item, dict)),
    ]
    return " ".join(pieces).lower()


def _requested_outputs(data: dict[str, Any]) -> list[str]:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    outputs = task.get("requested_outputs")
    if not isinstance(outputs, list):
        return []
    return [item.strip() for item in outputs if isinstance(item, str) and item.strip()]


def _has_input_kind(data: dict[str, Any], kind: str) -> bool:
    inputs = data.get("inputs")
    if not isinstance(inputs, list):
        return False
    return any(isinstance(item, dict) and item.get("kind") == kind for item in inputs)
