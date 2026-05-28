# reference DOE Parity Contract

## Summary

Define the precise reference DOE surfaces BioSymphony Ferm DoE will expose first, without weakening fermentation-specific readiness gates.

## Inputs

- `docs/reference-doe-fast-path.md`
- `docs/superpower-roadmap-vs-reference-doe.md`
- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/tournament.py`

## Acceptance Criteria

- A machine-readable parity matrix exists for Custom Design, Screening/DSD, RSM, Mixture, Space-Filling, Diagnostics, Compare Designs, Augment Design, Bayesian Optimization, and Profiler/Prediction.
- Each parity row has current status, target status, required artifacts, and validation command.
- The mode `reference-doe-engine` remains opt-in or signal-selected, not forced into every campaign.
- Non-parity claims are explicit; no doc claims full reference DOE replacement before tests support it.

## Validation Commands

```bash
python3 -m py_compile $(find src skills/biosymphony-ferm-doe/scripts -name '*.py' | sort)
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `docs/`
- `src/biosymphony_ferm_doe/`
- `tests/`

## Dependencies

- None

## Risk Notes

Do not store secrets or private fermentation data. Do not overclaim reference DOE parity before executable diagnostics and tests exist.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: parity-contract
touched_areas:
  - docs/
  - src/biosymphony_ferm_doe/
  - tests/
complexity: medium
-->
