# Arm Data Model And Sidecar Contract

## Summary

Implement and validate manifest, sidecar, and example contracts that preserve arm identity before design generation or dossier compilation.

## Inputs

- `docs/data-model.md` - required `campaign_arms` field definitions
- `templates/sidecar-campaign-goal.json` - goal sidecar shape
- `templates/sidecar-input-pack.json` - input sidecar shape
- `templates/sidecar-issue-pack.json` - issue sidecar shape
- `templates/campaign-contract.md` - human-readable campaign intake contract

## Acceptance Criteria

- [ ] Campaign manifests can declare `campaign_arms` with stable `arm_id` values and per-arm refs.
- [ ] Sidecar validation preserves campaign-goal, input-pack, issue-pack, and compute-policy arm references.
- [ ] Example or synthetic contracts cover at least a plate/downscale arm and a controlled bioreactor arm.
- [ ] Validation errors distinguish missing arm metadata from ordinary single-arm campaigns.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/campaign-arms-v1/issues/02-arm-data-model-sidecar.md
python3 skills/biosymphony-ferm-doe/scripts/sidecar_check.py templates/sidecar-campaign-goal.json templates/sidecar-input-pack.json templates/sidecar-issue-pack.json
```

## Touched Areas

- `src/biosymphony_ferm_doe/contract.py` - manifest and dossier contract validation
- `skills/biosymphony-ferm-doe/scripts/sidecar_check.py` - sidecar arm-reference validation
- `templates/` - arm-aware contract examples
- `examples/` - sanitized multi-arm fixture
- `tests/` - contract and sidecar coverage

## Dependencies

Blocked by: CA-W0-01

## Risk Notes

- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in fixtures.
- Keep factual extracted inputs separate from inferred or synthetic planning data.
- Do not make `campaign_arms` mandatory for ordinary single-arm campaigns.

## Complexity

tier: large

<!-- symphony:schema
schema_version: 1
pack_id: campaign-arms-v1
pack_issue_id: CA-W1-01
touched_areas:
  - src/biosymphony_ferm_doe/contract.py
  - skills/biosymphony-ferm-doe/scripts/sidecar_check.py
  - templates/
  - examples/
  - tests/
complexity: large
-->
