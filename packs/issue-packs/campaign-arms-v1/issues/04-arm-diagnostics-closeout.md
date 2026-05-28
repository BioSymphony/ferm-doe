# Arm Diagnostics And Closeout Gate

## Summary

Add the final diagnostics and closeout checks that decide whether a coupled-arm campaign is executable, limited, or RED before lab handoff.

## Inputs

- `src/biosymphony_ferm_doe/tournament.py` - candidate adjudication
- `src/biosymphony_ferm_doe/model_matrix.py` - categorical association and variance diagnostics
- `src/biosymphony_ferm_doe/contract.py` - final dossier self-check
- `docs/linear-issue-pack-strategy.md` - W3 closeout policy

## Acceptance Criteria

- [ ] Dossier includes categorical aliasing diagnostics using Cramer's V or another named contingency-table association metric.
- [ ] Dossier includes per-arm continuous-factor variance and constant-factor limitations after projection.
- [ ] Final readiness verdict can be RED when campaign arms cannot be physically executed or bridged safely.
- [ ] Worker closeout records claim level as planned multi-arm campaign unless executed result rows and confirmatory validation exist.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/campaign-arms-v1/issues/04-arm-diagnostics-closeout.md
PYTHONPATH=src python3 -m unittest tests.test_doe_parity_v1 tests.test_engine -v
python3 skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py ferm-doe-dossier
```

## Touched Areas

- `src/biosymphony_ferm_doe/tournament.py` - readiness adjudication
- `src/biosymphony_ferm_doe/model_matrix.py` - arm diagnostics
- `src/biosymphony_ferm_doe/contract.py` - self-check requirements
- `ferm-doe-dossier/` - generated diagnostic artifacts
- `tests/` - closeout and diagnostic coverage

## Dependencies

Blocked by: CA-W2-01

## Risk Notes

- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in diagnostic artifacts.
- Do not describe a pre-execution campaign as optimized, validated, or ready for production.
- Treat missing assay comparability, vessel-cap, or bridge-policy evidence as a blocker or limitation.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: campaign-arms-v1
pack_issue_id: CA-W3-01
touched_areas:
  - src/biosymphony_ferm_doe/tournament.py
  - src/biosymphony_ferm_doe/model_matrix.py
  - src/biosymphony_ferm_doe/contract.py
  - ferm-doe-dossier/
  - tests/
complexity: large
-->
