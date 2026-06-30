# Input Materialization

## Summary

Materialize user-owned factor spaces and constraint sets into campaign state without flattening multi-arm campaigns.

## Inputs

- `src/biosymphony_ferm_doe/compiler.py` - campaign state compilation
- `examples/scfv-fusion-acf-fedbatch-v0/inputs/factor_space.yaml` - multi-arm fixture
- `examples/scfv-fusion-acf-fedbatch-v0/inputs/constraint_set.yaml` - rich constraints fixture

## Acceptance Criteria

- [ ] `factor_space.yaml|json|csv` and `constraint_set.yaml|json|csv` are loaded from `inputs[]`.
- [ ] Inline manifest definitions win over external duplicate IDs and conflicts are recorded.
- [ ] Multi-arm factor spaces are preserved; executable factor flattening requires an active arm/space.
- [ ] Rich authored constraints remain separate from executable row constraints.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_materialization -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/compiler.py` - materialization hook
- `src/biosymphony_ferm_doe/materialization.py` - loaders and merge rules
- `tests/` - YAML/JSON/CSV materialization coverage

## Dependencies

Blocked by: baseline-contract

## Risk Notes

- Do not write back to user input files.
- Do not collapse plate-only and reactor-only factors into one chimeric DOE table.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: input-materialization
touched_areas:
  - src/biosymphony_ferm_doe/compiler.py
  - src/biosymphony_ferm_doe/materialization.py
  - tests/
complexity: large
-->
