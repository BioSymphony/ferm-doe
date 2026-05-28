# Agent Harnesses

How to plug `biosymphony-ferm-doe` into the runtimes long-running agents actually use. The skill is runtime-agnostic; this doc is the bridge.

## Common ground

- **The campaign manifest is durable state.** `<campaign_dir>/campaign_manifest.json` is the single source of truth. Updating it across turns is the agent's job.
- **The CLI is stdlib-only at runtime.** No deps to manage, no virtualenv to ship; just `python3 -m biosymphony_ferm_doe.cli`.
- **JSON output is machine-readable.** `--summary` returns ~10 fields; full output returns the per-check list. Pipe it, parse it, post it.
- **Hand-off lives in `expected/AGENTS.md`.** Every session ends by updating it.

## State persistence model

| Layer | Where it lives | Who owns it |
|---|---|---|
| Manifest (`campaign_manifest.json`) | repo / workspace | the skill (you write to it; the validator reads it) |
| Inputs (`inputs/*.csv`) | repo / workspace | the agent / scientist |
| Expected artifacts (`expected/*`) | repo / workspace | the agent |
| Hand-off (`expected/AGENTS.md`) | repo / workspace | the agent that's pausing |
| Validator output | stdout / `--out FILE` | ephemeral |
| Issue tracker comments / labels | external system | the agent's harness |

Resume = read the manifest, read `expected/AGENTS.md`, run `validate --summary`, continue.

## Claude Code

`agents/claude.md` is the starting reference. Patterns specific to Claude Code:

- Use the Bash tool for `ferm-doe list-campaigns`, `ferm-doe inspect-campaign`, `ferm-doe agent-brief`, `ferm-doe validate`, and `audit`. The output is small and parseable.
- Use the Read tool for the manifest, then the Edit tool for incremental updates. Avoid Write; it overwrites the whole file and risks losing state another agent might be holding.
- Use TaskCreate to plan profile-by-profile work. Mark tasks completed as you fix warnings.

## OpenAI Agents SDK / Codex CLI

`agents/openai.yaml` is the starting reference. Patterns:

- Wrap `ferm-doe list-campaigns`, `ferm-doe inspect-campaign`, `ferm-doe agent-brief`, and `ferm-doe validate --summary` as JSON-schema-typed tools; parse them directly into the agent's reasoning loop.
- For Codex CLI: pass the campaign directory as an argument; let Codex own the read/write of the manifest file.

## Long-horizon orchestrators (generic)

`agents/generic.md` covers the baseline. The pattern that always works:

1. Persist `<campaign_dir>` somewhere durable (repo, S3, local filesystem with backup).
2. The orchestrator's worker calls `ferm-doe list-campaigns`, reads the selected manifest, calls `ferm-doe inspect-campaign`, `ferm-doe agent-brief`, and `ferm-doe validate --summary`, then decides the next action.
3. The worker writes the updated manifest back atomically (write to `<path>.tmp`, then rename).
4. The orchestrator re-dispatches when new evidence arrives (lab-execution results, instrument calibration logs, additional literature).

## Tracker-driven runners

For trackers like Linear, Jira, or GitHub Issues:

- Tracker issue ↔ campaign
- Tracker sub-issue ↔ wave
- Tracker comment ↔ readiness summary
- Tracker label ↔ profile + worst_axis
- Tracker status ↔ readiness verdict (RED / YELLOW / GREEN)

## What the skill does *not* do

- Schedule, dispatch, or orchestrate workers. That work belongs to the harness.
- Authenticate to external systems. The harness brings credentials.
- Track time, cost, or budget. Record those as `constraints[]` if needed; the validator will not model them.
- Execute physical lab experiments. BioSymphony Ferm DoE is a pre-experiment planning system, not an execution system; the lab team owns physical execution and the batch record built on top of the DOE plan.

## Anti-patterns

- **Two agents updating the same manifest in parallel.** Use a lock or a worktree per agent. The validator is fast enough that serial updates are not a bottleneck.
- **Agent writes a "summary" to the manifest's free-text fields instead of `assumptions[]`.** Use the structured slot. Free-text drifts.
- **Agent commits a campaign manifest with private process data to a public repo.** Use a private workspace; keep the public examples synthetic.
- **Agent ignores `stop_rules[]`.** They exist so a paused campaign cannot be silently resumed by a different agent.

## Testing your harness against the skill

```bash
# 1. fresh checkout
git clone https://github.com/BioSymphony/ferm-doe.git
cd ferm-doe

# 2. validate your harness can call the CLI and parse the output
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary

# 3. confirm the diagnostic warnings round-trip through your harness's tool plumbing
# 4. wire stop-rule firing into your harness's escalation path
```

If your harness can't surface the eight warnings from the diagnostic demo to a human, fix the harness before pointing it at a real campaign.
