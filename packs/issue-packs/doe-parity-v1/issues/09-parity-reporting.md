# Parity Reporting

## Summary

Make the user-facing parity reports match actual behavior and spell out assumptions, optional adapters, and non-parity boundaries.

## Inputs

- `src/biosymphony_ferm_doe/parity.py` - parity matrix and non-parity report
- `skills/biosymphony-ferm-doe/SKILL.md` - operator guidance
- `docs/high-roi-doe-parity-strategy.md` - product posture

## Acceptance Criteria

- [ ] Reports distinguish exact, adapter-backed, approximate, and heuristic claims.
- [ ] `assumptions_and_nonparity.md` names local stdlib fallback scope and optional adapter gaps.
- [ ] Skill guidance says users can choose screening, scouting, RSM, mixture, custom constrained, augmentation, confirmatory, or user-supplied DOE.
- [ ] Docs align with engine behavior and do not claim commercial DOE clone parity.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_skill_operator_reference_map_covers_success_path tests.test_engine.EngineTests.test_doe_parity_artifacts -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/parity.py` - report text
- `skills/biosymphony-ferm-doe/SKILL.md` - skill guidance
- `docs/` - durable product docs
- `tests/` - reference-map and parity-report checks

## Dependencies

Blocked by: benchmark-harness, dossier-integration

## Risk Notes

- Prefer explicit caveats over vague confidence.
- Do not hide optional dependency absence.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: parity-reporting
touched_areas:
  - src/biosymphony_ferm_doe/parity.py
  - skills/biosymphony-ferm-doe/SKILL.md
  - docs/
  - tests/
complexity: medium
-->
