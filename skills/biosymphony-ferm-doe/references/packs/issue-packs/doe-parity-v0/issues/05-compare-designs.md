# Compare Designs

## Summary

Build a reference DOE-like compare-design report that ranks candidates across statistical diagnostics and BioSymphony fermentation intelligence.

## Inputs

- `src/biosymphony_ferm_doe/tournament.py`
- `src/biosymphony_ferm_doe/dossier.py`
- `docs/reference-doe-fast-path.md`

## Acceptance Criteria

- Dossier includes `design_comparison.md` and `design_comparison.json`.
- Compare report shows design family, run count, accepted/rejected, total score, D/I/A/G/FDS metrics, alias pressure, feasibility, assay, response semantics, mode transfer, cost/time, robustness, and follow-up value.
- The selected design rationale is understandable to a DOE software user.
- The report lists non-statistical rejection reasons before statistical score when a design is not runnable.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py --manifest examples/xylanase-wxz1-2012/campaign_manifest.json --out /tmp/doe-parity-compare --run-budget 12
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py /tmp/doe-parity-compare
```

## Touched Areas

- `src/biosymphony_ferm_doe/tournament.py`
- `src/biosymphony_ferm_doe/dossier.py`
- `tests/`

## Dependencies

- `custom-design-core`
- `diagnostics-core`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Do not hide caveats behind a single total score. Scorecards must keep component scores visible.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: compare-designs
touched_areas:
  - src/biosymphony_ferm_doe/tournament.py
  - src/biosymphony_ferm_doe/dossier.py
  - tests/
complexity: medium
-->
