# Generic agent config for biosymphony-ferm-doe

Use this as a runtime-agnostic reference when integrating the skill into any agent framework.

## State model

The campaign manifest is the single source of truth. Treat `<campaign_dir>/campaign_manifest.json` as durable state and update it incrementally across turns.

## Inputs the agent should read

- `schemas/campaign_manifest.schema.json`: manifest contract
- `skills/biosymphony-ferm-doe/SKILL.md`: long-agent loop, refuse-vs-warn
- `docs/PROFILES.md`: profile registry and composition rules
- `docs/SCALE_BRIDGE.md`: scale-bridge framework
- `docs/DOE_FAMILIES.md`: design family vocabulary
- `NON_CLAIMS.md`: boundary statements

## Outputs the agent maintains

- `<campaign_dir>/campaign_manifest.json`
- `<campaign_dir>/expected/readiness_summary.json`
- `<campaign_dir>/expected/selected_wave_1_design.csv`
- `<campaign_dir>/expected/run_packet.md`
- `<campaign_dir>/expected/AGENTS.md`

## Validation tools

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate <campaign_dir> [--summary] [--out FILE]
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli audit <repo_root>
```

Exit code 1 if errors; exit code 0 if warnings only or clean.

## Conversation arc

1. **Intake**: capture user goal; pick profile(s); draft manifest skeleton.
2. **Readiness gate**: run validate; address errors then warnings.
3. **Factor framing**: declare factor types deliberately; mark hard-to-change factors when split-plot is in scope.
4. **Scale framing**: fill `scale_context` when a scale profile is declared.
5. **DoE selection**: pick a family; declare resolution / center points / replication / randomization; label statistical claim level.
6. **Run packet**: produce `expected/run_packet.md` with stop conditions linked to `stop_rules[]`.
7. **follow-up**: append to `waves[]`; evaluate `decision_rules[]`; advance, augment, narrow, or pause.

## Refuse vs warn

- Refuse (RED): missing required block for the declared profile; assayed response missing measurement contract; release-contract violation when `claim_level == public_synthetic_demo`.
- Warn (YELLOW): profile-advised gaps; DoE family minimum-runs shortfall; partial readiness state on any axis.

## Biosafety-relevant context

Before generating a first-batch design, scan the manifest for biorisk-relevant signals (unfamiliar host strain, recombinant DNA, scale-up beyond bench, factor or response language matching containment-relevant patterns). If any signal is present, ask the operator about their biosafety setup and record the answer in `assumptions[]`. The skill does not gate on biosafety; the agent surfaces the question. See [`BIOSAFETY.md`](../BIOSAFETY.md).

## Issue tracker integration (optional)

If your harness has access to an issue tracker (Linear, GitHub Issues, Jira), the conventions in [`agents/linear.md`](linear.md) generalize:

- one issue per campaign, sub-issues per wave
- comments carry `validate --summary` JSON
- issue status mirrors `readiness.overall`
- `stop_rules[]` firing moves the issue to a blocked state and tags `owner_role`

Do not require a specific tracker. The skill itself does not depend on one.
