# Agent Quickstart

This repo is designed for coding agents, but the safest first run is still local and explicit: install the CLI, run a public demo, then let the agent iterate on a manifest.

## Copy-Paste Agent Prompt

Use this prompt after cloning the repo and installing it with `python -m pip install -e .`.

```text
You are working in the BioSymphony Ferm DoE public repo.

Use the repo-local skill at skills/biosymphony-ferm-doe/SKILL.md.
Keep all work local unless I explicitly ask for a different destination.
Use public-safe fixtures or data I provide in this local workspace only.
Do not paste credentials, non-public biological material, customer records, or exact proprietary recipes into public examples.

Start with examples/demo-pb-screening-public:
1. Run ferm-doe validate examples/demo-pb-screening-public --summary.
2. Explain the readiness status and failed_check_ids, if any.
3. Generate the first-batch design, analyze the bundled synthetic results, plan follow-up, and finalize a run packet under /tmp/demo-pb.
4. Keep claim levels visible in every generated artifact.
5. Before suggesting that anything is shareable, run `make public-ready`.
```

## What The Agent Should Do

The agent should treat `campaign_manifest.json` as durable state. It should run `ferm-doe validate <campaign_dir> --summary` between meaningful edits, fix structural errors before readiness warnings, and preserve clear claim levels such as `public_synthetic_demo`, `planned_wave2_design`, and `bayesian_optimization_planned`.

The agent should not turn a YELLOW demo into a physical-execution plan. YELLOW usually means the fixture is useful for learning the workflow, not that assay qualification, scale transfer, or statistician review has happened.

At campaign closeout, the agent should produce a campaign-local handoff file at `artifacts/<campaign>/AGENTS.md` (the canonical resume path for future agents) and capture any hiccups, excluded results, or arm-scoped negative memory in `learning_ledger.csv`, `hiccup_review.md`, and `negative_result_memory.json`. The self-learning pattern is documented in [`docs/SELF_LEARNING_DOE.md`](SELF_LEARNING_DOE.md). These artifacts are the portable memory across agent runtimes: a future Claude Code, Codex, or Symphony worker reads them the same way.

## First Useful Commands

```bash
ferm-doe validate examples/demo-pb-screening-public --summary
ferm-doe list-campaigns examples
ferm-doe inspect-campaign examples/demo-pb-screening-public
ferm-doe agent-brief examples/demo-pb-screening-public \
  --goal "Plan a safe next-experiment-round fermentation DOE campaign." \
  --out /tmp/demo-pb/agent_brief.json \
  --md-out /tmp/demo-pb/agent_brief.md
ferm-doe generate-design examples/demo-pb-screening-public \
  --out /tmp/demo-pb/wave1_design.csv \
  --metadata-out /tmp/demo-pb/wave1_design.metadata.json \
  --seed 0
ferm-doe analyze examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/wave1_analysis.json \
  --md-out /tmp/demo-pb/wave1_analysis.md \
  --seed 0
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2 \
  --remaining-budget 3
ferm-doe finalize examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/run_packet.md \
  --json-out /tmp/demo-pb/run_packet.json
```

## Create Your First Local Campaign

After the demo, make a separate local campaign directory instead of editing public fixtures in place.

```bash
mkdir -p /tmp/my-ferm-campaign/inputs /tmp/my-ferm-campaign/expected
cp templates/campaign_manifest.template.json /tmp/my-ferm-campaign/campaign_manifest.json
cp templates/operator-intake.md /tmp/my-ferm-campaign/operator-intake.md
```

Then replace every `REPLACE_ME`, add only public-safe or locally owned input rows under `inputs/`, and run:

```bash
ferm-doe validate /tmp/my-ferm-campaign --summary
```

Use the failed check IDs as the first agent worklist. Do not generate a design until structural blockers are fixed.

## Reading The Result

- `status: RED` means the proposed campaign should not advance until blockers are fixed.
- `status: YELLOW` means the plan may be useful for learning, review, or limited planning, but it still has caveats.
- `status: GREEN` means the manifest satisfies the current readiness gates. It still does not replace assay validation, statistician review, or a validated execution system.

## Where To Go Next

- [`USE_CASES.md`](USE_CASES.md): choose a workflow by job-to-be-done.
- [`PUBLIC_ADOPTION_PATH.md`](PUBLIC_ADOPTION_PATH.md): move from CLI-only to repo-local skill to harness configs.
- [`PUBLIC_SECURITY_MODEL.md`](PUBLIC_SECURITY_MODEL.md): understand the local-first privacy boundary.
- [`../examples/README.md`](../examples/README.md): pick the right public fixture for a first run.
