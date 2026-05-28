"""Scientific swarm planning and swarm-to-tournament review logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compiler import compile_campaign_state, normalize_swarm_policy
from .io_utils import markdown_table, parse_number, read_csv, resolve_path, write_csv, write_json


SWARM_DOSSIER_FILES = [
    "evidence_swarm_plan.json",
    "evidence_table_template.csv",
    "evidence_rows.normalized.csv",
    "evidence_ingestion_report.json",
    "factor_universe.json",
    "factor_universe.md",
    "assumption_attack_report.json",
    "assumption_attack_report.md",
    "observability_plan.json",
    "control_run_strategy.json",
    "symphony_agent_graph.json",
    "swarm_adjudication_brief.md",
]

EVIDENCE_TABLE_HEADERS = [
    "lane_id",
    "evidence_id",
    "source_type",
    "source_ref",
    "source_title",
    "source_date",
    "source_trust",
    "license",
    "extraction_method",
    "agent_id",
    "review_status",
    "claim_type",
    "entity_type",
    "claim",
    "factor_or_response",
    "suggested_action",
    "suggested_role",
    "suggested_min",
    "suggested_max",
    "phase",
    "effect_direction",
    "severity",
    "decision_impact",
    "contradiction_group",
    "confidence",
    "caveat",
]

NORMALIZED_EVIDENCE_HEADERS = EVIDENCE_TABLE_HEADERS + [
    "confidence_score",
    "provenance_score",
    "quality_score",
    "quality_label",
    "evidence_weight",
    "provenance_gaps",
    "source_path",
    "row_number",
    "validation_status",
    "validation_messages",
]

FACTOR_CLASSES = {"doe_factor", "fixed_control", "block", "monitor_only", "wave2_candidate", "exclude"}
NON_DOE_FACTOR_CLASSES = {"fixed_control", "monitor_only", "wave2_candidate", "exclude"}

SWARM_ISSUES = [
    {
        "issue_id": "SW-W0-01",
        "title": "Swarm contract and artifact schema",
        "wave": "W0",
        "dependencies": [],
        "artifacts": ["evidence_swarm_plan.json", "symphony_agent_graph.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W1-01",
        "title": "Literature and evidence prior lane",
        "wave": "W1",
        "dependencies": ["SW-W0-01"],
        "artifacts": ["evidence_table_template.csv"],
        "touched_areas": ["ferm-doe-dossier/swarm/evidence/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W1-02",
        "title": "Prior data and source trust lane",
        "wave": "W1",
        "dependencies": ["SW-W0-01"],
        "artifacts": ["evidence_table_template.csv", "evidence_rows.normalized.csv", "evidence_ingestion_report.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/evidence/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W1-03",
        "title": "Assay and product-class skeptic lane",
        "wave": "W1",
        "dependencies": ["SW-W0-01"],
        "artifacts": ["assumption_attack_report.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/assay/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W1-04",
        "title": "Process engineering and scale-transfer lane",
        "wave": "W1",
        "dependencies": ["SW-W0-01"],
        "artifacts": ["observability_plan.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/process/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W1-05",
        "title": "Cost, runability, sampling, and schedule lane",
        "wave": "W1",
        "dependencies": ["SW-W0-01"],
        "artifacts": ["control_run_strategy.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/runability/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W2-01",
        "title": "Factor universe integration",
        "wave": "W2",
        "dependencies": ["SW-W1-01", "SW-W1-02", "SW-W1-04"],
        "artifacts": ["factor_universe.json", "factor_universe.md", "evidence_ingestion_report.json"],
        "touched_areas": ["ferm-doe-dossier/swarm/factor-universe/"],
        "complexity": "large",
    },
    {
        "issue_id": "SW-W2-02",
        "title": "Assumption attack and contradiction reconciliation",
        "wave": "W2",
        "dependencies": ["SW-W1-01", "SW-W1-03", "SW-W1-04", "SW-W1-05"],
        "artifacts": ["assumption_attack_report.json", "assumption_attack_report.md"],
        "touched_areas": ["ferm-doe-dossier/swarm/assumption-attack/"],
        "complexity": "large",
    },
    {
        "issue_id": "SW-W2-03",
        "title": "Observability and control-run strategy",
        "wave": "W2",
        "dependencies": ["SW-W1-03", "SW-W1-04", "SW-W1-05"],
        "artifacts": ["observability_plan.json", "control_run_strategy.json", "selected_wave_1_design.csv"],
        "touched_areas": ["ferm-doe-dossier/swarm/observability/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W3-01",
        "title": "Swarm adjudication brief for DOE tournament",
        "wave": "W3",
        "dependencies": ["SW-W2-01", "SW-W2-02", "SW-W2-03"],
        "artifacts": ["swarm_adjudication_brief.md"],
        "touched_areas": ["ferm-doe-dossier/swarm/"],
        "complexity": "medium",
    },
    {
        "issue_id": "SW-W4-01",
        "title": "Dossier integration and follow-up memory hooks",
        "wave": "W4",
        "dependencies": ["SW-W3-01"],
        "artifacts": ["dossier_manifest.json", "wave_2_decision_rules.md"],
        "touched_areas": ["ferm-doe-dossier/"],
        "complexity": "medium",
    },
]


def swarm_enabled(state: dict[str, Any]) -> bool:
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    return bool(policy.get("enabled"))


def swarm_tournament_enabled(state: dict[str, Any]) -> bool:
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    return swarm_enabled(state) and bool(policy.get("use_swarm_for_tournament", True))


def swarm_factor_universe_enabled(state: dict[str, Any]) -> bool:
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    return swarm_enabled(state) and bool(policy.get("apply_factor_universe_to_design", True))


def compile_swarm_plan(
    manifest_path: Path,
    out_dir: Path,
    state: dict[str, Any] | None = None,
    force: bool = True,
    evidence_tables: list[Path] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    compiled = dict(state) if state is not None else compile_campaign_state(manifest_path, enable_swarm=force)
    policy = compiled.get("swarm_policy") if isinstance(compiled.get("swarm_policy"), dict) else {}
    if force or not policy:
        compiled["swarm_policy"] = normalize_swarm_policy(policy, enable_swarm=True)
    compiled = ensure_swarm_review(manifest_path, compiled, evidence_tables=evidence_tables, force=True)
    write_swarm_artifacts(out_dir, compiled)

    return {
        "schema_version": 1,
        "swarm_plan_kind": "scientific_swarm_plan",
        "campaign_id": compiled["campaign_id"],
        "artifact_count": len(SWARM_DOSSIER_FILES),
        "artifacts": SWARM_DOSSIER_FILES,
        "issue_count": len(SWARM_ISSUES),
        "evidence_rows": compiled["swarm_review"]["evidence_ingestion"]["usable_row_count"],
    }


def ensure_swarm_review(
    manifest_path: Path | None,
    state: dict[str, Any],
    evidence_tables: list[Path] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if not swarm_enabled(state):
        return state
    if state.get("swarm_review") and not force and not evidence_tables:
        return state
    resolved_manifest = manifest_path or Path(str(state.get("source_manifest") or "campaign_manifest.json"))
    compiled = dict(state)
    review = build_swarm_review(resolved_manifest, compiled, evidence_tables=evidence_tables)
    compiled["swarm_review"] = review
    return compiled


def build_swarm_review(
    manifest_path: Path,
    state: dict[str, Any],
    evidence_tables: list[Path] | None = None,
) -> dict[str, Any]:
    evidence_rows, evidence_report = ingest_evidence_tables(manifest_path, state, evidence_tables)
    factor_universe = build_factor_universe(state, evidence_rows, evidence_report)
    attack = build_assumption_attack(state, evidence_rows, evidence_report)
    observability = build_observability_plan(state, evidence_rows)
    controls = build_control_run_strategy(state, evidence_rows, factor_universe)
    return {
        "schema_version": 1,
        "review_kind": "scientific_swarm_review",
        "campaign_id": state["campaign_id"],
        "evidence_ingestion": evidence_report,
        "evidence_rows": evidence_rows,
        "factor_universe": factor_universe,
        "assumption_attack": attack,
        "observability_plan": observability,
        "control_run_strategy": controls,
        "tournament_hints": build_tournament_hints(factor_universe, attack, evidence_rows),
    }


def write_swarm_artifacts(out_dir: Path, state: dict[str, Any]) -> None:
    review = state.get("swarm_review") if isinstance(state.get("swarm_review"), dict) else build_swarm_review(Path(str(state.get("source_manifest") or "")), state)
    plan = build_evidence_swarm_plan(state, review["evidence_ingestion"])
    factor_universe = review["factor_universe"]
    attack = review["assumption_attack"]
    observability = review["observability_plan"]
    controls = review["control_run_strategy"]
    graph = build_symphony_agent_graph(state)
    brief = render_swarm_adjudication_brief(state, factor_universe, attack, observability, controls)

    write_json(out_dir / "campaign_state.json", state)
    write_json(out_dir / "evidence_swarm_plan.json", plan)
    write_csv(out_dir / "evidence_table_template.csv", [], EVIDENCE_TABLE_HEADERS)
    write_csv(out_dir / "evidence_rows.normalized.csv", review["evidence_rows"], NORMALIZED_EVIDENCE_HEADERS)
    write_json(out_dir / "evidence_ingestion_report.json", review["evidence_ingestion"])
    write_json(out_dir / "factor_universe.json", factor_universe)
    (out_dir / "factor_universe.md").write_text(render_factor_universe_md(factor_universe))
    write_json(out_dir / "assumption_attack_report.json", attack)
    (out_dir / "assumption_attack_report.md").write_text(render_assumption_attack_md(attack))
    write_json(out_dir / "observability_plan.json", observability)
    write_json(out_dir / "control_run_strategy.json", controls)
    write_json(out_dir / "symphony_agent_graph.json", graph)
    (out_dir / "swarm_adjudication_brief.md").write_text(brief)


def build_evidence_swarm_plan(state: dict[str, Any], evidence_report: dict[str, Any] | None = None) -> dict[str, Any]:
    lanes = [
        _lane("literature_prior", "Extract published factor ranges, inhibition thresholds, media/feed precedents, and organism/product failure modes.", ["factor_universe.json", "evidence_table_template.csv"]),
        _lane("prior_data_source_trust", "Audit prior ledgers, source labels, inclusion status, and historical comparability.", ["evidence_table_template.csv"]),
        _lane("protocol_vendor_methods", "Capture protocol, reagent, assay, and equipment-method caveats without copying private data.", ["evidence_table_template.csv"]),
        _lane("assay_product_class_skeptic", "Challenge response semantics, sample fraction, matrix effects, calibration, extraction recovery, and turnaround.", ["assumption_attack_report.json"]),
        _lane("process_engineering_scale_transfer", "Challenge oxygen, pH/base, feedability, foam, phase transfer, and vessel-control assumptions.", ["observability_plan.json"]),
        _lane("cost_runability_schedule", "Challenge sampling load, operator burden, run duration, media/control cost, and reactor availability.", ["control_run_strategy.json"]),
    ]
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    return {
        "schema_version": 1,
        "plan_kind": "evidence_swarm_plan",
        "campaign_id": state["campaign_id"],
        "dry_run_only": True,
        "lanes": [lane for lane in lanes if lane["lane_id"] in set(policy.get("lanes", [])) or not policy.get("lanes")],
        "evidence_table_headers": EVIDENCE_TABLE_HEADERS,
        "evidence_ingestion": {
            "configured_table_count": len(evidence_report.get("evidence_table_paths", [])) if evidence_report else 0,
            "usable_row_count": evidence_report.get("usable_row_count", 0) if evidence_report else 0,
            "conflict_count": len(evidence_report.get("conflicts", [])) if evidence_report else 0,
        },
        "no_live_search_policy": "The core engine does not perform unbounded live search. Evidence execution is agent-lane powered through Scientific Swarm or evidence-executor sidecars; the engine ingests local rows with provenance, confidence, contradictions, and decision impact.",
    }


def ingest_evidence_tables(
    manifest_path: Path,
    state: dict[str, Any],
    evidence_tables: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = configured_evidence_paths(manifest_path, state, evidence_tables)
    factor_ids = {factor["factor_id"] for factor in state.get("factors", [])}
    response_ids = {response["response_id"] for response in state.get("responses", [])}
    known_entities = factor_ids | response_ids
    normalized: list[dict[str, Any]] = []
    missing_paths: list[str] = []
    load_errors: list[dict[str, str]] = []
    for path in paths:
        if not path.exists():
            missing_paths.append(str(path))
            continue
        try:
            raw_rows = read_evidence_rows(path)
        except Exception as exc:  # pragma: no cover - defensive file parsing
            load_errors.append({"path": str(path), "error": str(exc)})
            continue
        for index, raw in enumerate(raw_rows, start=1):
            row = normalize_evidence_row(raw, path, index, known_entities)
            normalized.append(row)
    conflicts = evidence_conflicts(normalized)
    unknown_entities = sorted(
        {
            str(row.get("factor_or_response"))
            for row in normalized
            if row.get("factor_or_response") and "unknown_entity" in str(row.get("validation_messages", ""))
        }
    )
    usable_rows = [row for row in normalized if row.get("validation_status") == "usable"]
    report = {
        "schema_version": 1,
        "report_kind": "scientific_swarm_evidence_ingestion",
        "campaign_id": state["campaign_id"],
        "evidence_table_paths": [str(path) for path in paths],
        "loaded_row_count": len(normalized),
        "usable_row_count": len(usable_rows),
        "malformed_row_count": sum(1 for row in normalized if row.get("validation_status") != "usable"),
        "missing_paths": missing_paths,
        "load_errors": load_errors,
        "unknown_entities": unknown_entities,
        "conflicts": conflicts,
        "entity_counts": _entity_counts(usable_rows),
        "role_suggestions": _role_suggestions(usable_rows),
        "quality_summary": evidence_quality_summary(normalized),
        "provenance_gaps": evidence_provenance_gap_summary(normalized),
        "policy": "Rows are local cached evidence returned by agents, users, or optional evidence-executor sidecars; the core engine performs no live web search.",
    }
    return normalized, report


def configured_evidence_paths(manifest_path: Path, state: dict[str, Any], evidence_tables: list[Path] | None = None) -> list[Path]:
    base = manifest_path.parent if manifest_path else Path.cwd()
    raw_paths: list[str] = []
    policy = state.get("swarm_policy") if isinstance(state.get("swarm_policy"), dict) else {}
    raw_paths.extend(str(path) for path in policy.get("evidence_tables", []) if path)
    for item in state.get("inputs", []):
        text = " ".join(str(item.get(key, "")) for key in ["input_id", "kind", "path"]).lower()
        if "evidence" in text or "swarm" in text:
            raw_paths.append(str(item.get("path") or ""))
    raw_paths.extend(str(path) for path in evidence_tables or [])
    resolved: list[Path] = []
    seen: set[str] = set()
    for raw in raw_paths:
        path = resolve_path(raw, base)
        if not path:
            continue
        key = str(path)
        if key not in seen:
            resolved.append(path)
            seen.add(key)
    return resolved


def read_evidence_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("evidence") or data.get("items") or []
        else:
            rows = data
        return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []
    rows, _ = read_csv(path)
    return rows


def normalize_evidence_row(raw: dict[str, Any], source_path: Path, row_number: int, known_entities: set[str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for header in EVIDENCE_TABLE_HEADERS:
        normalized[header] = str(raw.get(header) or "").strip()
    normalized["evidence_id"] = normalized["evidence_id"] or f"{source_path.stem}-{row_number:03d}"
    normalized["confidence_score"] = round(confidence_score(normalized["confidence"]), 4)
    provenance = provenance_score(normalized)
    quality = evidence_quality_score(normalized, provenance)
    normalized["provenance_score"] = round(provenance, 4)
    normalized["quality_score"] = round(quality, 4)
    normalized["quality_label"] = quality_label(quality)
    normalized["evidence_weight"] = round(quality, 4)
    normalized["provenance_gaps"] = ";".join(provenance_gaps(normalized))
    normalized["source_path"] = str(source_path)
    normalized["row_number"] = row_number
    messages: list[str] = []
    if not normalized["claim"]:
        messages.append("missing_claim")
    entity = normalized["factor_or_response"]
    if not entity:
        messages.append("missing_factor_or_response")
    elif entity not in known_entities:
        messages.append("unknown_entity")
    if normalized["suggested_role"] and role_from_text(normalized["suggested_role"]) not in FACTOR_CLASSES:
        messages.append("unknown_suggested_role")
    if normalized["suggested_min"] and parse_number(normalized["suggested_min"]) is None:
        messages.append("non_numeric_suggested_min")
    if normalized["suggested_max"] and parse_number(normalized["suggested_max"]) is None:
        messages.append("non_numeric_suggested_max")
    review_status = str(normalized.get("review_status") or "").lower()
    if review_status in {"rejected", "excluded"}:
        messages.append("review_rejected")
        status = "excluded"
    else:
        status = "usable" if not messages else "malformed"
    normalized["validation_status"] = status
    normalized["validation_messages"] = ";".join(messages)
    return normalized


def confidence_score(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        return 0.5
    numeric = parse_number(text)
    if numeric is not None:
        return max(0.0, min(1.0, float(numeric) / 100.0 if float(numeric) > 1 else float(numeric)))
    return {
        "very_high": 0.95,
        "high": 0.85,
        "medium": 0.6,
        "moderate": 0.6,
        "low": 0.35,
        "weak": 0.25,
    }.get(text.replace("-", "_"), 0.5)


def confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def quality_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    if score > 0:
        return "low"
    return "excluded"


def source_trust_score(row: dict[str, Any]) -> float:
    explicit = confidence_score(row.get("source_trust"))
    if row.get("source_trust"):
        return explicit
    source_type = str(row.get("source_type") or "").strip().lower()
    if source_type in {"prior_run", "prior_run_ledger", "historical_run", "trusted_internal"}:
        return 0.85
    if source_type in {"peer_reviewed", "paper", "literature", "publication"}:
        return 0.8
    if source_type in {"vendor_protocol", "protocol", "method"}:
        return 0.7
    if source_type in {"agent_summary", "symphony_worker", "codex_worker"}:
        return 0.6
    if source_type in {"guess", "unreviewed_note"}:
        return 0.25
    return 0.45


def review_status_score(row: dict[str, Any]) -> float:
    status = str(row.get("review_status") or "").strip().lower()
    if status in {"accepted", "curated", "reviewed", "approved"}:
        return 0.9
    if status in {"needs_review", "unreviewed", "draft", ""}:
        return 0.55
    if status in {"rejected", "excluded"}:
        return 0.0
    return 0.5


def provenance_gaps(row: dict[str, Any]) -> list[str]:
    gaps = []
    for field in ["source_type", "source_ref", "claim_type"]:
        if not row.get(field):
            gaps.append(f"missing_{field}")
    if not row.get("license") and str(row.get("source_type") or "").lower() in {"paper", "literature", "publication", "peer_reviewed"}:
        gaps.append("missing_license")
    if not row.get("extraction_method") and str(row.get("source_type") or "").lower() in {"agent_summary", "symphony_worker", "codex_worker"}:
        gaps.append("missing_extraction_method")
    if not row.get("review_status"):
        gaps.append("missing_review_status")
    return gaps


def provenance_score(row: dict[str, Any]) -> float:
    source_ref = 1.0 if row.get("source_ref") else 0.0
    source_type = 1.0 if row.get("source_type") else 0.0
    claim_type = 1.0 if row.get("claim_type") else 0.0
    license_or_internal = 1.0 if row.get("license") or str(row.get("source_type") or "").lower() in {"prior_run", "prior_run_ledger", "trusted_internal"} else 0.55
    extraction = 1.0 if row.get("extraction_method") or str(row.get("source_type") or "").lower() not in {"agent_summary", "symphony_worker", "codex_worker"} else 0.55
    score = (
        0.30 * source_trust_score(row)
        + 0.20 * source_ref
        + 0.15 * source_type
        + 0.10 * claim_type
        + 0.10 * license_or_internal
        + 0.10 * extraction
        + 0.05 * review_status_score(row)
    )
    return max(0.0, min(1.0, score))


def evidence_quality_score(row: dict[str, Any], provenance: float) -> float:
    score = (
        0.45 * float(row.get("confidence_score") or 0.5)
        + 0.35 * provenance
        + 0.15 * source_trust_score(row)
        + 0.05 * review_status_score(row)
    )
    return max(0.0, min(1.0, score))


def evidence_conflicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = [row for row in rows if row.get("validation_status") == "usable"]
    conflicts: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in usable:
        explicit = str(row.get("contradiction_group") or "").strip()
        key = explicit or f"entity:{row.get('factor_or_response')}"
        grouped.setdefault(key, []).append(row)
    for key, group in grouped.items():
        roles = sorted({role_from_text(row.get("suggested_role") or row.get("suggested_action")) for row in group if role_from_text(row.get("suggested_role") or row.get("suggested_action"))})
        severities = sorted({str(row.get("severity") or "").lower() for row in group if row.get("severity")})
        mins = {str(row.get("suggested_min")) for row in group if row.get("suggested_min")}
        maxes = {str(row.get("suggested_max")) for row in group if row.get("suggested_max")}
        explicit_group = not key.startswith("entity:")
        role_conflict = len(set(roles) - {""}) > 1
        range_conflict = len(mins) > 1 or len(maxes) > 1
        if explicit_group and len(group) > 1 or role_conflict or range_conflict:
            conflicts.append(
                {
                    "conflict_id": key,
                    "entities": sorted({str(row.get("factor_or_response")) for row in group if row.get("factor_or_response")}),
                    "evidence_ids": [str(row.get("evidence_id")) for row in group],
                    "roles": roles,
                    "severities": severities,
                    "range_conflict": range_conflict,
                    "role_conflict": role_conflict,
                }
            )
    return conflicts


def evidence_quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row.get("validation_status") == "usable"]
    if not usable:
        return {"usable_rows": 0, "mean_quality_score": 0.0, "high_quality_rows": 0, "medium_quality_rows": 0, "low_quality_rows": 0}
    scores = [float(row.get("quality_score") or 0.0) for row in usable]
    return {
        "usable_rows": len(usable),
        "mean_quality_score": round(sum(scores) / len(scores), 4),
        "high_quality_rows": sum(1 for score in scores if score >= 0.8),
        "medium_quality_rows": sum(1 for score in scores if 0.6 <= score < 0.8),
        "low_quality_rows": sum(1 for score in scores if score < 0.6),
    }


def evidence_provenance_gap_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for gap in str(row.get("provenance_gaps") or "").split(";"):
            if gap:
                counts[gap] = counts.get(gap, 0) + 1
    return counts


def build_factor_universe(
    state: dict[str, Any],
    evidence_rows: list[dict[str, Any]] | None = None,
    evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_rows = evidence_rows or []
    conflicts = evidence_report.get("conflicts", []) if evidence_report else []
    factors = []
    for factor in state.get("factors", []):
        manifest_classification = classify_factor(factor)
        linked_rows = factor_evidence_rows(factor["factor_id"], evidence_rows)
        evidence_classification, evidence_score = evidence_classification_for(linked_rows)
        factor_conflicts = conflicts_for_entity(factor["factor_id"], conflicts)
        final_classification = final_factor_classification(manifest_classification, evidence_classification, evidence_score, factor_conflicts)
        range_recommendation = factor_range_recommendation(factor, linked_rows, bool(factor_conflicts))
        confidence = factor_confidence(manifest_classification, evidence_score, factor_conflicts, linked_rows)
        factors.append(
            {
                "factor_id": factor["factor_id"],
                "name": factor.get("name", factor["factor_id"]),
                "classification": final_classification,
                "manifest_classification": manifest_classification,
                "evidence_classification": evidence_classification or "",
                "final_classification": final_classification,
                "type": factor.get("type", ""),
                "phase": factor.get("phase", "unspecified"),
                "unit": factor.get("unit", ""),
                "bounds": {"min": factor.get("min"), "max": factor.get("max")},
                "levels": factor.get("levels", []),
                "confidence": confidence_label(confidence),
                "confidence_score": round(confidence, 4),
                "evidence_count": len(linked_rows),
                "evidence_refs": [row.get("evidence_id") for row in linked_rows] or [factor.get("source") or "manifest"],
                "evidence_actions": evidence_actions(linked_rows),
                "conflicts": factor_conflicts,
                "range_recommendation": range_recommendation,
                "doe_implication": factor_doe_implication(final_classification, range_recommendation, bool(factor_conflicts)),
                "rationale": factor_classification_rationale(factor, manifest_classification, evidence_classification, final_classification, linked_rows, factor_conflicts),
            }
        )
    counts: dict[str, int] = {}
    for item in factors:
        counts[item["final_classification"]] = counts.get(item["final_classification"], 0) + 1
    return {
        "schema_version": 1,
        "universe_kind": "scientific_swarm_factor_universe",
        "campaign_id": state["campaign_id"],
        "classification_counts": counts,
        "evidence_row_count": sum(item["evidence_count"] for item in factors),
        "conflict_count": len(conflicts),
        "quality_summary": evidence_report.get("quality_summary", {}) if evidence_report else {},
        "provenance_gaps": evidence_report.get("provenance_gaps", {}) if evidence_report else {},
        "factors": factors,
        "evidence_only_items": evidence_only_items(state, evidence_rows),
    }


def apply_factor_universe_to_factors(factors: list[dict[str, Any]], factor_universe: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not factor_universe:
        return [dict(factor) for factor in factors]
    by_id = {item["factor_id"]: item for item in factor_universe.get("factors", [])}
    transformed: list[dict[str, Any]] = []
    doe_count = 0
    for factor in factors:
        item = by_id.get(factor.get("factor_id"))
        updated = dict(factor)
        if item:
            final_class = str(item.get("final_classification") or item.get("classification") or "")
            updated["swarm_final_classification"] = final_class
            if final_class == "doe_factor":
                doe_count += 1
                updated["role"] = "candidate"
                recommendation = item.get("range_recommendation") if isinstance(item.get("range_recommendation"), dict) else {}
                if recommendation.get("changed"):
                    if recommendation.get("final_min") not in {None, ""}:
                        updated["min"] = recommendation["final_min"]
                    if recommendation.get("final_max") not in {None, ""}:
                        updated["max"] = recommendation["final_max"]
            elif final_class == "block":
                updated["role"] = "block_only"
            else:
                updated["role"] = "excluded"
        transformed.append(updated)
    return transformed if doe_count else [dict(factor) for factor in factors]


def classify_factor(factor: dict[str, Any]) -> str:
    role = str(factor.get("role") or "").lower()
    factor_type = str(factor.get("type") or "").lower()
    if role in {"exclude", "excluded"}:
        return "exclude"
    if role in {"monitor", "monitor_only"}:
        return "monitor_only"
    if bool(factor.get("block")) or factor_type == "block":
        return "block"
    if bool(factor.get("hard_to_change")):
        return "block"
    if role in {"fixed", "control", "fixed_control"} or not bool(factor.get("controllable", True)):
        return "fixed_control"
    if role in {"wave2", "wave2_candidate", "defer"}:
        return "wave2_candidate"
    has_bounds = factor.get("min") is not None and factor.get("max") is not None
    has_levels = bool(factor.get("levels"))
    if has_bounds or has_levels or factor_type in {"mixture", "categorical", "ordinal"}:
        return "doe_factor"
    return "wave2_candidate"


def build_assumption_attack(
    state: dict[str, Any],
    evidence_rows: list[dict[str, Any]] | None = None,
    evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    challenges: list[dict[str, Any]] = []
    for index, item in enumerate(state.get("missing_info", []), start=1):
        challenges.append(
            challenge(
                index,
                "readiness_gap",
                item.get("severity", "warning"),
                f"{item.get('field')} can be left unresolved.",
                item.get("reason", "Missing information can invalidate the design."),
                [item.get("field", "")],
                "Resolve before GREEN readiness or keep as an explicit dossier caveat.",
            )
        )
    next_index = len(challenges) + 1
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    product_text = " ".join(str(value) for value in [state.get("name", ""), *context.values()]).lower()
    response_text = " ".join(" ".join(str(value) for value in response.values()) for response in state.get("responses", [])).lower()
    if any(token in product_text + " " + response_text for token in ["hydrophobic", "pellet", "intracellular"]):
        challenges.append(
            challenge(
                next_index,
                "assay_product_class",
                "warning",
                "The measured response represents true whole-broth or pellet-associated product titer.",
                "Hydrophobic or pellet-associated products can bias extraction, fraction choice, and apparent titer.",
                [response.get("response_id", "") for response in state.get("responses", [])],
                "Require extraction recovery, matrix spike, and sample-fraction agreement before treating titer as optimization truth.",
            )
        )
        next_index += 1
    for constraint in state.get("constraints", []):
        if constraint.get("kind") != "safety_decoy":
            continue
        constraint_id = str(constraint.get("constraint_id") or "safety_decoy_constraint")
        constraint_keywords = derive_safety_decoy_keywords(constraint)
        evidence_check = validate_evidence_quality_for_safety_decoy(
            evidence_rows or [], constraint_keywords
        )
        description = str(constraint.get("description") or constraint_id)
        affected = sorted(_safety_decoy_affected_factors(state, constraint, constraint_keywords))
        challenges.append(
            challenge(
                next_index,
                "decoy_constraint_gap",
                "warning",
                f"Literature directly addresses the {constraint_id} condition without a methodological leap.",
                (
                    f"The {constraint_id} constraint is a deliberate literature gap ({description}). "
                    "Swarm agents must flag the gap explicitly rather than fabricate citations or extrapolate "
                    "from adjacent literature without acknowledging the methodological leap. "
                    f"Decoy-related evidence: {evidence_check['total_related_rows']} total rows, "
                    f"{evidence_check['properly_flagged_rows']} properly flagged with gap/extrapolated/insufficient markers, "
                    f"{evidence_check['unflagged_rows']} unflagged."
                ),
                affected or [constraint_id],
                (
                    "Every evidence row related to this safety_decoy constraint MUST explicitly note evidence "
                    "quality as 'gap', 'extrapolated', or 'insufficient' in the caveat field or quality_label. "
                    "Do NOT present adjacent-domain citations as direct support for the decoy condition."
                ),
            )
        )
        next_index += 1
    selected_modes = set(state.get("workflow_modes", {}).get("selected", []))
    if "shake-flask-to-bioreactor" in selected_modes or "batch-to-fedbatch-production" in selected_modes:
        challenges.append(
            challenge(
                next_index,
                "process_scale_transfer",
                "warning",
                "Flask behavior transfers cleanly to controlled bioreactor batch and production phases.",
                "pH control, oxygen transfer, feed timing, foam, and induction can change the limiting mechanism.",
                [factor["factor_id"] for factor in state.get("factors", []) if factor.get("phase") in {"growth", "production", "switch", "growth_and_production"}],
                "Run a reactor baseline and bridge controls before trusting broad DOE variation.",
            )
        )
        next_index += 1
    if any("sampling" in str(value).lower() for value in state.values()) or state.get("responses"):
        challenges.append(
            challenge(
                next_index,
                "runability_sampling",
                "warning",
                "Sampling and analytics cadence can support every response without distorting the run.",
                "Frequent offline sampling, extraction assays, and endpoint productivity calculations can overload operators or miss phase events.",
                [response.get("response_id", "") for response in state.get("responses", [])],
                "Tie sampling events to decisions, assay turnaround, and minimum reactor-volume impact.",
            )
        )
        next_index += 1
    if any("cost" in str(value).lower() for value in state.get("constraints", []) + state.get("responses", [])):
        challenges.append(
            challenge(
                next_index,
                "cost_time",
                "warning",
                "The highest endpoint titer is the best campaign outcome.",
                "A shorter run with lower endpoint titer can win on productivity or cost per liter.",
                [state.get("objective", {}).get("response_id", "")],
                "Score titer, productivity, run duration, and cost together before selecting follow-up.",
            )
        )
        next_index += 1
    for conflict in (evidence_report or {}).get("conflicts", []):
        challenges.append(
            challenge(
                next_index,
                "evidence_contradiction",
                "warning",
                f"Evidence for {', '.join(conflict.get('entities', [])) or conflict.get('conflict_id')} is internally consistent.",
                "Contradictory evidence can push the DOE toward a factor range or role that is not defensible.",
                conflict.get("entities", []),
                "Resolve the contradiction or keep the affected factor conservative before first-batch.",
            )
        )
        next_index += 1
    for row in evidence_rows or []:
        if row.get("validation_status") != "usable":
            continue
        severity = str(row.get("severity") or "").lower()
        impact = str(row.get("decision_impact") or "").lower()
        quality = float(row.get("quality_score") or row.get("confidence_score") or 0.0)
        high_impact = severity in {"blocker", "critical"} or impact in {"hard_constraint", "blocker", "stop"}
        if high_impact and quality >= 0.7:
            challenges.append(
                challenge(
                    next_index,
                    str(row.get("claim_type") or "evidence_backed_constraint"),
                    severity or "blocker",
                    str(row.get("claim") or "Evidence-backed constraint can be ignored."),
                    str(row.get("caveat") or "Evidence row declares a high-impact decision constraint."),
                    [str(row.get("factor_or_response") or "")],
                    str(row.get("suggested_action") or "Respect this evidence before selecting an executable DOE."),
                )
            )
            next_index += 1
        elif high_impact:
            challenges.append(
                challenge(
                    next_index,
                    "evidence_provenance_gap",
                    "warning",
                    str(row.get("claim") or "High-impact evidence is trusted enough to guide first-batch."),
                    "The evidence row requests a hard decision but has low provenance or quality score.",
                    [str(row.get("factor_or_response") or "")],
                    "Escalate to a Symphony evidence worker before treating this as a veto or hard constraint.",
                )
            )
            next_index += 1
    return {
        "schema_version": 1,
        "report_kind": "scientific_swarm_assumption_attack",
        "campaign_id": state["campaign_id"],
        "challenge_count": len(challenges),
        "blocker_count": sum(1 for item in challenges if str(item.get("severity")).lower() in {"blocker", "critical"}),
        "challenges": challenges,
    }


def build_observability_plan(state: dict[str, Any], evidence_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    measurements: list[dict[str, Any]] = []
    context = state.get("campaign_context") if isinstance(state.get("campaign_context"), dict) else {}
    observed_text = " ".join(str(value) for value in [*state.values(), *context.values()]).lower()
    if "do" in observed_text or "oxygen" in observed_text:
        measurements.append(measurement("do", "online", "oxygen-transfer and oxygen-limitation proxy", "Cannot prove intracellular flux or product toxicity alone."))
    if "ph" in observed_text:
        measurements.append(measurement("ph", "online", "acid/base demand, growth state, and control stability", "Setpoint compliance does not prove comparable metabolic state."))
    if "offgas" in observed_text or "co2" in observed_text or "o2" in observed_text:
        measurements.append(measurement("offgas_o2_co2", "online", "respiration, oxygen uptake, carbon dioxide evolution, and phase changes", "Needs alignment with feed and biomass data."))
    if any("temp" in factor.get("factor_id", "") or "temperature" in factor.get("name", "").lower() for factor in state.get("factors", [])):
        measurements.append(measurement("temperature", "online", "thermal control and response-surface factor compliance", "Does not explain production response without phase labels."))
    if "biomass" in observed_text or any(response.get("class") == "productivity" for response in state.get("responses", [])):
        measurements.append(measurement("biomass", "offline", "growth trajectory, product-per-biomass normalization, and phase switch context", "Four-hour cadence can miss sharp transitions."))
    for response in state.get("responses", []):
        response_class = response.get("class", "unknown")
        if response_class in {"titer", "productivity", "yield", "quality", "activity"}:
            measurements.append(measurement(response["response_id"], "offline", f"{response_class} decision response", "Assay readiness and sample fraction must match response semantics."))
    for row in evidence_rows or []:
        if row.get("validation_status") == "usable" and str(row.get("entity_type") or "").lower() == "measurement":
            measurements.append(measurement(str(row.get("factor_or_response")), "evidence", str(row.get("claim")), str(row.get("caveat") or "Evidence-derived measurement claim.")))
    unobservable = [
        "intracellular toxicity or pathway bottleneck without targeted byproduct/substrate/product-per-biomass data",
        "oxygen limitation mechanism without kLa/OTR proxy or comparable agitation/aeration context",
    ]
    coverage = observability_coverage_score(state, measurements, unobservable)
    return {
        "schema_version": 1,
        "plan_kind": "scientific_swarm_observability_plan",
        "campaign_id": state["campaign_id"],
        "measurements": measurements,
        "unobservable_risks": unobservable,
        "coverage_score": coverage,
        "weak_proxy_policy": "A measurement can guide DOE only when the decision it supports is named explicitly.",
    }


def build_control_run_strategy(
    state: dict[str, Any],
    evidence_rows: list[dict[str, Any]] | None = None,
    factor_universe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    controls = [
        control("baseline", "current_recipe_or_best_known_condition", 1, "Anchor first-batch against the known process before expansion."),
        control("center", "midpoint_of_primary_doe_factors", 2, "Estimate repeatability, drift, and assay/process noise at the design center."),
        control("assay_control", "matrix_spike_or_extraction_recovery", 1, "Protect response interpretation for product-class and matrix effects."),
        control("repeat", "selected_center_or_baseline_repeat", 1, "Separate real factor effects from day/run/operator noise."),
    ]
    selected_modes = set(state.get("workflow_modes", {}).get("selected", []))
    if "shake-flask-to-bioreactor" in selected_modes:
        controls.insert(1, control("bridge", "shake_flask_to_bioreactor_baseline_bridge", 1, "Make transfer from flask recipe to controlled reactor interpretable."))
    if "batch-to-fedbatch-production" in selected_modes:
        controls.append(control("phase_switch_control", "standard_induction_and_feed_switch", 1, "Anchor growth-to-production transition before varying feed or inducer policy."))
    if factor_universe and factor_universe.get("conflict_count"):
        controls.append(control("contradiction_resolution", "affected_factor_center_or_safe_bound", 1, "Keep evidence-conflicted factors interpretable in first-batch."))
    for row in evidence_rows or []:
        if row.get("validation_status") == "usable" and role_from_text(row.get("suggested_role")) == "fixed_control":
            controls.append(control("evidence_fixed_control", str(row.get("factor_or_response")), 1, str(row.get("claim") or "Evidence recommends fixing this factor.")))
    return {
        "schema_version": 1,
        "strategy_kind": "scientific_swarm_control_run_strategy",
        "campaign_id": state["campaign_id"],
        "controls": controls,
        "required_center_points": sum(int(item.get("count", 0)) for item in controls if item.get("control_type") == "center"),
        "required_repeats": sum(int(item.get("count", 0)) for item in controls if item.get("control_type") == "repeat"),
        "randomization_note": "Controls should be interleaved where feasible, but hard-to-change vessel and phase constraints can override full randomization.",
    }


def build_symphony_agent_graph(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "graph_kind": "scientific_swarm_symphony_agent_graph",
        "campaign_id": state["campaign_id"],
        "dry_run_only": True,
        "parallelism_policy": {
            "W0": 1,
            "W1": 5,
            "W2": 3,
            "W3": 1,
            "W4": 1,
        },
        "issues": SWARM_ISSUES,
        "note": "This graph is a local dry-run planning artifact. It does not create Linear issues or launch Symphony.",
    }


def build_tournament_hints(factor_universe: dict[str, Any], attack: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    constrained_factors = [
        row.get("factor_or_response")
        for row in evidence_rows
        if row.get("validation_status") == "usable"
        and (str(row.get("severity") or "").lower() in {"blocker", "critical"} or str(row.get("decision_impact") or "").lower() in {"hard_constraint", "blocker", "stop"})
    ]
    return {
        "schema_version": 1,
        "hint_kind": "scientific_swarm_tournament_hints",
        "excluded_or_fixed_factors": [
            item["factor_id"]
            for item in factor_universe.get("factors", [])
            if item.get("final_classification") in NON_DOE_FACTOR_CLASSES
        ],
        "blocker_challenges": [
            item["challenge_id"]
            for item in attack.get("challenges", [])
            if str(item.get("severity") or "").lower() in {"blocker", "critical"}
        ],
        "evidence_backed_constraint_factors": sorted({str(item) for item in constrained_factors if item}),
    }


def render_factor_universe_md(factor_universe: dict[str, Any]) -> str:
    rows = [
        [
            item["factor_id"],
            item["manifest_classification"],
            item["final_classification"],
            item["phase"],
            item["confidence"],
            item["evidence_count"],
            item["doe_implication"],
        ]
        for item in factor_universe.get("factors", [])
    ]
    return "# Factor Universe\n\n" + markdown_table(["Factor", "Manifest", "Final", "Phase", "Confidence", "Evidence", "DOE implication"], rows) + "\n"


def render_assumption_attack_md(report: dict[str, Any]) -> str:
    rows = [
        [item["challenge_id"], item["category"], item["severity"], item["assumption_under_attack"], item["recommended_action"]]
        for item in report.get("challenges", [])
    ]
    return "# Assumption Attack Report\n\n" + markdown_table(["ID", "Category", "Severity", "Assumption", "Action"], rows) + "\n"


def render_swarm_adjudication_brief(
    state: dict[str, Any],
    factor_universe: dict[str, Any],
    attack: dict[str, Any],
    observability: dict[str, Any],
    controls: dict[str, Any],
) -> str:
    factor_counts = ", ".join(f"{key}: {value}" for key, value in sorted(factor_universe.get("classification_counts", {}).items()))
    top_challenges = attack.get("challenges", [])[:5]
    challenge_rows = [[item["category"], item["severity"], item["recommended_action"]] for item in top_challenges]
    measurement_rows = [[item["measurement_id"], item["kind"], item["decision_value"]] for item in observability.get("measurements", [])]
    control_rows = [[item["control_type"], item["count"], item["purpose"]] for item in controls.get("controls", [])]
    return (
        "# Swarm Adjudication Brief\n\n"
        f"- Campaign: {state['campaign_id']}\n"
        f"- Factor classifications: {factor_counts or 'none'}\n"
        f"- Evidence rows: {factor_universe.get('evidence_row_count', 0)}\n"
        f"- Evidence quality: {factor_universe.get('quality_summary', {}).get('mean_quality_score', 0)} mean quality score\n"
        f"- Evidence conflicts: {factor_universe.get('conflict_count', 0)}\n"
        f"- Assumption challenges: {attack.get('challenge_count', 0)}\n"
        f"- Observability coverage: {observability.get('coverage_score', '')}\n\n"
        "## Top Assumption Challenges\n\n"
        + markdown_table(["Category", "Severity", "Action"], challenge_rows)
        + "\n\n## Observability Map\n\n"
        + markdown_table(["Measurement", "Kind", "Decision value"], measurement_rows)
        + "\n\n## Control Strategy\n\n"
        + markdown_table(["Control", "Count", "Purpose"], control_rows)
        + "\n"
    )


def factor_classification_rationale(
    factor: dict[str, Any],
    manifest_classification: str,
    evidence_classification: str,
    final_classification: str,
    rows: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> str:
    if conflicts:
        return "Evidence is conflicting; keep the manifest role conservative until the contradiction is resolved."
    if evidence_classification and evidence_classification != manifest_classification:
        return f"Evidence suggests {evidence_classification}; final classification is {final_classification} based on confidence and conflict policy."
    if final_classification == "doe_factor":
        return "Manifest and/or evidence provides controllable bounds or levels suitable for first-batch DOE consideration."
    if final_classification == "fixed_control":
        return "Factor is fixed, non-controllable, or evidence recommends holding it as a control."
    if final_classification == "block":
        return "Factor is hard to change or blocks/randomization groups should account for it."
    if final_classification == "monitor_only":
        return "Factor is useful context but should be observed rather than varied."
    if final_classification == "exclude":
        return "Factor is explicitly excluded or evidence recommends excluding it from this campaign."
    if rows:
        return "Evidence exists but does not yet justify first-batch variation."
    return "Insufficient bounds or evidence; keep as a follow-up candidate until the swarm resolves it."


def factor_doe_implication(classification: str, range_recommendation: dict[str, Any], has_conflict: bool) -> str:
    if has_conflict:
        return "do_not_expand_until_conflict_resolved"
    if classification == "doe_factor" and range_recommendation.get("changed"):
        return "vary_in_tightened_evidence_range"
    if classification == "doe_factor":
        return "eligible_for_wave1_variation"
    if classification == "fixed_control":
        return "hold_fixed_or_control"
    if classification == "block":
        return "model_as_block_or_hard_to_change"
    if classification == "monitor_only":
        return "measure_but_do_not_vary"
    if classification == "exclude":
        return "exclude_from_design"
    return "defer_to_wave2"


def factor_evidence_rows(factor_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("validation_status") == "usable" and row.get("factor_or_response") == factor_id]


def evidence_classification_for(rows: list[dict[str, Any]]) -> tuple[str, float]:
    scores: dict[str, float] = {}
    for row in rows:
        role = role_from_text(row.get("suggested_role") or row.get("suggested_action"))
        if role in FACTOR_CLASSES:
            scores[role] = scores.get(role, 0.0) + float(row.get("quality_score") or row.get("confidence_score") or 0.5)
    if not scores:
        return "", 0.0
    role, score = max(scores.items(), key=lambda item: (item[1], item[0]))
    return role, min(1.0, score / max(1.0, sum(scores.values())))


def role_from_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "vary": "doe_factor",
        "doe": "doe_factor",
        "doe_factor": "doe_factor",
        "candidate": "doe_factor",
        "fix": "fixed_control",
        "fixed": "fixed_control",
        "control": "fixed_control",
        "fixed_control": "fixed_control",
        "block": "block",
        "hard_to_change": "block",
        "monitor": "monitor_only",
        "monitor_only": "monitor_only",
        "wave2": "wave2_candidate",
        "wave_2": "wave2_candidate",
        "wave2_candidate": "wave2_candidate",
        "defer": "wave2_candidate",
        "exclude": "exclude",
        "excluded": "exclude",
        "drop": "exclude",
    }
    return aliases.get(text, text)


def final_factor_classification(manifest_class: str, evidence_class: str, evidence_score: float, conflicts: list[dict[str, Any]]) -> str:
    if conflicts:
        return manifest_class
    if evidence_class in FACTOR_CLASSES and evidence_score >= 0.7:
        return evidence_class
    return manifest_class


def factor_range_recommendation(factor: dict[str, Any], rows: list[dict[str, Any]], has_conflict: bool) -> dict[str, Any]:
    manifest_min = factor.get("min")
    manifest_max = factor.get("max")
    mins = [parse_number(row.get("suggested_min")) for row in rows if float(row.get("quality_score") or row.get("confidence_score") or 0.0) >= 0.7 and parse_number(row.get("suggested_min")) is not None]
    maxes = [parse_number(row.get("suggested_max")) for row in rows if float(row.get("quality_score") or row.get("confidence_score") or 0.0) >= 0.7 and parse_number(row.get("suggested_max")) is not None]
    evidence_min = max(mins) if mins else None
    evidence_max = min(maxes) if maxes else None
    final_min = manifest_min
    final_max = manifest_max
    policy = "manifest_bounds"
    if not has_conflict:
        if evidence_min is not None:
            final_min = max(float(manifest_min), evidence_min) if manifest_min is not None else evidence_min
            policy = "tightened_by_high_confidence_evidence"
        if evidence_max is not None:
            final_max = min(float(manifest_max), evidence_max) if manifest_max is not None else evidence_max
            policy = "tightened_by_high_confidence_evidence"
    changed = final_min != manifest_min or final_max != manifest_max
    return {
        "manifest_min": manifest_min,
        "manifest_max": manifest_max,
        "evidence_min": evidence_min,
        "evidence_max": evidence_max,
        "final_min": final_min,
        "final_max": final_max,
        "changed": bool(changed),
        "policy": "conflict_no_change" if has_conflict else policy,
    }


def factor_confidence(manifest_classification: str, evidence_score: float, conflicts: list[dict[str, Any]], rows: list[dict[str, Any]]) -> float:
    if conflicts:
        return 0.35
    if rows:
        return max(0.25, min(0.95, 0.45 + evidence_score * 0.5))
    return 0.75 if manifest_classification == "doe_factor" else 0.55


def evidence_actions(rows: list[dict[str, Any]]) -> list[str]:
    actions = []
    for row in rows:
        action = str(row.get("suggested_action") or row.get("suggested_role") or "").strip()
        if action and action not in actions:
            actions.append(action)
    return actions


def conflicts_for_entity(entity: str, conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [conflict for conflict in conflicts if entity in set(conflict.get("entities", []))]


def evidence_only_items(state: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {factor["factor_id"] for factor in state.get("factors", [])} | {response["response_id"] for response in state.get("responses", [])}
    items = []
    for row in rows:
        entity = str(row.get("factor_or_response") or "")
        if entity and entity not in known:
            items.append({"factor_or_response": entity, "evidence_id": row.get("evidence_id"), "claim": row.get("claim")})
    return items


# Common short tokens that are not informative as keyword matches.
_SAFETY_DECOY_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "into", "onto",
        "are", "was", "were", "have", "has", "had", "but", "not", "any",
        "all", "our", "its", "their", "than", "then", "about", "across",
        "under", "over", "between", "within", "without", "literature", "gap",
        "decoy", "constraint", "deliberate", "deliberately", "expected",
        "topic", "topics", "note", "notes", "rationale", "description",
    }
)


def derive_safety_decoy_keywords(constraint: dict[str, Any]) -> set[str]:
    """Build a generic keyword set for a safety_decoy constraint.

    Sources, in priority order:
      1. ``evidence_keywords`` (if explicitly authored on the constraint)
      2. ``expected_lit_topics`` (already a list of phrases)
      3. ``description`` text + ``constraint_id``
    Tokens shorter than 4 characters or in the stopword list are dropped.
    Multi-word phrases from ``expected_lit_topics`` are kept verbatim and
    also split into their component tokens so substring matching works
    against either form.
    """
    keywords: set[str] = set()

    explicit = constraint.get("evidence_keywords") or []
    if isinstance(explicit, str):
        explicit = [explicit]
    for term in explicit:
        if isinstance(term, str) and term.strip():
            keywords.add(term.strip().lower())

    topics = constraint.get("expected_lit_topics") or []
    if isinstance(topics, str):
        topics = [topics]
    for topic in topics:
        if not isinstance(topic, str):
            continue
        phrase = topic.strip().lower()
        if phrase:
            keywords.add(phrase)
            for token in phrase.replace("/", " ").replace("-", " ").split():
                token = token.strip(" ,.;:()[]{}")
                if len(token) >= 4 and token not in _SAFETY_DECOY_STOPWORDS:
                    keywords.add(token)

    if not keywords:
        fallback_text = " ".join(
            str(constraint.get(key) or "")
            for key in ("constraint_id", "description", "rationale")
        ).lower()
        for token in fallback_text.replace("/", " ").replace("-", " ").replace("_", " ").split():
            token = token.strip(" ,.;:()[]{}")
            if len(token) >= 4 and token not in _SAFETY_DECOY_STOPWORDS:
                keywords.add(token)

    return keywords


def is_constraint_related_evidence(row: dict[str, Any], keywords: Any) -> bool:
    """Return True when an evidence row text overlaps any of ``keywords``.

    ``keywords`` may be any iterable of strings; an empty iterable yields
    False. Matching is case-insensitive substring matching against the
    concatenation of the row's claim, caveat, factor_or_response, and
    entity_type fields.
    """
    keyword_list = [k for k in (keywords or []) if isinstance(k, str) and k]
    if not keyword_list:
        return False
    fields = [
        str(row.get("claim") or ""),
        str(row.get("caveat") or ""),
        str(row.get("factor_or_response") or ""),
        str(row.get("entity_type") or ""),
    ]
    combined_text = " ".join(fields).lower()
    return any(keyword.lower() in combined_text for keyword in keyword_list)


def validate_evidence_quality_for_safety_decoy(
    rows: list[dict[str, Any]], constraint_keywords: Any
) -> dict[str, Any]:
    """Validate that evidence rows touching a safety_decoy constraint are
    explicitly marked as gap/extrapolated/insufficient.

    Returns a summary dict with counts and per-row details for any
    unflagged rows so callers can surface the gap to swarm agents.
    """
    keyword_list = [k for k in (constraint_keywords or []) if isinstance(k, str) and k]
    related = [
        row
        for row in rows
        if row.get("validation_status") == "usable"
        and is_constraint_related_evidence(row, keyword_list)
    ]
    flagged: list[dict[str, Any]] = []
    unflagged: list[dict[str, Any]] = []
    for row in related:
        caveat_text = str(row.get("caveat") or "").lower()
        quality_label = str(row.get("quality_label") or "").lower()
        gap_markers = ("gap", "extrapolated", "insufficient", "limited", "sparse", "thin")
        has_gap_flag = any(
            marker in caveat_text or marker in quality_label for marker in gap_markers
        )
        claim_text = str(row.get("claim") or "")
        truncated_claim = claim_text[:50] + "..." if len(claim_text) > 50 else claim_text
        if has_gap_flag or quality_label in {"low", "excluded"}:
            flagged.append({"evidence_id": row.get("evidence_id"), "claim": truncated_claim})
        else:
            unflagged.append(
                {
                    "evidence_id": row.get("evidence_id"),
                    "claim": claim_text,
                    "caveat": row.get("caveat"),
                }
            )
    return {
        "total_related_rows": len(related),
        "properly_flagged_rows": len(flagged),
        "unflagged_rows": len(unflagged),
        "flagged_details": flagged,
        "unflagged_details": unflagged,
    }


def _safety_decoy_affected_factors(
    state: dict[str, Any],
    constraint: dict[str, Any],
    constraint_keywords: Any,
) -> set[str]:
    """Best-effort lookup of factor_ids relevant to a safety_decoy constraint.

    Order of evidence:
      1. an explicit ``affected_factors`` list on the constraint
      2. factors whose id or name contains any of ``constraint_keywords``
    """
    explicit = constraint.get("affected_factors") or []
    if isinstance(explicit, str):
        explicit = [explicit]
    factor_ids = {str(item) for item in explicit if isinstance(item, str) and item}
    if factor_ids:
        return factor_ids
    keyword_list = [k.lower() for k in (constraint_keywords or []) if isinstance(k, str) and k]
    if not keyword_list:
        return factor_ids
    for factor in state.get("factors", []):
        identifier = str(factor.get("factor_id") or "")
        name = str(factor.get("name") or "")
        haystack = f"{identifier} {name}".lower()
        if any(keyword in haystack for keyword in keyword_list):
            factor_ids.add(identifier)
    return factor_ids


def observability_coverage_score(state: dict[str, Any], measurements: list[dict[str, Any]], unobservable: list[str]) -> float:
    response_ids = {response["response_id"] for response in state.get("responses", [])}
    measured_ids = {item["measurement_id"] for item in measurements}
    response_coverage = len(response_ids & measured_ids) / max(1, len(response_ids))
    online = 1.0 if any(item.get("kind") == "online" for item in measurements) else 0.0
    offline = 1.0 if any(item.get("kind") == "offline" for item in measurements) else 0.0
    penalty = min(0.35, 0.06 * len(unobservable))
    return round(max(0.0, min(1.0, 0.25 + 0.45 * response_coverage + 0.15 * online + 0.15 * offline - penalty)), 4)


def _entity_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        entity = str(row.get("factor_or_response") or "")
        if entity:
            counts[entity] = counts.get(entity, 0) + 1
    return counts


def _role_suggestions(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        role = role_from_text(row.get("suggested_role") or row.get("suggested_action"))
        if role:
            counts[role] = counts.get(role, 0) + 1
    return counts


def _lane(lane_id: str, task: str, artifacts: list[str]) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "task": task,
        "expected_artifacts": artifacts,
        "acceptance": "Return structured evidence, confidence, caveats, and implications for factor selection or DOE readiness.",
    }


def challenge(
    index: int,
    category: str,
    severity: str,
    assumption: str,
    why: str,
    affected: list[str],
    action: str,
) -> dict[str, Any]:
    return {
        "challenge_id": f"AA-{index:02d}",
        "category": category,
        "severity": severity,
        "assumption_under_attack": assumption,
        "why_it_matters": why,
        "affected_items": [item for item in affected if item],
        "recommended_action": action,
    }


def measurement(measurement_id: str, kind: str, decision_value: str, caveat: str) -> dict[str, str]:
    return {
        "measurement_id": measurement_id,
        "kind": kind,
        "decision_value": decision_value,
        "caveat": caveat,
    }


def control(control_type: str, placement: str, count: int, purpose: str) -> dict[str, Any]:
    return {
        "control_type": control_type,
        "placement": placement,
        "count": count,
        "purpose": purpose,
    }
