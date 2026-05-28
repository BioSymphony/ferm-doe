# Diagnostics Verdicts

## Summary

Expand design diagnostics so invalid or weak experiments are named explicitly before any lab handoff.

## Inputs

- `src/biosymphony_ferm_doe/model_matrix.py` - rank, aliasing, variance, and condition diagnostics
- `src/biosymphony_ferm_doe/tournament.py` - acceptance and rejection reasons
- `src/biosymphony_ferm_doe/contract.py` - overclaim checks

## Acceptance Criteria

- [ ] Rank, non-estimable terms, inverse status, and condition number are emitted.
- [ ] Categorical confounding uses Cramer's V or another named contingency-table association metric.
- [ ] Constant and near-constant projected factors are reported.
- [ ] Center/lack-of-fit/control adequacy and blocking/randomization warnings are visible in exported diagnostics.
- [ ] Response-specific power/noise assumptions are kept as assumptions when no executed data exists.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_doe_parity_v1 -v
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_diagnostics_include_doe_comparable_fields -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/model_matrix.py` - diagnostics
- `src/biosymphony_ferm_doe/tournament.py` - named verdicts
- `src/biosymphony_ferm_doe/parity.py` - non-parity report
- `tests/` - diagnostic regressions

## Dependencies

Blocked by: intent-and-claims

## Risk Notes

- Diagnostics are design diagnostics, not fitted result models.
- Do not hide no-accepted-design, aliasing, constant-factor, or underpowered caveats.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: diagnostics-verdicts
touched_areas:
  - src/biosymphony_ferm_doe/model_matrix.py
  - src/biosymphony_ferm_doe/tournament.py
  - src/biosymphony_ferm_doe/parity.py
  - tests/
complexity: large
-->
