## Summary

Create the readiness dossier skeleton for the xylanase WX-Z1 public-data demo, separating source-derived numeric data from inferred or missing execution details.

## Inputs

- `campaign_manifest` - examples/xylanase-wxz1-2012/campaign_manifest.json
- `historical_run_ledger` - examples/xylanase-wxz1-2012/inputs/historical_run_ledger.csv
- `factor_space` - examples/xylanase-wxz1-2012/inputs/factor_space.yaml
- `source_catalog` - examples/xylanase-wxz1-2012/source/source_catalog.md

## Acceptance Criteria

- [ ] `outputs/readiness_verdict.md` states GREEN, YELLOW, or RED and explains the verdict.
- [ ] Source-derived fields, inferred fields, and missing fields are explicitly separated.
- [ ] Assay readiness caveats include dynamic range, controls, replicate noise, and sample handling status.
- [ ] Feasibility caveats include equipment, reagent quantity, time, vessel, agitation, pH, temperature, and sampling status.
- [ ] follow-up decision-rule placeholders are drafted for optimization, assay rescue, replication, and stop outcomes.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/xylanase-wxz1-2012/campaign_manifest.json
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/xylanase-wxz1-2012/linear_issues/wave0-readiness.md
```

## Touched Areas

- `examples/xylanase-wxz1-2012/outputs/` - readiness and dossier outputs
- `examples/xylanase-wxz1-2012/inputs/` - source-derived demo inputs

## Dependencies

Blocked by: none

## Risk Notes

- Do not store secrets, private process records, confidential strain data, or unpublished media formulations in Linear.
- This public paper-derived demo is not sufficient for physical execution without organism, assay, equipment, and safety review.
- Record confidence limitations for historical-data trust and inferred execution details.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - examples/xylanase-wxz1-2012/outputs/
  - examples/xylanase-wxz1-2012/inputs/
complexity: medium
-->

