## Summary

Compile the selected first-batch run packet and pre-register follow-up decision rules.

## Inputs

- `design_tournament_report` - upstream dossier artifact
- `selected_goal_pack` - selected goal pack path

## Acceptance Criteria

- [ ] Run sheet, result capture template, and follow-up decision rules are drafted.
- [ ] Physical execution caveats are visible at the top of the packet.
- [ ] Output paths are listed for local or approved remote reproduction where applicable.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py ferm-doe-dossier
python3 skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py ferm-doe-dossier
```

## Touched Areas

- `ferm-doe-dossier/` - run packet and decision rules

## Dependencies

Blocked by: design-tournament

## Risk Notes

- The packet is not a physical-execution authorization unless a human explicitly approves physical setup.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - ferm-doe-dossier/
complexity: medium
-->
