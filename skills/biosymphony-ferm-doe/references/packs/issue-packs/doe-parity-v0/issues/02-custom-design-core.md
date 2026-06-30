# Custom Design Core

## Summary

Implement a reference DOE custom design core: factor model, model terms, candidate set, constraints, run budget, blocking, hard-to-change factors, reproducible seeds, and optimality selection.

## Inputs

- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/schemas.py`
- `tests/test_engine.py`

## Acceptance Criteria

- Campaign state can express continuous, discrete, categorical, ordinal, mixture, blocking, hard-to-change, and fixed-control factors.
- Design generation accepts model terms: main effects, selected interactions, quadratic terms, mixture terms, and if-possible terms.
- Linear constraints, forbidden combinations, fixed candidate inclusion, and run exclusions are represented and validated.
- The engine emits `candidate_set.csv`, `model_matrix.csv`, and `custom_design.scorecard.json`.
- Repeated runs with the same seed are deterministic.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 skills/biosymphony-ferm-doe/scripts/propose_wave1_design.py --manifest examples/xylanase-wxz1-2012/campaign_manifest.json --out /tmp/doe-parity-custom-design --run-budget 12
```

## Touched Areas

- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/schemas.py`
- `tests/`

## Dependencies

- `parity-contract`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Do not treat fermentation feasibility as a secondary concern; custom design candidates must still pass readiness and feasibility scoring.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: custom-design-core
touched_areas:
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/schemas.py
  - tests/
complexity: large
-->
