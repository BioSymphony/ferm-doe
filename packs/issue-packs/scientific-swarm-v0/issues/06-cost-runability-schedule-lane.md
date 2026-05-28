# Cost, Runability, Sampling, And Schedule Lane

## Summary

Challenge operator burden, sampling cadence, assay throughput, reactor availability, run duration, and cost per liter.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `control_run_strategy.json`

## Acceptance Criteria

- Execution friction is visible before DOE selection.
- Controls and repeats protect interpretability without overloading the run.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-runability
test -f /tmp/biosymphony-swarm-runability/control_run_strategy.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/runability/`

## Dependencies

- SW-W0-01

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W1-05
touched_areas:
  - ferm-doe-dossier/swarm/runability/
complexity: medium
-->
