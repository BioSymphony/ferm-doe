"""Agent kickoff brief for long-horizon Ferm DoE orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .campaign_inspector import inspect_campaign


REPO_OWNS = [
    "campaign manifest and task contracts",
    "deterministic validation and readiness checks",
    "planning artifacts, dossiers, handoff packets, and follow-up rules",
    "claim boundaries for planning, assay readiness, scale transfer, cost realism, and remote success",
    "machine-readable resume and closeout surfaces",
]

ORCHESTRATOR_OWNS = [
    "turning a user goal into bounded work",
    "choosing local, tracker-backed, or approved cloud execution lanes",
    "sequencing and monitoring workers",
    "asking only high-leverage operator questions when inputs are incomplete",
    "installing optional extras in isolated environments",
    "fetching, validating, hashing, and cleaning up remote artifacts when paid resources are used",
]

FAIL_CLOSED_RULES = [
    "Do not call a YELLOW or RED planning package lab-ready.",
    "Do not launch paid remote resources without explicit operator approval, budget, timeout, cleanup, and artifact validation.",
    "Do not paste private process data, secrets, provider logs, or full manifests into public trackers.",
    "If an expected artifact or acceptance command is unclear, stop and create a bounded task request before executing.",
    "Treat provider RUNNING or worker heartbeat as progress only; success requires fetched artifacts and validation.",
]

TRACKER_SAFE_FIELDS = [
    "campaign_id",
    "readiness.overall",
    "failed_check_ids",
    "warning_count",
    "error_count",
    "worst_axis",
    "artifact paths",
    "next requested action",
]


def build_agent_brief(
    path: Path,
    *,
    goal: str = "",
    command_style: str = "public",
    compute_policy: str = "local-first",
    tracker: str = "generic",
) -> dict[str, Any]:
    """Build a compact kickoff artifact for a capable external orchestrator."""

    command_style = "public"
    inspection = inspect_campaign(path, command_style=command_style)
    workstreams = _workstreams(inspection, command_style=command_style, compute_policy=compute_policy, tracker=tracker)
    return {
        "schema_version": 1,
        "brief_kind": "biosymphony_ferm_doe_agent_brief",
        "goal": goal,
        "campaign": {
            "campaign_id": inspection.get("campaign_id"),
            "path": inspection.get("campaign_dir"),
            "manifest_path": inspection.get("manifest_path"),
            "claim_level": inspection.get("claim_level"),
            "profiles": inspection.get("profiles", []),
            "readiness": inspection.get("readiness", {}),
            "capabilities": inspection.get("capabilities", {}),
            "present_artifacts": inspection.get("present_artifacts", []),
        },
        "orchestrator_boundary": {
            "repo_owns": REPO_OWNS,
            "orchestrator_owns": ORCHESTRATOR_OWNS,
            "not_missing_when": [
                "a capable agent can identify the next artifact",
                "the acceptance command is explicit",
                "the claim boundary is machine-readable",
                "local and cloud lanes preserve the same artifact contract",
            ],
        },
        "starter_commands": _starter_commands(inspection, command_style=command_style),
        "workstreams": workstreams,
        "tracker_contract": {
            "mode": tracker,
            "safe_fields": TRACKER_SAFE_FIELDS,
            "policy": "Post summaries and artifact references, not raw private manifests, result rows, secrets, or provider logs.",
        },
        "compute_policy": _compute_policy(compute_policy),
        "fail_closed_rules": FAIL_CLOSED_RULES,
        "closeout_expectations": [
            "list artifacts created or deliberately skipped",
            "record validation commands and status",
            "record assumptions, unresolved blockers, and degraded routes",
            "record next action for the same or future agent",
        ],
        "non_claim": "This brief is an orchestration aid for capable agents; it does not validate readiness, launch workers, or approve physical execution.",
    }


def render_agent_brief_markdown(brief: dict[str, Any]) -> str:
    campaign = brief["campaign"]
    lines = [
        f"# Agent Brief: {campaign.get('campaign_id') or 'campaign'}",
        "",
        f"Goal: {brief.get('goal') or 'not specified'}",
        f"Campaign path: `{campaign.get('path')}`",
        f"Readiness: `{campaign.get('readiness', {}).get('overall') or 'unknown'}`",
        "",
        "## Boundary",
        "",
        "BioSymphony owns contracts, deterministic checks, artifacts, and claim boundaries. The orchestrator owns task sequencing, worker routing, optional tracker updates, and local or cloud execution choices.",
        "",
        "## First Commands",
        "",
        "```bash",
        *[command["command"] for command in brief.get("starter_commands", [])],
        "```",
        "",
        "## Workstreams",
        "",
    ]
    for item in brief.get("workstreams", []):
        lines.extend(
            [
                f"### {item['id']}: {item['title']}",
                "",
                f"Lane: `{item['lane']}`",
                f"When: {item['when']}",
                f"Artifacts: {', '.join(f'`{artifact}`' for artifact in item['artifacts'])}",
                f"Acceptance: {', '.join(f'`{check}`' for check in item['acceptance_checks'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Fail Closed",
            "",
            *[f"- {rule}" for rule in brief.get("fail_closed_rules", [])],
            "",
        ]
    )
    return "\n".join(lines)


def _starter_commands(inspection: dict[str, Any], *, command_style: str) -> list[dict[str, str]]:
    campaign = inspection["campaign_dir"]
    commands = [
        {"id": "catalog", "command": f"ferm-doe list-campaigns {Path(campaign).parent.as_posix()}", "reason": "see nearby campaigns and reusable fixtures"},
        {"id": "inspect", "command": f"ferm-doe inspect-campaign {campaign}", "reason": "summarize declared campaign shape"},
        {"id": "validate", "command": f"ferm-doe validate {campaign} --summary", "reason": "get tracker-safe readiness fields"},
    ]
    commands.extend(inspection.get("recommended_next_commands", [])[:3])
    return _dedupe_commands(commands)


def _dedupe_commands(commands: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows = []
    for command in commands:
        key = command["command"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(command)
    return rows


def _workstreams(inspection: dict[str, Any], *, command_style: str, compute_policy: str, tracker: str) -> list[dict[str, Any]]:
    capabilities = inspection.get("capabilities", {})
    campaign = inspection["campaign_dir"]
    out_root = f".runtime/{Path(campaign).name}"
    streams = [
        _stream(
            "intake",
            "Confirm goal, claim level, and stop policy",
            "always first unless the manifest is already current",
            "local-agent",
            ["operator_intake.md", "campaign_manifest.json", "missing_operator_items.json"],
            [f"ferm-doe inspect-campaign {campaign}", f"ferm-doe validate {campaign} --summary"],
        ),
        _stream(
            "readiness",
            "Turn validator output into the first worklist",
            "after intake and after any material manifest edit",
            "local-agent",
            ["expected/readiness_summary.json", "readiness.json"],
            [f"ferm-doe validate {campaign} --summary"],
        ),
    ]
    if not capabilities.get("has_evidence_table"):
        streams.append(
            _stream(
                "evidence",
                "Collect public, sanitized, or operator-provided evidence rows",
                "when factors, ranges, assumptions, or assay details need support",
                _tracker_lane(tracker),
                ["inputs/evidence_table.csv", "_swarm/CITATIONS.json", "_swarm/NOTES.md"],
                ["ferm-doe validate-task-request templates/task_request.template.json"],
            )
        )
    if capabilities.get("can_generate_wave1_design") and not capabilities.get("has_selected_wave1_design"):
        streams.append(
            _stream(
                "wave1-design",
                "Generate or adjudicate the first planned design",
                "after structural validation blockers are resolved",
                "local-agent",
                ["selected_wave_1_design.csv", "design_metadata.json", "design_adjudication.json"],
                [f"ferm-doe generate-design {campaign} --out {out_root}/wave1_design.csv --metadata-out {out_root}/wave1_design.metadata.json"],
            )
        )
    if capabilities.get("can_plan_wave2"):
        streams.append(
            _stream(
                "adaptive-wave2",
                "Plan the next experiment round from joined result rows",
                "only after result rows are available and QC exclusions are explicit",
                "local-agent",
                ["adaptive_wave2_plan.json", "assay_power_results.json", "augment_design.csv"],
                [command["command"] for command in inspection.get("recommended_next_commands", []) if command.get("id") == "plan-wave2"] or [f"ferm-doe plan-wave2 {campaign} --results {campaign}/inputs/wave1_results.csv --out-dir {out_root}/wave2"],
            )
        )
    if not capabilities.get("has_run_packet"):
        streams.append(
            _stream(
                "handoff",
                "Compile the packet or dossier that a future agent can resume",
                "after readiness, design, and claim-boundary artifacts exist",
                "local-agent",
                ["expected/run_packet.md", "ferm-doe-dossier/", "expected/AGENTS.md"],
                [f"ferm-doe finalize {campaign} --out {out_root}/run_packet.md --json-out {out_root}/run_packet.json"],
            )
        )
    if compute_policy in {"cloud-prep", "cloud-allowed"}:
        streams.append(
            _stream(
                "remote-execution-prep",
                "Prepare a bounded remote worker handoff without making the provider the campaign brain",
                "only for heavier adapter tests, reproducibility smoke, or artifact builds",
                "orchestrator-controlled",
                ["provider_handoff.json", "stage_contract.json", "artifact_hashes.json", "cleanup_evidence.json"],
                ["validate stage contract", "fetch artifacts", "verify hashes", "verify cleanup"],
            )
        )
    return streams


def _stream(id_: str, title: str, when: str, lane: str, artifacts: list[str], acceptance_checks: list[str]) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "when": when,
        "lane": lane,
        "artifacts": artifacts,
        "acceptance_checks": acceptance_checks,
    }


def _tracker_lane(tracker: str) -> str:
    if tracker == "linear":
        return "symphony-linear-worker"
    if tracker == "none":
        return "local-agent"
    return "tracker-capable-agent"


def _compute_policy(policy: str) -> dict[str, Any]:
    descriptions = {
        "local-only": "Use local execution only. Cloud/provider work is out of scope for this brief.",
        "local-first": "Default to local stdlib and optional local extras; prepare cloud work only when it has clear ROI.",
        "cloud-prep": "Allow provider handoff artifacts, but do not mutate paid resources from this command.",
        "cloud-allowed": "Cloud work may be routed by the orchestrator after explicit approval, budget, timeout, validation, and cleanup policy.",
    }
    return {
        "mode": policy,
        "description": descriptions.get(policy, descriptions["local-first"]),
        "paid_mutation_policy": "never from this brief; a trusted orchestrator must own approval, launch, artifact verification, and cleanup",
    }
