# Execution Planner

## Summary

Add post-selection execution planning that turns a statistical design into a blocked/randomized lab run sheet without changing model identity.

## Inputs

- `src/biosymphony_ferm_doe/contract.py` - run sheet and contract proof
- `src/biosymphony_ferm_doe/dossier.py` - dossier outputs
- `src/biosymphony_ferm_doe/swarm.py` - control strategy hints

## Acceptance Criteria

- [ ] Dossier includes `execution_plan.json`.
- [ ] `run-sheet.tsv` separates `design_run_id`, execution order, block, randomization group, and vessel/slot.
- [ ] Full, blocked, split-plot-like, and manual-locked order policies are supported.
- [ ] Contract self-check preserves joins across selected design, run sheet, design matrix, and results ledger.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_execution_plan -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/execution_plan.py` - planner
- `src/biosymphony_ferm_doe/contract.py` - proof artifacts
- `src/biosymphony_ferm_doe/dossier.py` - output manifest
- `tests/` - execution packet coverage

## Dependencies

Blocked by: baseline-contract

## Risk Notes

- Do not claim full randomization when block or hard-to-change factors constrain order.
- Manual locked order must retain rationale fields.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: execution-planner
touched_areas:
  - src/biosymphony_ferm_doe/execution_plan.py
  - src/biosymphony_ferm_doe/contract.py
  - src/biosymphony_ferm_doe/dossier.py
  - tests/
complexity: large
-->
