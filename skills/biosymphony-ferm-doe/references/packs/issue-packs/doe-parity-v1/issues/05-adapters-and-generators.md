# Adapters And Generators

## Summary

Add optional DOE adapter paths behind the stdlib fallback, and keep backend labels honest when an adapter is available but not used.

## Inputs

- `src/biosymphony_ferm_doe/doe.py` - candidate generation
- `src/biosymphony_ferm_doe/utilities/deps.py` - optional dependency detection
- `src/biosymphony_ferm_doe/utilities/common.py` - backend and claim manifest output

## Acceptance Criteria

- [ ] SciPy QMC LHS/Sobol paths emit adapter-backed rows only when that adapter code path executed.
- [ ] PB, factorial, RSM, and mixture stdlib fallbacks carry non-parity labels unless exactness is proven.
- [ ] Custom constrained selection uses a named D/I/A/G or space-filling criterion trace.
- [ ] Stdlib-only and optional-adapter environments both produce valid dossiers.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_doe_parity_v1 -v
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_utility_check_deps_reports_missing_optional_without_failure -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/doe.py` - adapter and fallback candidate rows
- `src/biosymphony_ferm_doe/utilities/` - backend status and utility manifests
- `tests/` - fallback and adapter-truthfulness coverage

## Dependencies

Blocked by: intent-and-claims

## Risk Notes

- Backend availability is not backend execution.
- Do not use optional commercial/proprietary format claims unless an import/export validator exists.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: adapters-and-generators
touched_areas:
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/utilities/
  - tests/
complexity: large
-->
