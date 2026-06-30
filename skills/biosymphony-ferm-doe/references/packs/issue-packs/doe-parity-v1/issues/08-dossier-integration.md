# Dossier Integration

## Summary

Integrate DOE parity metadata, materialized inputs, and execution planning into the dossier without turning BioSymphony into a rigid DOE clone.

## Inputs

- `src/biosymphony_ferm_doe/dossier.py` - dossier compiler
- `src/biosymphony_ferm_doe/contract.py` - artifact self-check
- `src/biosymphony_ferm_doe/parity.py` - parity reports
- `examples/` - reference, xylanase, yeast, and SCFV fixtures

## Acceptance Criteria

- [ ] `selected_wave_1_design.csv` remains the statistical design table.
- [ ] `execution_plan.json` and `run-sheet.tsv` carry physical execution fields.
- [ ] DOE export includes units, transforms, blocks, hard-to-change flags, arm IDs, constraints, fixed rows, randomization, responses, assumptions, and non-parity notes.
- [ ] SCFV multi-arm materialization compiles without flattening plate/reactor factors into a chimeric design.
- [ ] Reference DOE, xylanase, yeast, and SCFV examples compile or fail with explicit readiness blockers.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_execution_plan tests.test_materialization -v
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_compile_and_check_dossier tests.test_engine.EngineTests.test_doe_parity_artifacts tests.test_engine.EngineTests.test_utility_doe_export_import_roundtrip -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/dossier.py` - dossier outputs
- `src/biosymphony_ferm_doe/contract.py` - self-check joins
- `src/biosymphony_ferm_doe/utilities/doe_compat.py` - import/export
- `tests/` - dossier and round-trip coverage

## Dependencies

Blocked by: input-materialization, execution-planner, adapters-and-generators, diagnostics-verdicts

## Risk Notes

- Do not imply a selected first-batch plan is optimized, validated, or production-ready.
- Preserve user-supplied design paths and labels instead of forcing regeneration.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: dossier-integration
touched_areas:
  - src/biosymphony_ferm_doe/dossier.py
  - src/biosymphony_ferm_doe/contract.py
  - src/biosymphony_ferm_doe/utilities/doe_compat.py
  - tests/
complexity: large
-->
