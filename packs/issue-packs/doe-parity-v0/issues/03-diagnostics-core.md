# Diagnostics Core

## Summary

Raise design diagnostics from proxies to reference DOE reports: rank, estimability, alias/correlation, D/I/A/G metrics, FDS, prediction variance, power assumptions, and constraint violations.

## Inputs

- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/tournament.py`
- `docs/reference-doe-fast-path.md`

## Acceptance Criteria

- Every executable candidate design emits `design_diagnostics.json`.
- Diagnostics include rank, estimability, term count, alias/correlation matrix or summary, D/I/A/G metrics, FDS or approximation, prediction-variance summary, center/control count, replicate count, and constraint violations.
- Fermentation diagnostics are included: assay power caveat, sampling burden, oxygen/feed/pH/base/foam risk, cost/run, and mode-transfer risk.
- Tests include a design that is statistically acceptable but rejected for assay or feasibility reasons.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py --manifest examples/xylanase-wxz1-2012/campaign_manifest.json --out /tmp/doe-parity-diagnostics --run-budget 12
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py /tmp/doe-parity-diagnostics
```

## Touched Areas

- `src/biosymphony_ferm_doe/doe.py`
- `src/biosymphony_ferm_doe/tournament.py`
- `tests/`

## Dependencies

- `parity-contract`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Do not present proxy metrics as exact reference DOE-equivalent metrics. Exact, approximate, and heuristic metrics must be labeled.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: diagnostics-core
touched_areas:
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/tournament.py
  - tests/
complexity: large
-->
