# Dossier Integration And follow-up Memory Hooks

## Summary

Integrate swarm artifacts into the dossier and preserve attack findings as follow-up memory.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `dossier_manifest.json`
- `wave_2_decision_rules.md`

## Acceptance Criteria

- Swarm artifacts are required only when `swarm_policy.enabled` is true.
- follow-up rules mention assay/process/runability blockers surfaced by the swarm.
- No live Linear, Symphony, RunPod, or GxP/GMP workflow is launched.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-dossier --enable-swarm
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py /tmp/biosymphony-swarm-dossier
```

## Touched Areas

- `ferm-doe-dossier/`

## Dependencies

- SW-W3-01

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W4-01
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->
