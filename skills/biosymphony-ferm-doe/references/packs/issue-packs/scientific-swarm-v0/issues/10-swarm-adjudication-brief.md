# Swarm Adjudication Brief For DOE Tournament

## Summary

Condense factor universe, evidence quality, assumption attack, observability, and controls into an adjudication brief for DOE selection.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `swarm_adjudication_brief.md`

## Acceptance Criteria

- The brief states which issues should veto, constrain, or reweight DOE candidates.
- It is short enough for a DOE/statistics worker to consume before proposing designs.
- It distinguishes high-quality evidence from low-provenance claims and states whether controls should become executable rows.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-brief
test -f /tmp/biosymphony-swarm-brief/swarm_adjudication_brief.md
```

## Touched Areas

- `ferm-doe-dossier/swarm/`

## Dependencies

- SW-W2-01
- SW-W2-02
- SW-W2-03

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W3-01
touched_areas:
  - ferm-doe-dossier/swarm/
complexity: medium
-->
