# Adaptive follow-up Plan And Dossier

## Summary

Integrate adaptive follow-up artifacts with dossier decision rules, claim audit, and operator-facing skill guidance.

## Inputs

- `src/biosymphony_ferm_doe/dossier.py` - follow-up decision rules and assay report
- `src/biosymphony_ferm_doe/contract.py` - overclaim scanner and claim audit
- `skills/biosymphony-ferm-doe/SKILL.md` - operator workflow guidance

## Acceptance Criteria

- [ ] Dossiers emit `wave_2_decision_rules.json` and Markdown with adaptive prerequisites.
- [ ] `claim_audit.json` forbids optimized, validated, production-ready, formal-power, and follow-up success claims without executed joined evidence.
- [ ] `ferm-doe plan-wave2` writes `locked_prior_runs.csv`, `augment_design.csv`, `adaptive_trace.json`, and `wave2_manifest.patch.json`.
- [ ] Skill guidance tells agents to run the follow-up loop instead of manually narrowing result tables.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_plan_wave2_emits_required_artifacts_deterministically -v
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_contract_self_check_rejects_formal_assay_power_claim_without_backing -v
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_compile_and_check_dossier -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/adaptive_wave2.py` - artifact packet
- `src/biosymphony_ferm_doe/dossier.py` - dossier integration
- `src/biosymphony_ferm_doe/contract.py` - claim audit
- `skills/biosymphony-ferm-doe/SKILL.md` - agent guidance

## Dependencies

Blocked by: result-ingestion-and-assay-noise, power-policy-and-readiness

## Risk Notes

- `augment_design.csv` is a planned candidate table, not executed evidence.
- `scale_or_downscale` remains planning-only until bridge controls and executed confirmation evidence join.
- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: adaptive-wave2-assay-power-v0
pack_issue_id: adaptive-wave2-plan-and-dossier
touched_areas:
  - src/biosymphony_ferm_doe/adaptive_wave2.py
  - src/biosymphony_ferm_doe/dossier.py
  - src/biosymphony_ferm_doe/contract.py
  - skills/biosymphony-ferm-doe/SKILL.md
complexity: large
-->
