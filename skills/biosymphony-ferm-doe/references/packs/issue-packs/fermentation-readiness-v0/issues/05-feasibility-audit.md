## Summary

Assess reagent, vessel, time, sampling, and analytics feasibility before design selection.

## Inputs

- `reagent_inventory` - selected reagent inventory path
- `equipment_capacity` - selected equipment capacity path, if present
- `factor_space` - selected factor space path

## Acceptance Criteria

- [ ] Required reagents and approximate amounts are listed.
- [ ] Equipment and sampling constraints are explicit.
- [ ] Any impossible factor combinations are documented.

## Validation Commands

```bash
test -f examples/xylanase-wxz1-2012/inputs/reagent_inventory.csv
```

## Touched Areas

- `ferm-doe-dossier/` - feasibility report output

## Dependencies

Blocked by: data-trust-audit

## Risk Notes

- This issue must not authorize autonomous purchasing or physical setup.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->
