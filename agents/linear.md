---
name: ferm-doe-linear
description: Use when connecting BioSymphony Ferm DoE campaign manifests, readiness summaries, stop rules, and follow-up waves to Linear issues.
---

# Linear-aware agent integration

Pattern for using `biosymphony-ferm-doe` with a long-running agent that has Linear access (Claude Code + Linear MCP, OpenAI Agents SDK + Linear, Codex CLI + Linear, custom orchestrator).

The skill itself does not depend on Linear. Linear access lives in the agent that calls the skill. This doc describes the conventions that make the two work well together.

## Mapping

| Linear concept | Repo concept |
|---|---|
| Linear project | Family of related campaigns, e.g. "Q3 Pichia scale-down" |
| Linear issue | One campaign: `examples/<campaign_id>/` or your private equivalent |
| Linear sub-issue | One wave: entry in `waves[]` |
| Linear comment | Tracker-safe readiness summary, failed check IDs, or hand-off note |
| Linear status | Mirrors `readiness.overall` (Triage = RED, In Progress = YELLOW, Done = GREEN) |
| Linear label | Mirrors `profiles[]` and the worst-axis from `--summary` |
| Linear assignee | Maps to `risk_register[].owner_role` and `stop_rules[].owner_role` |

## Loop with Linear

1. **Intake from Linear**
   - Read the issue title and description.
   - Derive `campaign_id` from the Linear issue identifier (e.g. `BIO-142` → `campaign_id: bio-142-pichia-downscale`).
   - Pick `profiles[]` from the issue body or labels.
   - Draft `campaign_manifest.json`. Anything inferred goes in `assumptions[]` with `status: inferred` so the issue author can push back.

2. **Readiness gate posted as a comment**
   - Run `ferm-doe validate <campaign_dir> --summary`.
   - Post only the tracker-safe JSON fields to the Linear issue as a comment, with a one-line human summary above it.
   - Set the Linear status: RED → Triage, YELLOW → In Progress, GREEN → Ready for Review.

3. **Stop rules trigger Linear escalation**
   - When a `stop_rules[]` condition fires during execution, the agent:
     - moves the Linear issue to a "Blocked" status,
     - tags `owner_role` as a Linear label or assignee,
     - posts a comment with `rule_id`, `condition`, and the recommended `action`.
   - Do not auto-resume. A human resolves the stop, the agent re-validates, then continues.

4. **follow-up lands as a sub-issue**
   - When `decision_rules[]` fires `advance_to_next_wave`, create a Linear sub-issue named `follow-up: <campaign_id>`.
   - Append the new wave to `waves[]` in the manifest. Status starts `planned`.
   - Link the sub-issue back to the parent.

5. **Hand-off via `expected/AGENTS.md`**
   - Always update `expected/AGENTS.md` before closing the Linear issue or pausing.
   - Include the resume order, unresolved risks, and the worst-axis from the last `validate --summary`.

## Conventions

- **Synthetic/public data only in public repos.** If the campaign uses private process data, store the manifest in a private repository or workspace; keep this skill's public examples synthetic.
- **One campaign per Linear issue.** Sub-issues map to waves, not to factors or arms.
- **Comments include tracker-safe `--summary` fields**, not just prose. Future agents reading the issue history rely on machine-readable state.
- **Tracker-safe means status, worst axis, failed check IDs, warning/error counts, artifact references, manifest version, and next requested action.** Do not paste full manifests, result rows, assay details, biosafety answers, cloud URLs, provider logs, credentials, or customer/process records into tracker comments unless a private workspace retention/export policy explicitly allows it.
- **Do not paste raw `--out` JSON for the full check list into a tracker issue.** The full check list grows with the manifest and can contain context that belongs in the private workspace.
- **Stop rules cite the `rule_id` and the manifest version** (commit SHA or timestamp) so Linear escalations are reproducible.
- **Biosafety-relevant context is recorded in `assumptions[]`, not in Linear comments.** When the agent's biosafety heuristic fires (see [`BIOSAFETY.md`](../BIOSAFETY.md)), the operator's answer goes into the manifest. Linear sees the verdict and worst axis like any other readiness state.

## Worked example (sketch, not runnable)

```
Linear issue: BIO-142 "Downscale qualification: 50 L → 2 L for strain X"
        │
        ├─ Agent intake
        │     campaign_id: bio-142-pichia-downscale
        │     profiles: ["scale_down_qualification"]
        │     scale_context.from_scale.working_volume_l: 50
        │     scale_context.to_scale.working_volume_l: 2
        │
        ├─ Comment 1: validate --summary  →  status YELLOW, worst_axis "scale_context"
        │     (because bench kLa-vs-RPM curve is unqualified)
        │
        ├─ Linear status → In Progress
        │     Linear label → "scale_down_qualification"
        │
        ├─ Comment 2: validator output after kLa qualification ingest
        │     status YELLOW, warning_count 0
        │
        ├─ Sub-issue created: "first-batch execution: bio-142-pichia-downscale"
        │     waves[0]: { wave_id: "w1", status: "planned", design_table_path: ... }
        │
        └─ ... agent updates manifest as physical-execution results come back
```

## Out of scope for this skill

- Linear API calls. The agent makes them; the skill does not.
- Linear authentication. The agent holds the credentials.
- Linear project / team taxonomy. Each lab keeps its own; the skill is taxonomy-agnostic.

## Companion configs

- [`agents/claude.md`](claude.md): Claude Code patterns
- [`agents/openai.yaml`](openai.yaml): OpenAI Agents SDK / Codex CLI
- [`agents/generic.md`](generic.md): runtime-agnostic baseline
