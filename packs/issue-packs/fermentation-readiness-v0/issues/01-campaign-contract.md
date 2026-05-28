## Summary

Compile the campaign contract from the selected goal pack, input pack, source catalog, and campaign manifest.

## Inputs

- `campaign_manifest` - campaign manifest path selected by the campaign instance
- `goal_pack` - selected goal pack path
- `input_pack` - selected input pack path

## Acceptance Criteria

- [ ] Objective, responses, constraints, and stop policy are explicit.
- [ ] Readiness verdict criteria are stated as GREEN, YELLOW, or RED.
- [ ] Required downstream artifacts are listed.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/xylanase-wxz1-2012/campaign_manifest.json
```

## Touched Areas

- `ferm-doe-dossier/` - campaign contract output

## Dependencies

Blocked by: none

## Risk Notes

- Do not store secrets, private process records, unpublished sequences, or confidential media formulations in Linear.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->

