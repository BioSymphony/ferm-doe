# Power Policy And Readiness

## Summary

Add response-level assay-power checks that gate fitted or confirmatory DOE claims without assigning fake wet-assay requirements to derived metrics.

## Inputs

- `src/biosymphony_ferm_doe/assay_power.py` - response-level policy evaluator
- `src/biosymphony_ferm_doe/readiness.py` - assay-power readiness gate
- `src/biosymphony_ferm_doe/tournament.py` - intent-aware rejection or downgrade

## Acceptance Criteria

- [ ] Assayed responses can declare minimum detectable effect, expected effect, noise/CV, replicates, target power, LOD, LOQ, dynamic range, recovery, and turnaround.
- [ ] Cost, duration, and calculated responses are `NOT_APPLICABLE` for wet-assay power.
- [ ] Weak primary-response assay power blocks strong `rsm_fit`, `confirmatory`, and exact-required claims.
- [ ] Assay-power reports are labeled as planning checks, not formal analytical-method validation.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_assay_power_utility_passes_and_derived_responses_are_not_assay -v
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_assay_power_fails_for_missing_loq_high_cv_weak_recovery_and_replicates -v
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_tournament_rejects_strong_claim_intent_when_assay_power_is_weak -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/assay_power.py` - core evaluator
- `src/biosymphony_ferm_doe/utilities/assay_power.py` - standalone utility
- `src/biosymphony_ferm_doe/readiness.py` - readiness gate
- `src/biosymphony_ferm_doe/tournament.py` - claim-aware acceptance

## Dependencies

Blocked by: baseline-contract

## Risk Notes

- The stdlib power proxy is a deterministic planning check, not formal statistical power analysis.
- Do not infer wet-assay requirements for derived cost, duration, or schedule metrics.
- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: adaptive-wave2-assay-power-v0
pack_issue_id: power-policy-and-readiness
touched_areas:
  - src/biosymphony_ferm_doe/assay_power.py
  - src/biosymphony_ferm_doe/utilities/assay_power.py
  - src/biosymphony_ferm_doe/readiness.py
  - src/biosymphony_ferm_doe/tournament.py
complexity: large
-->
