## Summary

Generate and adjudicate candidate experiment strategies from the audited factor space, assay readiness, and feasibility constraints.

## Inputs

- `factor_space_audit` - upstream dossier artifact
- `assay_readiness_report` - upstream dossier artifact
- `feasibility_report` - upstream dossier artifact

## Acceptance Criteria

- [ ] At least two candidate strategies are compared.
- [ ] Recommended strategy explains information gain, feasibility, and caveats.
- [ ] Decision includes GREEN, YELLOW, or RED run-readiness status.

## Validation Commands

```bash
test -d packs/goal-packs
```

## Touched Areas

- `ferm-doe-dossier/design_candidates/` - candidate design outputs

## Dependencies

Blocked by: factor-space-audit, assay-readiness, feasibility-audit

## Risk Notes

- Do not emit a physical run plan if assay or feasibility verdict is RED.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/design_candidates/
complexity: large
-->

