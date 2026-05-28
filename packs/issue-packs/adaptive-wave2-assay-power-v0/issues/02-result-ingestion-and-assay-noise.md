# Result Ingestion And Assay Noise

## Summary

Make first-batch result ingestion trustworthy enough to drive follow-up only from joined, usable, arm-safe rows.

## Inputs

- `src/biosymphony_ferm_doe/ingest.py` - joins, QC/trust filtering, action recommendation, negative memory
- `src/biosymphony_ferm_doe/utilities/augment_design.py` - locked rows and augment candidates
- first-batch result CSVs with `run_id`, optional `arm_id`, `qc_status`, `inclusion_status`, and `trust_score`

## Acceptance Criteria

- [ ] QC-failed, excluded, and low-trust rows do not drive action recommendations.
- [ ] `result_ingestion_report.json` records excluded, QC-failed, low-trust, and usable row counts.
- [ ] Negative-result memory remains arm-scoped when `arm_id` is present.
- [ ] Multi-arm result ledgers cannot globally narrow a mixed factor space.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_plan_wave2_ignores_qc_failed_and_low_trust_rows -v
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_multi_arm_results_do_not_drive_global_narrowing_and_memory_is_arm_scoped -v
PYTHONPATH=src python3 -m unittest tests.test_campaign_arms_ingest -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/ingest.py` - result filtering and recommendation semantics
- `src/biosymphony_ferm_doe/utilities/augment_design.py` - locked prior rows
- `tests/` - result-ingestion regressions

## Dependencies

Blocked by: baseline-contract

## Risk Notes

- Low-quality rows may be retained for provenance, but they must not silently drive narrowing, scaling, or negative memory.
- Multi-arm ledgers require per-arm planning unless an explicit active arm is selected.
- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: adaptive-wave2-assay-power-v0
pack_issue_id: result-ingestion-and-assay-noise
touched_areas:
  - src/biosymphony_ferm_doe/ingest.py
  - src/biosymphony_ferm_doe/utilities/augment_design.py
  - tests/
complexity: medium
-->
