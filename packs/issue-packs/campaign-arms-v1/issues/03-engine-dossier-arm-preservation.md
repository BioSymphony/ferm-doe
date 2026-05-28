# Engine And Dossier Arm Preservation

## Summary

Preserve `arm_id` through campaign compilation, factor and constraint materialization, design selection, execution planning, and dossier artifacts.

## Inputs

- `src/biosymphony_ferm_doe/compiler.py` - campaign state compilation
- `src/biosymphony_ferm_doe/materialization.py` - factor and constraint loaders
- `src/biosymphony_ferm_doe/doe.py` - design generation and active-factor-space behavior
- `src/biosymphony_ferm_doe/dossier.py` - dossier compiler
- `docs/data-model.md` - arm data contract

## Acceptance Criteria

- [ ] Materialized factors, constraints, responses, and selected designs retain `arm_id` or explicit projection metadata.
- [ ] Design generation requires an active arm/factor space when multiple executable arms exist.
- [ ] Dossier outputs include `campaign_arms.json`, `per_arm_projection_summary.json`, `arm_bridge_policy.md`, and arm-aware run-sheet fields.
- [ ] Cross-arm bridge rules state which plate or flask signals can become reactor priors and which cannot.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/campaign-arms-v1/issues/03-engine-dossier-arm-preservation.md
PYTHONPATH=src python3 -m unittest tests.test_materialization tests.test_execution_plan tests.test_engine -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/compiler.py` - arm-aware campaign state
- `src/biosymphony_ferm_doe/materialization.py` - arm-owned factor and constraint refs
- `src/biosymphony_ferm_doe/doe.py` - active arm and projection behavior
- `src/biosymphony_ferm_doe/dossier.py` - arm dossier artifacts
- `tests/` - engine and dossier preservation coverage

## Dependencies

Blocked by: CA-W1-01

## Risk Notes

- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in tests or fixtures.
- Do not silently combine incompatible vessel formats into one executable table.
- Mark fallback or projection limits as dossier caveats instead of smoothing them out.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: campaign-arms-v1
pack_issue_id: CA-W2-01
touched_areas:
  - src/biosymphony_ferm_doe/compiler.py
  - src/biosymphony_ferm_doe/materialization.py
  - src/biosymphony_ferm_doe/doe.py
  - src/biosymphony_ferm_doe/dossier.py
  - tests/
complexity: large
-->
