# Prior Data And Source Trust Lane

## Summary

Audit prior run ledgers, source labels, transformations, inclusion status, provenance quality, review status, and historical comparability.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `evidence_table_template.csv`
- `evidence_rows.normalized.csv`
- `evidence_ingestion_report.json`

## Acceptance Criteria

- Every prior-data claim distinguishes source-extracted, transformed, inferred, synthetic, and excluded data.
- Historical comparability caveats feed the factor universe and control-run strategy.
- Source trust, review status, quality score, and provenance gaps are explicit enough for downstream factor selection.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-prior-data
test -f /tmp/biosymphony-swarm-prior-data/evidence_table_template.csv
```

## Touched Areas

- `ferm-doe-dossier/swarm/evidence/`

## Dependencies

- SW-W0-01

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W1-02
touched_areas:
  - ferm-doe-dossier/swarm/evidence/
complexity: medium
-->
