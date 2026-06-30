# Baseline And Parity Contract

## Summary

Make the current branch green, define the high-ROI DOE parity contract, and keep `doe-parity-v0` as historical context.

## Inputs

- `tests/` - current baseline suite
- `docs/high-roi-doe-parity-strategy.md` - parity posture
- `packs/issue-packs/doe-parity-v1/pack.yaml` - work graph

## Acceptance Criteria

- [ ] Full local unit suite passes or each remaining failure is documented as unrelated external fixture debt.
- [ ] `doe-parity-v1` pack validates as a bounded issue graph with downstream work in Backlog.
- [ ] Parity contract states that BioSymphony remains fermentation-first and adapter-honest.
- [ ] No issue requires paid remote compute.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/doe-parity-v1/issues/01-baseline-contract.md
```

## Touched Areas

- `tests/` - baseline gate
- `packs/issue-packs/doe-parity-v1/` - issue graph
- `docs/` - parity contract references

## Dependencies

Blocked by: none

## Risk Notes

- Do not claim full commercial DOE parity.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: baseline-contract
touched_areas:
  - tests/
  - packs/issue-packs/doe-parity-v1/
  - docs/
complexity: medium
-->
