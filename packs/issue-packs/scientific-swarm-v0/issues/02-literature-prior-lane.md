# Literature And Evidence Prior Lane

## Summary

Extract factor ranges, toxicity/inhibition thresholds, media/feed precedents, assay methods, and process failure modes from approved sources.

Use `evidence-executor-v0` when this lane needs active PubMed, bioRxiv, Scholar/manual-citation, vendor, protocol, or sanitized prior-run research. This Scientific Swarm lane consumes the resulting evidence rows; it should not turn prose notes into DOE decisions without the structured table.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `evidence_table_template.csv`
- `evidence_rows.normalized.csv`
- `evidence_ingestion_report.json`

## Acceptance Criteria

- Claims are source-linked, confidence-labeled, and tied to a factor, response, or process assumption.
- Contradictions and weak evidence are flagged for assumption attack.
- Evidence rows include source metadata, review status, quality score, and provenance gaps before they influence DOE.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-literature
test -f /tmp/biosymphony-swarm-literature/evidence_table_template.csv
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
pack_issue_id: SW-W1-01
touched_areas:
  - ferm-doe-dossier/swarm/evidence/
complexity: medium
-->
