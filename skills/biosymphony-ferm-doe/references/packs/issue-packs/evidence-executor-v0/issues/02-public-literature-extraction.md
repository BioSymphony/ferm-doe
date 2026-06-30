# Public Literature Evidence Extraction

## Summary

Extract bounded evidence rows from public literature sources such as PubMed, publisher landing pages, bioRxiv, and Google Scholar/manual citation lookup.

## Inputs

- `campaign_state.json`
- `templates/evidence-table.template.csv`
- `templates/evidence-executor-agent-brief.md`
- approved search plan from `EV-W0-01`

## Expected Artifacts

- `evidence_table.csv`
- `evidence_source_ledger.csv`
- `evidence_search_log.md`

## Acceptance Criteria

- Every row has one claim, a stable `source_ref`, source type, source title, source date when available, confidence, source trust, review status, and caveat when needed.
- Claims are mapped to known factor or response ids when possible.
- Public/reference findings are not represented as private target-process proof.
- Contradictions are grouped with `contradiction_group` instead of resolved silently.
- No article text, private records, secrets, or credentials are copied into outputs.

## Validation Commands

```bash
test -f evidence_table.csv
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-evidence-literature --evidence-table evidence_table.csv
test -f /tmp/biosymphony-evidence-literature/evidence_ingestion_report.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/evidence/literature/`

## Dependencies

- EV-W0-01

<!-- symphony:schema
schema_version: 1
pack_id: evidence-executor-v0
pack_issue_id: EV-W1-01
touched_areas:
  - ferm-doe-dossier/swarm/evidence/literature/
complexity: large
-->

<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: evidence-executor-v0
pack_issue_id: EV-W1-01
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
