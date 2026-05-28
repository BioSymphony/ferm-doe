# Intent And Claim Gating

## Summary

Add intent-aware DOE semantics so screening, scouting, RSM, mixture, custom, augmentation, confirmatory, and imported designs are accepted under different statistical claim rules.

## Inputs

- `src/biosymphony_ferm_doe/doe.py` - candidate metadata
- `src/biosymphony_ferm_doe/tournament.py` - acceptance gates
- `src/biosymphony_ferm_doe/contract.py` - claim audit

## Acceptance Criteria

- [ ] Campaigns can declare `design_policy.design_intent`.
- [ ] Every candidate emits method family, exactness, claim level, backend availability, and backend used.
- [ ] Rank-deficient RSM or confirmatory designs are rejected or downgraded.
- [ ] Stdlib-like designs cannot satisfy exact/adapter-required intents.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_doe_parity_v1 -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/doe.py` - design metadata
- `src/biosymphony_ferm_doe/tournament.py` - intent-aware gates
- `src/biosymphony_ferm_doe/contract.py` - claim boundaries
- `tests/` - parity regressions

## Dependencies

Blocked by: baseline-contract

## Risk Notes

- Scouting remains valid even when rank deficient, but fitted-model claims must not pass.
- Backend availability is not backend execution.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: intent-and-claims
touched_areas:
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/tournament.py
  - src/biosymphony_ferm_doe/contract.py
  - tests/
complexity: large
-->
