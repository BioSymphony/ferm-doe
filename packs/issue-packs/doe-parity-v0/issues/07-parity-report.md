# User-Facing Parity Report

## Summary

Create the user-facing output that makes BioSymphony feel reference DOE: familiar DOE labels, explicit parity status, exportable tables, diagnostics, and BioSymphony-only fermentation warnings.

## Inputs

- `docs/reference-doe-fast-path.md`
- `src/biosymphony_ferm_doe/dossier.py`
- `README.md`

## Acceptance Criteria

- Dossier includes `doe_parity_report.md` and `assumptions_and_nonparity.md`.
- Report states which reference DOE surfaces are matched, approximated, missing, or exceeded.
- Report includes source-linked reference DOE benchmark references.
- Report includes a "why BioSymphony selected this design" section.
- README links the reference DOE fast path.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py --manifest examples/xylanase-wxz1-2012/campaign_manifest.json --out /tmp/doe-parity-report --run-budget 12
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py /tmp/doe-parity-report
```

## Touched Areas

- `docs/`
- `src/biosymphony_ferm_doe/dossier.py`
- `README.md`
- `tests/`

## Dependencies

- `compare-designs`
- `augment-and-bayesopt`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Do not claim "beats reference DOE" generically. Claim specific ways BioSymphony adds fermentation campaign intelligence and list remaining non-parity areas.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: parity-report
touched_areas:
  - docs/
  - src/biosymphony_ferm_doe/dossier.py
  - README.md
  - tests/
complexity: medium
-->
