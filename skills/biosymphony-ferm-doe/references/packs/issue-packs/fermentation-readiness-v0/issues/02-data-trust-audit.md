## Summary

Audit source-derived run ledgers and assign inclusion status, trust scores, and transformation notes.

## Inputs

- `historical_run_ledger` - selected run ledger path
- `source_catalog` - selected source catalog path

## Acceptance Criteria

- [ ] Every run has inclusion status.
- [ ] Every run has source DOI or secure-store reference.
- [ ] Excluded or caveated rows have a reason.

## Validation Commands

```bash
python3 - <<'PY'
import csv
with open("examples/xylanase-wxz1-2012/inputs/historical_run_ledger.csv", newline="") as handle:
    rows = list(csv.DictReader(handle))
assert rows, "historical run ledger has no rows"
assert "trust_score" in rows[0], "trust_score column missing"
PY
```

## Touched Areas

- `ferm-doe-dossier/` - data trust report output

## Dependencies

Blocked by: campaign-contract

## Risk Notes

- Separate source-extracted, inferred, and synthetic values.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->
