# Assay And Product-Class Skeptic Lane

## Summary

Challenge whether the response definition, sample fraction, extraction, calibration, matrix effects, and turnaround can support DOE decisions.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `assumption_attack_report.json`

## Acceptance Criteria

- Product-class and assay risks are explicit.
- Weak or ambiguous response semantics become blockers or caveats, not hidden assumptions.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-assay
test -f /tmp/biosymphony-swarm-assay/assumption_attack_report.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/assay/`

## Dependencies

- SW-W0-01

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W1-03
touched_areas:
  - ferm-doe-dossier/swarm/assay/
complexity: medium
-->
