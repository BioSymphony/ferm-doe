# Evidence Executor Contract And Search Plan

## Summary

Define the bounded research scope and row contract for evidence workers. This pack is optional and feeds Scientific Swarm evidence ingestion; it does not change the deterministic DOE core.

## Inputs

- `campaign_state.json`
- selected campaign manifest
- `templates/evidence-table.template.csv`
- `templates/evidence-executor-agent-brief.md`

## Expected Artifacts

- `evidence_executor_plan.md`
- `evidence_search_log.md`

## Acceptance Criteria

- Source classes, exclusion rules, and search terms are stated before research starts.
- `factor_or_response` ids from the campaign are listed so workers can map evidence rows correctly.
- Evidence row fields, confidence labels, contradiction groups, and review status rules are copied from the template.
- No live Linear, RunPod, GxP/GMP, private data, or provider mutation is introduced.

## Validation Commands

```bash
test -f templates/evidence-table.template.csv
test -f templates/evidence-executor-agent-brief.md
```

## Touched Areas

- `ferm-doe-dossier/swarm/evidence/`

## Dependencies

- None

<!-- symphony:schema
schema_version: 1
pack_id: evidence-executor-v0
pack_issue_id: EV-W0-01
touched_areas:
  - ferm-doe-dossier/swarm/evidence/
complexity: medium
-->

<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: evidence-executor-v0
pack_issue_id: EV-W0-01
wave: EV-W0
artifacts:
  - evidence_executor_plan.md
  - evidence_search_log.md
validation_summary: pending
remote_launch: not_requested
claim_level: evidence_plan_only
scientific_caveats:
  - pending
suggested_action: pending
-->
