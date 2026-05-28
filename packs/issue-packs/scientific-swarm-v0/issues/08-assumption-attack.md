# Assumption Attack And Contradiction Reconciliation

## Summary

Run adversarial review against factor ranges, response semantics, assay readiness, process transfer, sampling, cost, and run duration.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `assumption_attack_report.json`
- `assumption_attack_report.md`

## Acceptance Criteria

- Challenges are categorized, severity-labeled, and tied to affected factors or responses.
- Contradictions become either resolved assumptions, dossier caveats, or stop conditions.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-attack
test -f /tmp/biosymphony-swarm-attack/assumption_attack_report.md
```

## Touched Areas

- `ferm-doe-dossier/swarm/assumption-attack/`

## Dependencies

- SW-W1-01
- SW-W1-03
- SW-W1-04
- SW-W1-05

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, confidential media formulations, or GxP/GMP claims. This is local dry-run planning only.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W2-02
touched_areas:
  - ferm-doe-dossier/swarm/assumption-attack/
complexity: large
-->
