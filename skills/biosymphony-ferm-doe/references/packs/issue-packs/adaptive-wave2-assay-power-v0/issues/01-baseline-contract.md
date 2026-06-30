# Baseline Contract

## Summary

Lock the adaptive follow-up artifact contract and prove the existing unit baseline is green before result-driven planning changes are activated.

## Inputs

- `docs/adaptive-wave2-assay-power-v0.md` - public campaign contract
- `src/biosymphony_ferm_doe/adaptive_wave2.py` - orchestration surface
- `tests/test_adaptive_wave2_assay_power.py` - campaign regression suite

## Acceptance Criteria

- [ ] `ferm-doe plan-wave2` emits the declared required artifacts deterministically.
- [ ] `adaptive_wave2_plan.json` uses claim level `planned_wave2_design`.
- [ ] Existing first-batch dossier, campaign-arms, and DOE parity tests remain compatible.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/cli.py` - command entry point
- `src/biosymphony_ferm_doe/adaptive_wave2.py` - follow-up orchestration
- `docs/` - durable campaign contract
- `tests/` - regression suite

## Dependencies

Blocked by: none

## Risk Notes

- Do not claim optimized, validated, production-ready, or scale-transfer success from planned follow-up artifacts.
- Do not store private process records, customer batch data, unpublished biology, secrets, or confidential media formulations.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: adaptive-wave2-assay-power-v0
pack_issue_id: baseline-contract
touched_areas:
  - src/biosymphony_ferm_doe/cli.py
  - src/biosymphony_ferm_doe/adaptive_wave2.py
  - docs/
  - tests/
complexity: medium
-->
