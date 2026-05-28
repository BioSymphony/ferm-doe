# Evidence Table Normalization And Handoff

## Summary

Merge research-worker evidence rows into a single local table, run Scientific Swarm ingestion, and hand off normalized evidence artifacts to the DOE tournament.

## Inputs

- literature `evidence_table.csv`
- protocol/vendor `evidence_table.csv`
- `campaign_state.json`
- selected campaign manifest

## Expected Artifacts

- `evidence_table.csv`
- `evidence_rows.normalized.csv`
- `evidence_ingestion_report.json`
- `evidence_executor_report.md`

## Acceptance Criteria

- Duplicate or conflicting rows are preserved with provenance instead of collapsed without explanation.
- `evidence_ingestion_report.json` records malformed rows, unknown entities, provenance gaps, conflicts, and quality summary.
- Evidence rows that should not influence DOE are marked rejected, excluded, low confidence, or unmapped.
- The handoff path for `swarm_policy.evidence_tables` is recorded.

## Validation Commands

```bash
test -f evidence_table.csv
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-evidence-handoff --evidence-table evidence_table.csv
test -f /tmp/biosymphony-evidence-handoff/evidence_rows.normalized.csv
test -f /tmp/biosymphony-evidence-handoff/evidence_ingestion_report.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/evidence/`

## Dependencies

- EV-W1-01
- EV-W1-02

<!-- symphony:schema
schema_version: 1
pack_id: evidence-executor-v0
pack_issue_id: EV-W2-01
touched_areas:
  - ferm-doe-dossier/swarm/evidence/
complexity: medium
-->

<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: evidence-executor-v0
pack_issue_id: EV-W2-01
wave: EV-W2
artifacts:
  - evidence_table.csv
  - evidence_rows.normalized.csv
  - evidence_ingestion_report.json
  - evidence_executor_report.md
validation_summary: pending
remote_launch: not_requested
claim_level: evidence_rows_for_review
scientific_caveats:
  - pending
suggested_action: pending
-->
