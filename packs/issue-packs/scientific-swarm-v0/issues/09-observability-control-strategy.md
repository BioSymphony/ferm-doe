# Observability And Control-Run Strategy

## Summary

Map measurements to decision value and recommend baseline, center, bridge, assay-control, phase-switch, and repeat controls, distinguishing assay controls from explicit fermentation control rows.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `observability_plan.json`
- `control_run_strategy.json`
- `selected_wave_1_design.csv`

## Acceptance Criteria

- Online and offline measurements have named decision value and caveats.
- Controls make first-batch interpretable across assay, process, and scale-transfer risk.
- Explicit fermentation control rows are budget-aware and appear in executable design packets when swarm policy enables augmentation.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-observability
test -f /tmp/biosymphony-swarm-observability/control_run_strategy.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/observability/`

## Dependencies

- SW-W1-03
- SW-W1-04
- SW-W1-05

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W2-03
touched_areas:
  - ferm-doe-dossier/swarm/observability/
complexity: medium
-->
