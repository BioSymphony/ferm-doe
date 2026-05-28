# Self-Learning DOE Runbook

This runbook makes adaptive DOE learning durable without pretending that planned rows or agent notes are experimental proof.

## Purpose

BioSymphony should learn from hiccups as much as from clean response improvements. A failed join, noisy assay, blocked bridge, chimeric arm row, QC exclusion, operator override, or empty augment table is useful campaign memory if it is recorded with a source artifact and a claim boundary.

The learning loop is:

1. Capture the hiccup in `learning_ledger.csv`.
2. Summarize the human-readable state in `hiccup_review.md`.
3. Decide whether the event changes factor space, assay policy, bridge policy, execution planning, or only the operator runbook.
4. Queue explicit manifest or contract patches instead of editing old evidence in place.
5. Rerun readiness, `plan-wave2`, dossier check, and contract self-check after patches.
6. Link durable lessons from `artifacts/<campaign>/AGENTS.md` and, when broadly reusable, a dated `logs/YYYY-MM-DD-<campaign>-learnings-review.md`.

## What Counts As A Learning Event

- result rows do not join `selected_wave_1_design.csv`
- result rows are missing `arm_id` or contain cross-arm factor leakage
- QC-failed, excluded, or low-trust rows would have changed the recommendation if not filtered
- assay power fails or has unresolved LOQ, dynamic range, recovery, CV, replicate, or turnaround gaps
- bridge policy blocks `scale_or_downscale`
- `pause` or `stop` is recommended
- an operator manually overrides the recommendation
- a generated augment row is physically impossible, over capacity, or conflicts with the lab schedule
- a prior assumption is superseded by executed evidence

## Required Campaign Files

- `learning_ledger.csv` - structured event memory
- `hiccup_review.md` - operator-readable summary
- `wave2_manifest.patch.json` - deterministic patch proposal from adaptive planning
- `artifacts/<campaign>/AGENTS.md` - canonical future-agent handoff
- `logs/YYYY-MM-DD-<campaign>-learnings-review.md` - durable cross-campaign lesson when the finding should update future behavior

Use `templates/doe-learning-ledger.template.csv` and `templates/doe-hiccup-report.template.md` when starting a campaign before `plan-wave2` has generated files.

## Claim Boundary

Learning events are not validation evidence by themselves. They can justify pausing, repairing a contract, changing a future design, or updating negative memory. They cannot justify optimized, validated, production-ready, formal-power, or scale-transfer claims unless executed rows later join and the contract self-check passes.

## Closeout Checklist

- [ ] Every blocker or warning in `learning_ledger.csv` has an owner, status, and follow-up validation command.
- [ ] Any manifest patch is explicit and rerun through readiness or dossier compilation.
- [ ] Any assay-power repair reruns `ferm-doe assay-power <campaign>`.
- [ ] Any scale/downscale repair reruns bridge eligibility through `ferm-doe plan-wave2`.
- [ ] `AGENTS.md` links the latest adaptive packet and names superseded artifacts.
- [ ] Broad lessons are copied to `logs/` without private process records or confidential media details.
