## Summary

Assess whether the response measurement is ready to support optimization decisions.

## Inputs

- `campaign_manifest` - selected campaign manifest path
- `historical_run_ledger` - selected run ledger path

## Acceptance Criteria

- [ ] Dynamic range, calibration, controls, replicate noise, and sample handling status are recorded.
- [ ] Missing assay evidence is listed as a blocker or caveat.
- [ ] Verdict is GREEN, YELLOW, or RED.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/xylanase-wxz1-2012/campaign_manifest.json
```

## Touched Areas

- `ferm-doe-dossier/` - assay readiness report output

## Dependencies

Blocked by: data-trust-audit

## Risk Notes

- A weak assay should produce a RED or YELLOW readiness verdict instead of a confident optimization design.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->
