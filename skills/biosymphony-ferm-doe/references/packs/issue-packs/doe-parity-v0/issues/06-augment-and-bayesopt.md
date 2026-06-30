# Augment Design And Bayesian Optimization

## Summary

Prepare the reference DOE Augment Design and Bayesian Optimization equivalent: locked prior runs, appended next runs, model refresh, candidate set generation, batch selection, and stop recommendations.

## Inputs

- `src/biosymphony_ferm_doe/ingest.py`
- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/tournament.py`
- `pyproject.toml`

## Acceptance Criteria

- `ingest_wave_results` can lock completed runs and request appended design candidates.
- Augmentation emits `augment_design.csv`, `locked_prior_runs.csv`, and `wave2_recommendation.json`.
- Bayesian/adaptive adapter interface exists and can run in stub/std fallback mode without BoFire/BoTorch installed.
- Optional BoFire/BoTorch path is documented and guarded behind optional dependencies.
- Stop recommendations include confirm, narrow, expand, pause, stop, and scale/downscale.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/ingest.py`
- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/tournament.py`
- `tests/`

## Dependencies

- `design-family-generators`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Bayesian optimization must not bypass assay readiness or campaign constraints. Label BO recommendations as model-based and campaign-gated.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: augment-and-bayesopt
touched_areas:
  - src/biosymphony_ferm_doe/ingest.py
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/tournament.py
  - tests/
complexity: large
-->
