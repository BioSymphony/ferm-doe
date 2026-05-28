# Issue Pack Generation Runbook

End-to-end walkthrough of `ferm-doe engine generate-issue-pack`. For the pack chooser (which pack do I pick), see [`ISSUE_PACK_COOKBOOK.md`](ISSUE_PACK_COOKBOOK.md). This doc shows what the command produces, how each artifact is shaped, and how an orchestrator consumes it.

## What an issue pack is

An issue pack turns a campaign manifest into a bounded work graph that any orchestrator can drive. Each pack ships:

- A set of per-issue Markdown bodies with summary, inputs, acceptance criteria, validation commands, touched areas, and dependencies.
- A `dependency_graph.json` that records the issue-to-issue blocking and depends-on edges.
- A `linear-map.json` placeholder for tracker IDs. Dry-run output leaves it empty; the orchestrator fills it in after creating the tracker entries.

The packs themselves live at [`../packs/issue-packs/`](../packs/issue-packs/) as source templates. The CLI emits an instance of a pack scoped to a specific campaign manifest.

## Generate against the reference fixture

```bash
ferm-doe engine generate-issue-pack \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/issuepack-demo \
  --pack fermentation-readiness-v0
```

Output:

```text
{"issues": 7, "status": "OK"}
```

And under `/tmp/issuepack-demo/`:

```text
campaign-contract-campaign-contract.md
data-trust-audit-data-trust-audit.md
factor-space-audit-factor-space-audit.md
assay-readiness-assay-readiness.md
feasibility-audit-feasibility-audit.md
design-tournament-design-tournament.md
run-packet-run-packet.md
dependency_graph.json
linear-map.json
```

Each `.md` file is the issue body. The two JSON files are the orchestration metadata.

## Anatomy of an issue body

Issue bodies follow a stable template. Example header from `campaign-contract-campaign-contract.md`:

```markdown
## Summary

Compile the campaign contract from the selected goal pack, input pack, source catalog, and campaign manifest.

## Inputs

- `campaign_manifest` - campaign manifest path selected by the campaign instance
- `goal_pack` - selected goal pack path
- `input_pack` - selected input pack path

## Acceptance Criteria

- [ ] Objective, responses, constraints, and stop policy are explicit.
- [ ] Readiness verdict criteria are stated as GREEN, YELLOW, or RED.
- [ ] Required downstream artifacts are listed.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py ...
```

## Touched Areas

- `ferm-doe-dossier/` - campaign contract output

## Dependencies

Blocked by: none
```

This is the shape an orchestrator pastes into a Linear issue body, a GitHub Issue body, or a sub-agent's task prompt. The validation commands are runnable as-is.

## Anatomy of `dependency_graph.json`

```json
{
  "campaign_id": "doe-fast-path-custom-design-demo",
  "graph_kind": "ferm_doe_linear_dry_run",
  "issues": [
    {
      "issue_id": "campaign-contract",
      "title": "Campaign Contract",
      "pack_id": "fermentation-readiness-v0",
      "file": "campaign-contract-campaign-contract.md",
      "depends_on": [],
      "blocks": ["data-trust-audit", "factor-space-audit"],
      "wave": "wave0"
    },
    ...
  ]
}
```

`depends_on` and `blocks` are the two edges. `wave` lets the orchestrator schedule packs across waves of the campaign. An orchestrator that wants parallel sub-agent dispatch reads this file and fans work to whichever issues have no outstanding dependencies.

## Anatomy of `linear-map.json`

```json
{
  "schema_version": 1,
  "status": "dry_run_uncreated",
  "mappings": {}
}
```

Empty in dry-run. After the orchestrator creates tracker entries, it fills `mappings` with `{issue_id: tracker_id}` pairs and updates `status` to `created`. This lets later runs update existing entries instead of creating duplicates.

## Combining packs

Pass `--pack` multiple times to bundle packs:

```bash
ferm-doe engine generate-issue-pack \
  --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json \
  --out /tmp/issuepack-yeast \
  --pack fermentation-readiness-v0 \
  --pack scientific-swarm-v0 \
  --pack evidence-executor-v0
```

The dependency graph merges across packs: the swarm and evidence-executor issues block on the fermentation-readiness contract, and the orchestrator gets one coherent work graph instead of three disjoint ones.

## Orchestrator integration patterns

### Symphony

A Symphony worker reads `dependency_graph.json`, dispatches each ready issue to a sub-agent (typically a Codex worker with `reasoning: high`), and updates `linear-map.json` with the Linear tracker IDs. The worker's job description is the issue body's `Summary`. Acceptance criteria become the success contract.

### Claude Code + Linear

A Claude Code session creates Linear issues from each `.md` body, sets `Blocked by` relationships from `depends_on`, and tracks the campaign as a Linear project. The agent reads tracker-safe `--summary` fields from `ferm-doe validate` and pastes them as Linear comments. See [`../agents/linear.md`](../agents/linear.md).

### Generic orchestrator (no tracker)

A scripted orchestrator reads `dependency_graph.json` and walks the graph in topological order. Each issue's `Validation Commands` block is the test that the issue is done. No tracker required.

## When to regenerate

Regenerate the pack when:

- The manifest factor list changes (issues like `factor-space-audit` need re-validation).
- The pack source under `packs/issue-packs/` is updated (a new acceptance criterion lands, for example).
- A new wave begins (follow-up packs are scoped differently from first-batch).

The orchestrator should preserve `linear-map.json` across regenerations so existing tracker entries are updated rather than recreated. The CLI is idempotent given the same manifest and pack list.

## Safety boundary

Issue bodies surface manifest fields. Do not put private process records, customer data, unpublished sequences, API keys, or exact confidential recipes into manifests that you intend to dispatch through this pipeline. Use sanitized manifest fields, source metadata, or secure-store references for anything that must stay private. The public release scanner under `ferm-doe audit` flags suspicious content before a pack is generated.
