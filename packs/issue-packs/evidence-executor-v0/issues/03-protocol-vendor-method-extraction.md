# Protocol Vendor And Method Evidence Extraction

## Summary

Extract evidence rows from operator-approved protocols, vendor methods, assay methods, equipment manuals, and sanitized prior-run summaries.

## Inputs

- `campaign_state.json`
- `templates/evidence-table.template.csv`
- `templates/evidence-executor-agent-brief.md`
- approved source list from `EV-W0-01`

## Expected Artifacts

- `evidence_table.csv`
- `evidence_source_ledger.csv`
- `evidence_search_log.md`

## Acceptance Criteria

- Rows capture assay, equipment, reagent, sampling, control, pH, oxygen, feed, foam, and runability claims when decision-relevant.
- Vendor/protocol claims are labeled with appropriate `source_type`, `license`, `source_trust`, and caveats.
- Local prior-run summaries remain sanitized and do not include confidential strain, customer, or recipe details.
- Evidence that affects factor selection uses an allowed `suggested_role`.

## Validation Commands

```bash
test -f evidence_table.csv
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-evidence-protocols --evidence-table evidence_table.csv
test -f /tmp/biosymphony-evidence-protocols/evidence_ingestion_report.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/evidence/protocols/`

## Dependencies

- EV-W0-01

<!-- symphony:schema
schema_version: 1
pack_id: evidence-executor-v0
pack_issue_id: EV-W1-02
touched_areas:
  - ferm-doe-dossier/swarm/evidence/protocols/
complexity: medium
-->

<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: evidence-executor-v0
pack_issue_id: EV-W1-02
wave: EV-W1
artifacts:
  - evidence_table.csv
  - evidence_source_ledger.csv
  - evidence_search_log.md
validation_summary: pending
remote_launch: not_requested
claim_level: evidence_rows_for_review
scientific_caveats:
  - pending
suggested_action: pending
-->
