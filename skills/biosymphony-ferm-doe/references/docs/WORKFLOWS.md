# Workflow Guide

BioSymphony Ferm DoE is useful in several operating modes. Start local, then add agents, trackers, or cloud resources only when the campaign needs them.

## Workflow Chooser

| If you are... | Use this workflow | Primary files | First command or doc |
|---|---|---|---|
| Trying the repo for the first time | Local closed-loop demo | `examples/demo-pb-screening-public/` | `ferm-doe validate examples/demo-pb-screening-public --summary` |
| Asking a coding agent to plan a campaign | Repo-local skill loop | `skills/biosymphony-ferm-doe/SKILL.md`, `campaign_manifest.json` | [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) |
| Running a multi-week planning program | Issue-pack or tracker-driven workflow | `packs/`, `expected/AGENTS.md`, tracker comments | [`ISSUE_PACK_COOKBOOK.md`](ISSUE_PACK_COOKBOOK.md) |
| Managing work in Linear | Linear-aware agent loop | `agents/linear.md`, `campaign_manifest.json` | [`../agents/linear.md`](../agents/linear.md) |
| Serving lightweight checks behind an API | AWS Lambda scaffold | `deploy/aws-lambda/` | [`../deploy/aws-lambda/README.md`](../deploy/aws-lambda/README.md) |
| Serving heavy BoTorch follow-up planning | Modal scaffold | `deploy/modal/` | [`../deploy/modal/README.md`](../deploy/modal/README.md) |
| Comparing adaptive backends | Backend evaluation workflow | `docs/adaptive-backend-evaluation.json` | [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) |
| Preparing public examples or docs | Public release workflow | `docs/RELEASE_READINESS_CHECKLIST.md`, scanners | [`RELEASE_READINESS_CHECKLIST.md`](RELEASE_READINESS_CHECKLIST.md) |

## What Users Get

- A manifest that records the question, factors, responses, assay contracts, scale context, decision rules, and caveats.
- A readiness verdict that can say `RED`, `YELLOW`, or `GREEN` with specific failed checks.
- A first-batch design with claim-level labels.
- first-batch analysis with effect estimates, permutation p-values, bootstrap CIs, and review artifacts.
- follow-up planning with negative-result memory, learning ledgers, and backend route recommendations.
- A run packet and `expected/AGENTS.md` handoff for the next agent, scientist, statistician, or tracker issue.
- Optional orchestration paths for Linear, issue packs, AWS Lambda, Modal, and custom agent harnesses.

## Local CLI Workflow

Use this when you want deterministic artifacts with no agent runtime and no cloud account.

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
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/run_packet.md \
  --json-out /tmp/demo-pb/run_packet.json
```

Best for:

- learning the contract
- validating public fixtures
- producing local review artifacts
- running in CI

## Coding-Agent Workflow

Use this when a campaign spans more than one turn and the agent needs durable memory.

1. Point the agent at [`../skills/biosymphony-ferm-doe/SKILL.md`](../skills/biosymphony-ferm-doe/SKILL.md).
2. Keep state in `<campaign_dir>/campaign_manifest.json`.
3. Run `ferm-doe validate <campaign_dir> --summary` between meaningful edits.
4. Write generated artifacts under `<campaign_dir>/expected/`.
5. Update `<campaign_dir>/expected/AGENTS.md` before pausing.

The skill does not need a specific agent runtime. Claude Code, OpenAI Agents SDK, Codex CLI, and custom orchestrators all work if they can read files, write files, and run shell commands.

Best for:

- long-horizon campaign planning
- iterative readiness rescue
- evidence-backed factor-space refinement
- handoff between multiple agents or reviewers

## Linear Workflow

Use this when a planning program needs status, ownership, review history, and a clean way to keep many agent tasks moving.

| Linear object | BioSymphony object |
|---|---|
| Project | related campaign family |
| Issue | one campaign directory |
| Sub-issue | one wave or bounded work packet |
| Comment | `validate --summary`, handoff note, or decision update |
| Status | readiness verdict or blocked state |
| Label | profile, worst axis, or owner role |

Recommended loop:

1. Create or select a Linear issue for the campaign.
2. Agent derives or updates `campaign_manifest.json`.
3. Agent posts tracker-safe `ferm-doe validate <campaign_dir> --summary` fields as a Linear comment.
4. Agent mirrors readiness to status: `RED` -> triage or blocked, `YELLOW` -> in progress, `GREEN` -> ready for review.
5. follow-up or scale-bridge work becomes a sub-issue with the parent campaign linked.
6. `stop_rules[]` firing moves the issue to blocked and tags the responsible role.

Tracker-safe comments contain only status, worst axis, failed check IDs, warning/error counts, artifact references, manifest version, and next requested action. Do not paste full manifests, result rows, assay details, biosafety answers, cloud URLs, provider logs, credentials, or customer/process records into tracker comments unless a private workspace retention/export policy explicitly allows it.

The skill itself never authenticates to Linear. Linear credentials, API calls, labels, and team taxonomy belong to the external agent harness. See [`../agents/linear.md`](../agents/linear.md).

Best for:

- multi-person planning programs
- agent work queues
- readiness audit trails
- explicit escalation when a design should not advance

## Cloud Resource Workflow

Cloud resources are optional wrappers around the same stateless commands. Use them when they make the workflow faster or easier to integrate; they are not required for normal local use.

| Need | Recommended scaffold | Why |
|---|---|---|
| Low-latency validation, design, analysis, scale/cost/sampling helpers, and stdlib follow-up planning | [`../deploy/aws-lambda/`](../deploy/aws-lambda/) | stdlib-only commands are small and cheap behind API Gateway |
| Heavy BoTorch follow-up planning | [`../deploy/modal/`](../deploy/modal/) | `torch + botorch + gpytorch` belongs in a heavier image with scale-to-zero |
| GPU experimentation | Modal GPU flag or equivalent provider | use only after spend, auth, and cleanup review |
| Persistent campaign state | Upstream store such as a repo, S3, database, or tracker | the endpoints should stay stateless |

Cloud rules:

- Keep credentials in provider secrets or upstream identity.
- Send bearer tokens in headers, not request bodies.
- Keep manifests and results bounded in size.
- Add rate limits, spend alarms, logging-retention rules, and tenant boundaries before serving other users.
- Do not move protected biological, operational, or customer data into a public endpoint by default.
- Run `make public-ready` before sharing deployment examples.

Best for:

- integrating with a web app or internal platform
- letting multiple agents call the same validation endpoint
- isolating heavy optional dependencies away from laptops and CI
- scaling backend comparisons without changing the manifest contract

## Issue-Pack Workflow

Use issue packs when a single campaign becomes too large for one agent session.

```bash
ferm-doe engine generate-issue-pack \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/ferm-doe-issues \
  --pack fermentation-readiness-v0
```

Issue packs convert a manifest into bounded work packets with inputs, expected artifacts, acceptance criteria, validation commands, and risk notes. They work locally and can also be copied into Linear, GitHub Issues, Jira, or a custom orchestrator.

Tracker handoff checklist:

- Preserve pack-local IDs and dependency fields.
- Copy validation commands and acceptance criteria into each tracker issue.
- Keep downstream issues in backlog until prerequisite checks pass.
- Post tracker-safe `validate --summary` fields as comments after substantive updates.
- Do not paste credentials, protected records, full result tables, or private paths into tracker issues.

Best for:

- splitting readiness, evidence, design, cost, and review work
- keeping most work in backlog while activating only the first wave
- making agent handoffs reproducible

## Safe Sharing Workflow

Before posting artifacts, opening a pull request, or switching a repository to public visibility:

```bash
make public-ready
```

Expected result:

- examples validate with `error_count == 0`
- local Markdown links resolve
- public-release scanner reports zero findings
- required gitleaks history and working-tree scans report no leaks
- generated artifacts preserve claim levels and non-claims

See [`PUBLIC_SECURITY_MODEL.md`](PUBLIC_SECURITY_MODEL.md) and [`RELEASE_READINESS_CHECKLIST.md`](RELEASE_READINESS_CHECKLIST.md).
