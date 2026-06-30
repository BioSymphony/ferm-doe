# Design Family Generators

## Summary

Implement explicit generators or adapters for the design families DOE software users expect: screening, DSD-like, RSM, mixture, mixture-process, space-filling, and custom optimal.

## Inputs

- `src/biosymphony_ferm_doe/doe.py`
- `pyproject.toml`
- `docs/reference-doe-fast-path.md`

## Acceptance Criteria

- Screening generator supports full/fractional factorial, Plackett-Burman, mixed-level screening, and DSD-like candidates.
- RSM generator supports CCD-like, Box-Behnken-like, and custom quadratic candidates with center/lack-of-fit planning.
- Mixture generator supports component bounds, sum constraints, and mixture-process candidates.
- Space-filling generator supports LHS and at least one low-discrepancy adapter or deterministic equivalent.
- Custom optimal generator scores candidate sets against selected optimality criteria.
- Optional PyDOE/SciPy adapters are used when installed, with stdlib fallback preserved.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 skills/biosymphony-ferm-doe/scripts/propose_wave1_design.py --manifest examples/xylanase-wxz1-2012/campaign_manifest.json --out /tmp/doe-parity-families --run-budget 16
```

## Touched Areas

- `src/biosymphony_ferm_doe/doe.py`
- `pyproject.toml`
- `tests/`

## Dependencies

- `custom-design-core`

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations. Do not add a dependency that breaks stdlib-only execution for Symphony workers.

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v0
pack_issue_id: design-family-generators
touched_areas:
  - src/biosymphony_ferm_doe/doe.py
  - pyproject.toml
  - tests/
complexity: large
-->
