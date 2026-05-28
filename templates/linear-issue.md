## Summary

<One or two sentence scientific work contract and expected artifact outcome.>

## Inputs

- `<input id>` - <source, local path, secure store reference, database accession, or sanitized example path>

## Acceptance Criteria

- [ ] <Specific, testable assertion, e.g. `campaign_manifest.json` validates with the preflight script.>
- [ ] <Specific artifact assertion, e.g. `selected_wave_1_design.csv` exists and every run has valid factor bounds.>
- [ ] <Specific scientific assertion, e.g. assay readiness verdict records dynamic range, controls, and caveats.>

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py <artifact path>
```

## Touched Areas

- `<path>` - <why this area is in scope>

## Dependencies

Blocked by: <issue-id or none>

## Risk Notes

- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear.
- Separate source-extracted data from inferred, transformed, and synthetic planning data.
- Record confidence limitations for assay readiness, historical-data trust, and model-based design recommendations.
- For long or remote runs, require a stage contract, progress ledger, actual provider/container state, `provider_handoff.json` when mutation is orchestrator-side, and explicit partial/degraded closeout for any fallback.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - <path>
complexity: medium
-->
