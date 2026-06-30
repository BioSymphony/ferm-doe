# Public Adoption Path

This repo is useful in several modes. Start with the local CLI, then add the repo-local skill, tracker integration, issue packs, or cloud endpoints only when the workflow needs them. For the full decision map, see [`WORKFLOWS.md`](WORKFLOWS.md).

## 1. CLI-Only

Use this path when you want deterministic local checks and generated artifacts.

```bash
python -m pip install -e .
ferm-doe validate examples/demo-pb-screening-public --summary
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
  --out /tmp/demo-pb/run_packet.md \
  --json-out /tmp/demo-pb/run_packet.json \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv
```

## 2. Repo-Local Skill

Use this path when a coding agent needs durable campaign behavior. Point the agent at [`../skills/biosymphony-ferm-doe/SKILL.md`](../skills/biosymphony-ferm-doe/SKILL.md) from the checkout. Keep it repo-local or workflow-scoped; do not copy it into a global always-on skill root.

Create a separate local campaign before adapting examples:

```bash
mkdir -p /tmp/my-ferm-campaign/inputs /tmp/my-ferm-campaign/expected
cp templates/campaign_manifest.template.json /tmp/my-ferm-campaign/campaign_manifest.json
cp templates/operator-intake.md /tmp/my-ferm-campaign/operator-intake.md
ferm-doe validate /tmp/my-ferm-campaign --summary
```

The agent loop is:

1. Read or create `campaign_manifest.json`.
2. Run `ferm-doe validate <campaign_dir> --summary`.
3. Fix structural errors first, then readiness warnings.
4. Generate or refresh design, analysis, follow-up, dossier, and handoff artifacts.
5. Re-run validation and the public release scanner before sharing artifacts.

## 3. Harness Configs

Use this path when a long-running orchestrator owns tasks, state, and review.

- [`../agents/generic.md`](../agents/generic.md): minimal harness contract.
- [`../agents/claude.md`](../agents/claude.md): Claude Code-oriented usage.
- [`../agents/openai.yaml`](../agents/openai.yaml): OpenAI Agents SDK / Codex-compatible config.
- [`../agents/linear.md`](../agents/linear.md): Linear issue mapping and status comments.

The public harness boundary is intentionally conservative: the CLI and skill can produce planning artifacts, but they do not approve physical execution, validate assays, or replace statistician review.

## 4. Linear And Tracker Workflows

Use this path when a planning program needs status, owners, and durable review history. The skill does not depend on Linear; a Linear-capable agent or custom orchestrator owns credentials and API calls.

- One Linear issue maps to one campaign directory.
- Sub-issues map to waves or bounded work packets.
- Comments should include `ferm-doe validate <campaign_dir> --summary` JSON.
- Status mirrors readiness: `RED` for triage or blocked, `YELLOW` for in progress, `GREEN` for ready for review.
- `stop_rules[]` firing should move the issue to blocked and tag the responsible role.

See [`../agents/linear.md`](../agents/linear.md) and [`WORKFLOWS.md`](WORKFLOWS.md).

## 5. Engine And Issue Packs

The full local engine surface lives under `ferm-doe engine ...`:

```bash
ferm-doe engine compile-state \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/ferm-doe-state

ferm-doe engine generate-issue-pack \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/ferm-doe-issues \
  --pack fermentation-readiness-v0

ferm-doe engine compile-dossier \
  --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json \
  --out /tmp/ferm-doe-dossier \
  --run-budget 16

ferm-doe engine check-dossier /tmp/ferm-doe-dossier
ferm-doe engine contract-self-check /tmp/ferm-doe-dossier
```

See [`../packs/README.md`](../packs/README.md) for pack names and [`engine-implementation.md`](engine-implementation.md) for the broader command map.

## 6. Optional Cloud Resources

Use cloud resources only when they add value. The local CLI remains the reference path.

- [`../deploy/aws-lambda/`](../deploy/aws-lambda/): lightweight stdlib subcommands behind API Gateway.
- [`../deploy/modal/`](../deploy/modal/): heavier BoTorch follow-up endpoint with scale-to-zero and GPU-flag-ready shape.

Keep endpoints stateless, credentials in provider secrets, and campaign state in an upstream store such as a repo, object store, database, or tracker. Add spend alarms, rate limits, request-size limits, and logging-retention policy before serving other users.

## 7. Before Sharing

Run these gates from the repo root:

```bash
make public-ready
```

`make public-ready` runs the release checks and requires gitleaks. If gitleaks is not installed, install it or use CI before public sharing. Do not publish private or unpublished data; keep it in a separate private workspace and publish only sanitized manifests, source metadata, synthetic fixtures, and claim-bounded summaries.
