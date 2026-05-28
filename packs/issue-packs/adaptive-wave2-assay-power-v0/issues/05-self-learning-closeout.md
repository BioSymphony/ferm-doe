# Self-Learning Closeout

## Summary

Capture adaptive DOE hiccups as durable campaign memory so future agents can repair contracts and improve follow-up planning without rewriting old evidence.

## Inputs

- `docs/self-learning-doe-runbook.md` - learning loop and closeout rules
- `templates/doe-learning-ledger.template.csv` - structured event ledger
- `templates/doe-hiccup-report.template.md` - operator-readable incident review
- `adaptive-wave2/learning_ledger.csv` and `adaptive-wave2/hiccup_review.md` - generated campaign artifacts

## Acceptance Criteria

- [ ] `plan-wave2` emits `learning_ledger.csv` and `hiccup_review.md`.
- [ ] Join failures, QC exclusions, low-trust rows, assay-power gaps, bridge blocks, arm-scope errors, and pause/stop decisions are recorded with a source artifact and claim boundary.
- [ ] Open learning events include follow-up validation commands or a clear operator decision.
- [ ] `artifacts/<campaign>/AGENTS.md` links the current adaptive packet and names superseded readiness or follow-up artifacts.
- [ ] Broadly reusable lessons are promoted to `logs/YYYY-MM-DD-<campaign>-learnings-review.md` without private process records or confidential media details.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power.AdaptiveFollowUpAssayPowerTests.test_plan_wave2_emits_required_artifacts_deterministically -v
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py packs/issue-packs/adaptive-wave2-assay-power-v0/issues/05-self-learning-closeout.md
```

## Touched Areas

- `src/biosymphony_ferm_doe/adaptive_wave2.py` - generated learning artifacts
- `docs/self-learning-doe-runbook.md` - durable runbook
- `templates/doe-learning-ledger.template.csv` - ledger template
- `templates/doe-hiccup-report.template.md` - report template
- `artifacts/<campaign>/AGENTS.md` - future-agent handoff

## Dependencies

Blocked by: adaptive-wave2-plan-and-dossier

## Risk Notes

- Learning events are planning memory, not validation evidence.
- Do not store secrets, private strain/process data, customer batch records, unpublished sequences, or confidential media formulations in Linear or repo artifacts.
- Do not let a self-learning entry strengthen claim level without executed joined evidence and a passing contract self-check.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: adaptive-wave2-assay-power-v0
pack_issue_id: self-learning-closeout
touched_areas:
  - src/biosymphony_ferm_doe/adaptive_wave2.py
  - docs/self-learning-doe-runbook.md
  - templates/doe-learning-ledger.template.csv
  - templates/doe-hiccup-report.template.md
  - artifacts/<campaign>/AGENTS.md
complexity: medium
-->
