## Summary

Audit factor bounds, units, categories, and compatibility with the selected goal pack.

## Inputs

- `factor_space` - selected factor space path
- `goal_pack` - selected goal pack path

## Acceptance Criteria

- [ ] Every factor has unit, type, min, max, and default when applicable.
- [ ] Fixed factors are separated from design variables.
- [ ] Missing physical constraints are listed.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/xylanase-wxz1-2012/campaign_manifest.json
```

## Touched Areas

- `ferm-doe-dossier/` - factor-space audit output

## Dependencies

Blocked by: campaign-contract

## Risk Notes

- Do not widen factor bounds beyond source or user-provided safety limits without review.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->

