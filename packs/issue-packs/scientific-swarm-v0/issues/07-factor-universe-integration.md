# Factor Universe Integration

## Summary

Integrate evidence into a phase-aware factor universe for DOE, fixed controls, blocks, monitor-only variables, follow-up candidates, and exclusions.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `factor_universe.json`
- `factor_universe.md`

## Acceptance Criteria

- Every factor has classification, phase, rationale, evidence refs, and confidence.
- DOE factors are separated from controls, blocks, monitors, and deferred variables.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-factor-universe
test -f /tmp/biosymphony-swarm-factor-universe/factor_universe.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/factor-universe/`

## Dependencies

- SW-W1-01
- SW-W1-02
- SW-W1-04

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W2-01
touched_areas:
  - ferm-doe-dossier/swarm/factor-universe/
complexity: large
-->
