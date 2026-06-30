# Campaign Arms Contract

## Summary

Define the first-class `campaign_arms` contract for coupled plate, flask, and bioreactor campaigns, including the degraded fallback rules when the engine cannot yet execute all arm behavior.

## Inputs

- `docs/data-model.md` - canonical campaign data model
- `docs/sidecar-architecture.md` - sidecar composition rules
- `skills/biosymphony-ferm-doe/SKILL.md` - operator and worker guidance
- `packs/issue-packs/campaign-arms-v1/pack.yaml` - issue graph

## Acceptance Criteria

- [ ] `campaign_arms` is documented as a required contract surface for coupled campaigns, not a narrative-only artifact.
- [ ] Required arm fields cover purpose, format, run budget, factor space, constraints, responses, assay policy, execution capabilities, bridge role, and readiness verdict.
- [ ] Degraded linked-manifest fallback is allowed only with an explicit bridge artifact and dossier limitation.
- [ ] CA-W1 through CA-W3 remain in Backlog until this contract is accepted.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/campaign-arms-v1/issues/01-campaign-arms-contract.md
```

## Touched Areas

- `docs/data-model.md` - campaign arms contract
- `docs/sidecar-architecture.md` - sidecar arm preservation rule
- `docs/linear-issue-pack-strategy.md` - pack activation strategy
- `skills/biosymphony-ferm-doe/SKILL.md` - worker guidance
- `packs/issue-packs/campaign-arms-v1/` - issue graph

## Dependencies

Blocked by: none

## Risk Notes

- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear.
- Do not flatten plate-only and reactor-only factors into one chimeric DOE table.
- Do not claim coupled-arm optimization before executed result rows and confirmatory validation exist.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: campaign-arms-v1
pack_issue_id: CA-W0-01
touched_areas:
  - docs/data-model.md
  - docs/sidecar-architecture.md
  - docs/linear-issue-pack-strategy.md
  - skills/biosymphony-ferm-doe/SKILL.md
  - packs/issue-packs/campaign-arms-v1/
complexity: medium
-->
