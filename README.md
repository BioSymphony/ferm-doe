# BioSymphony Ferm DoE

BioSymphony Ferm DoE is a toolkit for planning fermentation experiments with design of experiments (DoE). It produces design tables, measurement readiness reports, follow-up plans, and run packets.

![BioSymphony Ferm DoE banner](assets/images/biosymphony-ferm-doe-banner.png)

[![CI](https://github.com/BioSymphony/ferm-doe/actions/workflows/ci.yml/badge.svg)](https://github.com/BioSymphony/ferm-doe/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

Use the `ferm-doe` command line or a coding agent that can read files and run commands. A `campaign_manifest.json` records the objective, responses, factors, constraints, and evidence references so another person or agent can continue the work.

Outputs are planning artifacts for scientific review. Lab execution and experimental validation remain separate; see [scope and limitations](NON_CLAIMS.md).

## Start Here

In a cloned checkout, create a virtual environment and validate the synthetic screening demo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ferm-doe validate examples/demo-pb-screening-public --summary
```

Expected result: `error_count: 0` and `status: YELLOW`. The demo uses synthetic data to demonstrate planning checks.

Continue with the [agent demo prompt](#run-the-demo-with-your-agent) or the [manual CLI walkthrough](#drive-it-by-hand). For other tasks, choose a [use case](docs/USE_CASES.md). See [Install](#install) for clone commands and optional dependencies.

## Planning Workflow

![Six planning steps: define the campaign, check inputs, generate a design, analyze supplied results, plan a follow-up batch, and assemble a review packet.](assets/images/biosymphony-agent-loop.svg)

Resolve blocking errors before generating a design. Analysis uses supplied result rows; the demo bundles synthetic results. Lab execution happens separately. The `wave1` and `wave2` filenames identify the first batch and follow-up batch.

| Step | What you get | Command or file |
|---|---|---|
| Define the campaign | Objective, responses, factors, constraints, and source references | `campaign_manifest.json` |
| Check inputs | Errors, warnings, and checks that need attention | `validate --summary` |
| Generate a design | Factor settings for each proposed run | `generate-design` |
| Analyze results | Effect estimates, intervals, and model diagnostics | `analyze` |
| Plan the next batch | Recommended action, candidate rows, and manifest patch | `plan-wave2` |
| Assemble the packet | Markdown and JSON for scientific review | `finalize` |

## Planning Capabilities

| Planning task | Included support | Details |
|---|---|---|
| Choose experiments | Classical designs; optional constrained and Bayesian adapters | [Tool registry](docs/TOOL_REGISTRY.md) |
| Compare scales | Declared transfer criteria, assumptions, and evidence gaps | [Scale context](docs/SCALE_BRIDGE.md) |
| Review costs | Materials, operating costs, external benchmarks, and uncertainty | [Cost reporting](docs/COST_MODEL_REALISM_CHECK.md) |
| Continue a longer campaign | Bounded tasks, source references, and session handoffs | [Issue packs](docs/ISSUE_PACK_GENERATION.md) |

## Popular Use Cases

| You need to... | Start with |
|---|---|
| Learn the whole validate, design, analyze, follow-up batch, finalize loop | [`examples/demo-pb-screening-public/`](examples/demo-pb-screening-public/) |
| Turn validator warnings into an agent worklist | [`examples/demo-warnings-walkthrough-public/`](examples/demo-warnings-walkthrough-public/) |
| Check a scale-down or scale-up bridge before spending lab time | [`examples/demo-scale-bridge-public/`](examples/demo-scale-bridge-public/) |
| Handle hard-to-change fed-batch factors | [`examples/demo-split-plot-fedbatch-public/`](examples/demo-split-plot-fedbatch-public/) |
| Route constrained media planning through BoFire, ENTMOOT, OMLT, or BoTorch | [`docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) |
| Generate local issue packs for a longer agent run | [`docs/ISSUE_PACK_COOKBOOK.md`](docs/ISSUE_PACK_COOKBOOK.md) |
| Run a Linear-backed planning program or optional cloud endpoint | [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) |

See [`docs/USE_CASES.md`](docs/USE_CASES.md) for copy-paste agent requests and the recommended demo for each workflow.

## Agent Harnesses

Choose an agent integration or run the CLI directly. The repository includes configuration examples for these workflows:

| Harness | Use it when | Read |
|---|---|---|
| Claude Code, repo-local | You want one long-running session iterating on a manifest | [`agents/claude.md`](agents/claude.md) |
| Claude Code + Linear | You want status, ownership, blocked-state escalation, and tracker-safe readiness comments | [`agents/claude.md`](agents/claude.md) + [`agents/linear.md`](agents/linear.md) |
| Codex CLI or OpenAI Agents SDK | You prefer the OpenAI agent runtime, with or without Linear | [`agents/openai.yaml`](agents/openai.yaml) |
| Symphony or other long-horizon orchestrator | You want parallel sub-agents driven by a task queue and tracker | [`agents/generic.md`](agents/generic.md) + [`docs/ISSUE_PACK_COOKBOOK.md`](docs/ISSUE_PACK_COOKBOOK.md) |
| Cloud endpoint (AWS Lambda or Modal) | You want stateless planning commands behind an API | [`deploy/`](deploy/) |
| Hand-driven CLI | You want to drive `ferm-doe` yourself without an agent | [Drive it by hand](#drive-it-by-hand) |

See [Workflows](docs/WORKFLOWS.md) for state ownership and handoff conventions.

## When To Use This

Use this skill when a user, a Linear ticket, or an upstream agent asks you to plan one of the following, and the lab has not yet run the experiment:

- a fermentation or cell-culture screening DoE (microbial, yeast, mammalian, insect)
- a scale-up campaign from bench to pilot or pilot to manufacturing
- a scale-down qualification (build a small-scale model that recapitulates a larger scale)
- a fed-batch or perfusion campaign with hard-to-change setpoints (split-plot)
- a mixture or blend optimization (media composition, feed composition)
- a follow-up batch after a screening identifies active factors
- an assay-readiness review before any of the above

Skip this skill when the lab is mid-run and you need execution tooling (LIMS, ELN, robotics, real-time bioreactor control) or when you need a validated GxP batch-record system. See [`NON_CLAIMS.md`](NON_CLAIMS.md).

## Install

```bash
git clone https://github.com/BioSymphony/ferm-doe.git
cd ferm-doe
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
```

This installs the `ferm-doe` CLI that the agent calls. Optional scientific extras (BoFire, BoTorch, ENTMOOT, OMLT, TabPFN, pyDOE3, SALib, scipy) install separately when a campaign needs them; see [Optional extras](#optional-extras). Adapters degrade to a `not_available` report when the extra is missing, so the demos run on a clean install.

## Run The Demo With Your Agent

Open the checkout in your coding agent (Claude Code, Codex CLI, an OpenAI Agents SDK runner, or any orchestrator that can read files and run shell commands). Paste this prompt:

```text
You are working in the BioSymphony Ferm DoE public repo.

Use the repo-local skill at skills/biosymphony-ferm-doe/SKILL.md.
Keep all work local unless I explicitly ask for a different destination.
Use the fixtures in this checkout or data I provide in the local workspace.
Keep organization-specific inputs in a separate local workspace.

Start with examples/demo-pb-screening-public:
1. Run ferm-doe validate examples/demo-pb-screening-public --summary.
2. Explain the readiness status and failed_check_ids, if any.
3. Generate the first-batch design, analyze the bundled synthetic results, plan the follow-up batch with `plan-wave2`, and finalize a run packet under /tmp/demo-pb.
4. Keep claim levels visible in every generated artifact.
5. Before suggesting that anything is shareable, run `make public-ready`.
```

The demo writes disposable outputs under `/tmp/demo-pb/`. The [agent quickstart](docs/AGENT_QUICKSTART.md) lists the commands and expected artifacts.

When you are ready to plan your own campaign, ask the agent to copy `templates/campaign_manifest.template.json` and `templates/operator-intake.md` into a separate local workspace, fill them in, and run the same validate / design / analyze / plan-wave2 / finalize loop on the new campaign. Keep private or unpublished inputs out of this public checkout.

At closeout, ask the agent to write a campaign-local handoff at `artifacts/<campaign>/AGENTS.md` and to record hiccups, excluded results, and arm-scoped negative memory in the self-learning ledger and review files. The pattern is documented in [`docs/SELF_LEARNING_DOE.md`](docs/SELF_LEARNING_DOE.md). The artifacts are the portable memory across agent runtimes, so the next session (with the same agent or a different one) resumes from the same file.

## Drive It By Hand

You can also drive `ferm-doe` yourself without an agent. The same demo runs as:

```bash
ferm-doe validate examples/demo-pb-screening-public --summary
ferm-doe doctor
ferm-doe generate-design examples/demo-pb-screening-public \
  --out /tmp/demo-pb/wave1_design.csv --seed 0
ferm-doe analyze examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/wave1_analysis.json --seed 0
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2 --remaining-budget 3
ferm-doe finalize examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/run_packet.md --json-out /tmp/demo-pb/run_packet.json
```

See [CLI Commands](#cli-commands) for more examples. To check a contribution before sharing it, run:

```bash
make release-check
make doctor
make public-ready
```

`make release-check` runs the unit tests, validates every top-level public example with `error_count == 0`, checks the tool registry and adaptive-backend surface, and runs the public-release scanner over the public surface. `make public-ready` adds the required gitleaks history and working-tree secret scan. If `gitleaks` is missing, the public-ready gate fails closed.

## What `validate --summary` Looks Like

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-scale-bridge-public --summary
```

```json
{
  "campaign_id": "demo-scale-bridge-public",
  "claim_level": "public_synthetic_demo",
  "error_count": 0,
  "failed_check_ids": [],
  "non_claim": "This validation does not verify physical execution or assay results.",
  "profiles": ["scale_down_qualification"],
  "status": "YELLOW",
  "warning_count": 0,
  "worst_axis": null
}
```

Advisory gaps produce warnings such as these. Missing required fields and structural contradictions can produce blocking errors:

```json
{
  "status": "YELLOW",
  "error_count": 0,
  "warning_count": 8,
  "worst_axis": "general",
  "failed_check_ids": [
    "input-advised-equipment_inventory",
    "profile-advised-block-decision_rules",
    "assay-contract-incomplete_titer",
    "factor-mixture-media_blend",
    "doe-min-runs"
  ]
}
```

Read the full report for each failed check's severity. `failed_check_ids` can include advisory gaps as well as blocking errors.

| Readiness status | Meaning | Next planning step |
|---|---|---|
| RED | Blocking checks failed | Correct the listed inputs and rerun the checks |
| YELLOW | Guidance, incomplete evidence, or declared demo limits remain | Continue planning with those limits recorded |
| GREEN | The declared readiness checks are clear | Submit the plan for scientific review |

Readiness describes the recorded inputs and checks. Physical performance requires experimental evidence.

### Read The Claim Labels

Read `claim_level` with the artifact's method and provenance. Labels can describe design construction, analysis status, or synthetic inputs.

| Label examples | What they describe | What to review |
|---|---|---|
| `exact`, `adapter_backed`, `approximate`, `heuristic` | How a design was constructed | Method, factor bounds, constraints, and design diagnostics |
| `wave1_analysis_planned` | Analysis of supplied result rows | Result provenance, exclusions, and model assumptions |
| `planned_wave2_design`, `bayesian_optimization_planned` | A proposed follow-up batch | Recommended action, remaining budget, and constraints |
| `public_synthetic_demo` | Synthetic example data | Use as a contract fixture; obtain campaign-specific evidence before lab work |

Engine candidate records also include `exactness` and `planned_*_design` labels. Read the emitting command's metadata; see [design families](docs/DOE_FAMILIES.md) and [scope and limitations](NON_CLAIMS.md).

## Where This Project Fits

The toolkit keeps campaign inputs, planning checks, design candidates, and source references together across sessions. A notebook can inspect or extend the same outputs.

The engine's design comparison scores candidates against readiness, feasibility, and assay requirements. It returns the highest-scoring accepted candidate, or `no_accepted_design` when none passes. A separate critique informs the review and is excluded from design selection.

Cost reports distinguish estimates with different inputs and coverage:

| Cost basis | Includes | Evidence to record |
|---|---|---|
| Simulator estimate | Model-derived yield and cost | Model assumptions and fidelity |
| Materials | Reagents and quantities | Unit prices and their sources |
| Operating cost | Materials, labor, consumables, and overhead | Included work and allocation assumptions |
| Contract manufacturing benchmark | External manufacturing estimate | Scope, scale, and comparability |
| Uncertainty range | Variation in the preceding estimates | Bounds and the assumptions that change them |

Use the [cost reporting template](docs/COST_MODEL_REALISM_CHECK.md) to keep these bases explicit.

## Demos

Examples use synthetic data or documented public sources. Classical demos run with the base package. BoFire and ENTMOOT examples need their respective extras to generate backend candidates; without them, smoke scripts report `not_available`.

| Example | What to inspect |
|---|---|
| [Screening walkthrough](examples/demo-pb-screening-public/) | Design, analysis of bundled synthetic results, follow-up batch, and run packet |
| [Minimal campaign](examples/demo-xylanase-public/) | Manifest fields and measurement-readiness checks |
| [Guidance warnings](examples/demo-warnings-walkthrough-public/) | Intentionally incomplete inputs and the resulting worklist |
| [Scale bridge](examples/demo-scale-bridge-public/) | Declared source and target scales, transfer criterion, and evidence |
| [Fed-batch structure](examples/demo-split-plot-fedbatch-public/) | Hard-to-change factors and whole-plot groups |
| [Constrained media design](examples/demo-media-cost-bofire/) | BoFire design route with cost and total-mass constraints |
| [Multi-fidelity planning](examples/demo-shakeflask-to-2l-bofire/) | Historical inputs and BoFire scale-bridge routing |
| [Multi-arm campaign](examples/engine-multi-arm-scale-transfer-public/) | Separate arm designs and cross-arm bridge policy |
| [Custom design](examples/reference-doe-custom-design/) | Constrained design request and comparison artifacts |
| [Public-paper starter](examples/xylanase-wxz1-2012/) | Source references, normalized historical rows, and reuse notes |
| [Product-class starter](examples/yeast-isoprenoid-2l-fedbatch/) | Synthetic fed-batch planning inputs and derived responses |
| [Cardinality constraints](examples/entmoot-nchoosek-smoke/) | ENTMOOT v2 route for NChooseK Bayesian optimization |

## Design Maps

### Choose A Design Approach

| Campaign question | Starting approach | Check before choosing |
|---|---|---|
| Which factors matter? | Plackett–Burman or fractional factorial | Aliasing, factor count, and run budget |
| Is the response curved? | Central composite or Box–Behnken | Model terms, factor bounds, and center points |
| Do components form a blend? | Mixture design | Sum constraints and component limits |
| Are some settings hard to change? | Split-plot structure | Whole-plot groups and randomization |
| What should follow the first batch? | Sequential augmentation | Usable results and remaining budget |

Scale transfer is a campaign context that can accompany these designs. See [design recipes](docs/DOE_FAMILY_RECIPES.md) for supported generators and limits.

### Scale Transfer Criteria

![Scale review: record source and target conditions, compare declared criteria, resolve evidence gaps, and prepare a target-scale plan for review.](assets/images/scale-bridge-review.svg)

Choose criteria for the process, then record each criterion's source, target, tolerance, and evidence. Examples include oxygen transfer (`kLa`), power per volume (`P/V`), tip speed, and mixing time. An evidence gap remains a planning task until the required measurements or justification are supplied. See the [scale-bridge framework](docs/SCALE_BRIDGE.md).

## Architecture

The base CLI uses the Python standard library. Optional scientific dependencies run through explicit adapters; missing extras produce availability reports. The [tool registry](docs/TOOL_REGISTRY.md) separates implemented adapters from evaluation candidates.

| Component | Role | Entry point |
|---|---|---|
| Scientist or coding agent | Define the question, inspect reports, and revise inputs | [Repository skill](skills/biosymphony-ferm-doe/SKILL.md) |
| Campaign files | Preserve factors, responses, constraints, evidence references, and decisions | `campaign_manifest.json` and input tables |
| CLI and adapters | Validate inputs, generate designs, and analyze supplied results | [CLI reference](docs/CLI_REFERENCE.md) |
| Orchestrator, when used | Assign bounded tasks and collect reviewed artifacts | [Harness configurations](agents/) |

## Documentation

Start with the [documentation map](docs/README.md), [CLI reference](docs/CLI_REFERENCE.md), or [visual overview](docs/VISUAL_OVERVIEW.md).

<details>
<summary>Full documentation index</summary>

- [`docs/README.md`](docs/README.md): grouped documentation map
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md): short definitions of the terms a newcomer hits in the first ten minutes
- [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md): single-page index of every `ferm-doe` subcommand
- [`docs/ADAPTER_MAP.md`](docs/ADAPTER_MAP.md): capability-centric map of optional extras and their CLI surfaces
- [`examples/README.md`](examples/README.md): demo chooser and expected validation statuses
- [`docs/AGENT_QUICKSTART.md`](docs/AGENT_QUICKSTART.md): copy-paste prompt and first commands for coding agents
- [`docs/USE_CASES.md`](docs/USE_CASES.md): newcomer workflow chooser and example agent requests
- [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md): local, agent, Linear, issue-pack, and cloud-resource workflow map
- [`docs/ORCHESTRATOR_BOUNDARY.md`](docs/ORCHESTRATOR_BOUNDARY.md): what BioSymphony owns versus what an agent, tracker, or cloud runner owns
- [`docs/superpowers.md`](docs/superpowers.md): capability index and high-value planning moves
- [`docs/PUBLIC_ADOPTION_PATH.md`](docs/PUBLIC_ADOPTION_PATH.md): path from first clone to agent harness to handoff
- [`docs/PUBLIC_SECURITY_MODEL.md`](docs/PUBLIC_SECURITY_MODEL.md): local-first privacy, secret, scanner, and deployment boundaries
- [`docs/RELEASE_READINESS_CHECKLIST.md`](docs/RELEASE_READINESS_CHECKLIST.md): local public-switch checklist
- [`docs/ISSUE_PACK_COOKBOOK.md`](docs/ISSUE_PACK_COOKBOOK.md): local issue-pack commands for agent work graphs
- [`docs/ISSUE_PACK_GENERATION.md`](docs/ISSUE_PACK_GENERATION.md): end-to-end runbook for `engine generate-issue-pack` and orchestrator integration
- [`docs/diagrams/agent-loop-public.mmd`](docs/diagrams/agent-loop-public.mmd): Mermaid version of the planning workflow
- [`skills/biosymphony-ferm-doe/SKILL.md`](skills/biosymphony-ferm-doe/SKILL.md): long-agent loop, refuse-vs-warn rules
- [`docs/PROFILES.md`](docs/PROFILES.md): profile registry and composition
- [`docs/SCALE_BRIDGE.md`](docs/SCALE_BRIDGE.md): scale-bridge framework (criteria, bridge_factors, recapitulation)
- [`docs/SCALE_BRIDGE_METHODOLOGY.md`](docs/SCALE_BRIDGE_METHODOLOGY.md): entry conditions, sulfite kLa calibration, scale-down qualification protocol
- [`docs/DOE_FAMILIES.md`](docs/DOE_FAMILIES.md): supported design families
- [`docs/DOE_FAMILY_RECIPES.md`](docs/DOE_FAMILY_RECIPES.md): manifest-patch recipes for swapping `doe.family`
- [`docs/ADAPTIVE_WAVE2.md`](docs/ADAPTIVE_WAVE2.md): first-batch result ingestion, assay-power checks, and follow-up planning artifacts
- [`docs/WAVE2_BOTORCH.md`](docs/WAVE2_BOTORCH.md): follow-up planning walkthrough with the BoTorch backend (qEI / qUCB)
- [`docs/SELF_LEARNING_DOE.md`](docs/SELF_LEARNING_DOE.md): learning ledger, hiccup review, and arm-scoped negative memory runbook
- [`docs/TOOL_REGISTRY.md`](docs/TOOL_REGISTRY.md): curated BO/DoE and sidecar landscape with positioning and adapter status
- [`docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md): backend-selection surface for BoFire, BayBE, Ax/BoTorch, ENTMOOT, OMLT, and TabPFN
- [`docs/BOFIRE_POSITIONING.md`](docs/BOFIRE_POSITIONING.md): when to route to BoFire and when to stay on stdlib
- [`docs/BOFIRE_CONSTRAINT_PATTERNS.md`](docs/BOFIRE_CONSTRAINT_PATTERNS.md): linear, NChooseK, cardinality patterns, including the `SoboStrategy` + `NChooseK` trap
- [`docs/ENTMOOT_SWAP_DESIGN.md`](docs/ENTMOOT_SWAP_DESIGN.md): ENTMOOT v2 NChooseK adapter design and swap criteria
- [`docs/CONTRACTS.md`](docs/CONTRACTS.md): public task request and design-packet contract checks
- [`docs/SWARMS_AND_EVIDENCE.md`](docs/SWARMS_AND_EVIDENCE.md): source-tracking pattern for design rationale
- [`docs/dossier-generation.md`](docs/dossier-generation.md): how the planning packet is assembled and checked
- [`docs/COST_MODEL_REALISM_CHECK.md`](docs/COST_MODEL_REALISM_CHECK.md): cost assumptions, operating costs, and uncertainty ranges
- [`docs/OPEN_DATA_PUBLICATION_STRATEGY.md`](docs/OPEN_DATA_PUBLICATION_STRATEGY.md): how a campaign artifact set maps to a publishable open-data drop
- [`docs/SIMULATOR_V2_SPEC.md`](docs/SIMULATOR_V2_SPEC.md): simulator v2 spec (SPEC ONLY; not yet implemented)
- [`docs/AGENT_HARNESSES.md`](docs/AGENT_HARNESSES.md): Claude Code, OpenAI Agents SDK, Codex CLI, Linear-aware runners, generic harnesses
- [`schemas/campaign_manifest.schema.json`](schemas/campaign_manifest.schema.json): JSON Schema for the manifest
- [`schemas/task_request.schema.json`](schemas/task_request.schema.json): JSON Schema for bounded agent task requests
- [`schemas/engine_task_request.schema.json`](schemas/engine_task_request.schema.json): JSON Schema for the richer engine task router
- [`schemas/tables/`](schemas/tables/): Frictionless-compatible table contracts (run ledger, evidence, equipment, reagent, design, results)
- [`NON_CLAIMS.md`](NON_CLAIMS.md): scope and boundary statements
- [`CHANGELOG.md`](CHANGELOG.md): release history
- [`CONTRIBUTING.md`](CONTRIBUTING.md): how to add profiles, families, demos
- [`agents/`](agents/): runtime-specific agent configs (Claude, OpenAI, generic, Linear)

</details>

## Agent Harness Integration

A coding agent reads the [repository skill](skills/biosymphony-ferm-doe/SKILL.md), runs CLI commands, and saves campaign files between sessions. Use the [harness configurations](agents/) to connect an orchestrator or tracker.

For multi-agent campaigns, an orchestrator assigns bounded tasks and integrates their artifacts into one review packet.

![An orchestrator defines tasks and dependencies, workers return scoped artifacts, and an integrator assembles a packet for human review.](assets/images/agent-work-packets.svg)

The full runbook is in [`docs/ISSUE_PACK_GENERATION.md`](docs/ISSUE_PACK_GENERATION.md); pack chooser and copy-paste recipes live in [`docs/ISSUE_PACK_COOKBOOK.md`](docs/ISSUE_PACK_COOKBOOK.md).

## CLI Commands

A single-page index of every `ferm-doe` subcommand, grouped by lifecycle stage, is at [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md). Expand the examples for individual planning steps.

<details>
<summary>CLI examples</summary>

```bash
# short summary instead of the full check list
ferm-doe validate examples/demo-scale-bridge-public --summary

# write JSON to a file instead of stdout (good for agent pipes)
ferm-doe validate examples/demo-scale-bridge-public --out /tmp/result.json

# validate a bounded agent task request
ferm-doe validate-task-request templates/task_request.template.json

# route a richer engine task request
ferm-doe engine route-task-request templates/engine_task_request.template.json

# check the compact public design-packet contract surface
ferm-doe check-dossier examples/demo-xylanase-public

# evaluate response-level assay-power assumptions
ferm-doe assay-power examples/demo-xylanase-public

# recommend a DoE family from the manifest
ferm-doe recommend-family examples/demo-xylanase-public

# generate the first-batch design from the manifest's `doe.family`
ferm-doe generate-design examples/demo-xylanase-public \
  --out /tmp/wave1_design.csv \
  --metadata-out /tmp/wave1_design.metadata.json \
  --seed 0

# derive an engineering recipe at to_scale (RPM, sparge, agitator power, kLa)
ferm-doe scale-recipe examples/demo-scale-bridge-public \
  --out /tmp/scale_recipe.json \
  --md-out /tmp/scale_recipe.md

# formulate Derringer-Suich desirability goals from responses and decision_rules
ferm-doe goals examples/demo-xylanase-public --out /tmp/goals.json

# design-level power analysis (per-coefficient MDE)
ferm-doe doe-power examples/demo-xylanase-public --sigma 0.5

# sampling schedule for fed-batch / perfusion runs
ferm-doe sampling-plan examples/demo-scale-bridge-public \
  --out /tmp/sampling.csv \
  --md-out /tmp/sampling.md

# cost / resource rollup against operator-declared unit costs
ferm-doe cost-rollup examples/demo-xylanase-public --out /tmp/cost.json

# fit OLS to first-batch results: effect estimates, permutation p-values, lack-of-fit
ferm-doe analyze examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/analysis.json \
  --md-out /tmp/analysis.md \
  --seed 0

# compose every available artifact into one review-ready planning packet in Markdown
ferm-doe finalize examples/demo-pb-screening-public \
  --out /tmp/run_packet.md \
  --json-out /tmp/run_packet.json \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv

# plan the follow-up batch from first-batch result rows (stdlib closed-loop)
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir wave2_public_plan \
  --remaining-budget 3

# plan the follow-up batch with BoTorch (Gaussian-process surrogate + acquisition)
# Full walkthrough: docs/WAVE2_BOTORCH.md
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir wave2_bo_plan \
  --backend botorch \
  --acquisition qei \
  --bo-n-candidates 6

# full local engine commands live behind the engine subcommand
ferm-doe engine compile-state \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/ferm-doe-state
ferm-doe engine compile-dossier \
  --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json \
  --out /tmp/ferm-doe-dossier \
  --run-budget 16
ferm-doe engine utility check-deps

# audit-skip marker on a line names the specific release rule to ignore
# api_key=PLACEHOLDER_NEVER_COMMIT  # audit-skip: assigned_secret_like_value documentation example
```

</details>

## Optional Extras

The base package runs the classical demos. Install an extra in your cloned checkout when you need its adapter, for example:

```bash
python -m pip install -e '.[botorch]'
```

Replace `botorch` with an extra from the table. Missing dependencies produce an availability report; some commands provide a separate stdlib fallback. See the [adapter map](docs/ADAPTER_MAP.md) for command-specific behavior and the [backend findings](docs/BACKEND_EVAL_FINDINGS.md) for tested limits.

| Extra | Adds |
|---|---|
| `scipy` | Student-t p-values in `analyze` and t-quantiles in `doe-power` |
| `pydoe3` | Larger Box–Behnken designs and maximin Latin hypercube sampling |
| `botorch` | Gaussian-process Bayesian follow-up through `plan-wave2` |
| `bofire` | Constrained design and Bayesian or multi-fidelity planning routes |
| `entmoot` | ENTMOOT v2 Bayesian planning with NChooseK cardinality constraints |
| `omlt` | Mixed-integer surrogate planning with linear and NChooseK constraints |
| `tabpfn` | Foundation-model surrogate for low-data comparisons; model access required |
| `backend-eval` | BayBE and Ax imports for comparison fixtures |
| `sensitivity` | SALib sensitivity analysis on result rows |
| `report` | Plotly figures in the BoFire HTML report |
| `contracts` | Frictionless validation of table contracts |

The supported BoFire adapter has a documented `SoboStrategy` + `NChooseK` limit. Use the [ENTMOOT or OMLT routing guidance](docs/ENTMOOT_SWAP_DESIGN.md) when Bayesian follow-up requires cardinality constraints. Registry candidates do not imply implemented adapters.

## FAQ

**Q. Does this generate DoE designs?**
A. Yes. `ferm-doe generate-design` emits a first-batch design CSV directly from the campaign manifest, stdlib only, no external generator required. Supported families and claim levels: `full_factorial`, `fractional_factorial`, `plackett_burman` (n in {8, 12, 16, 20, 24}), `definitive_screening` (k in {3..6, 9, 10}), `central_composite` (face-centered, rotatable, orthogonal), `box_behnken` (k in {3, 4}), `latin_hypercube`, and `scheffe_mixture` are emitted at `claim_level: exact`. `optimal_d`, `optimal_i`, and `extreme_vertices_mixture` use coordinate exchange or constraint enumeration and are labeled `heuristic`; review with a statistician before expensive runs. Follow-up candidate rows come from `ferm-doe plan-wave2` under `claim_level: planned_wave2_design`. The generated design CSV and metadata include claim labels for review.

**Q. Does this adapt after the first batch?**
A. Yes, in planning mode. `ferm-doe plan-wave2` joins trusted, QC-passing result rows, evaluates assay-power policy, writes negative memory and learning artifacts, and recommends `confirm`, `narrow`, `expand`, `pause`, `stop`, or a bridge-gated `scale_or_downscale` plan for the next experiment round. With `--backend botorch`, it routes through a Gaussian-process surrogate and an acquisition function (qEI or qUCB) for `n_candidates` follow-up points. Outputs are labeled `planned_wave2_design` or `bayesian_optimization_planned`, not validated optimization. The next action depends on the supplied results and campaign policy.

| Recommended action | Planning purpose |
|---|---|
| `confirm` | Check a candidate with additional runs |
| `narrow` | Concentrate the next design around a promising region |
| `expand` | Explore beyond the current design's coverage, within declared bounds |
| `pause` | Resolve data, assay, arm-scope, or policy gaps |
| `stop` | Record why another batch is not recommended |
| `scale_or_downscale` | Propose next-arm candidates after bridge eligibility checks |

The recommendation records its reason and evidence. These actions describe planning outputs; they do not schedule or execute experiments.

**Q. When do I route to BoFire vs the stdlib path?**
A. See [`docs/BOFIRE_POSITIONING.md`](docs/BOFIRE_POSITIONING.md). Short version: stdlib for unconstrained or simple-box screening and adaptive follow-up planning; BoFire for linear or nonlinear constraint blends (cost, total-mass, NChooseK) and for multi-fidelity scale-bridge planning. The BoFire adapter degrades to a "not_available" report when the extra is absent, so smoke scripts run on any laptop.

**Q. When do I route to ENTMOOT instead of BoFire?**
A. When Bayesian follow-up must enforce NChooseK cardinality constraints. The repository's BoFire 0.3.1 audit found that `SoboStrategy` plus `NChooseK` did not return candidates. Upstream issue #450 is now closed, but later BoFire releases have not been evaluated against this adapter. ENTMOOT and OMLT remain the conservative MIP-backed routes. See [`docs/ENTMOOT_SWAP_DESIGN.md`](docs/ENTMOOT_SWAP_DESIGN.md).

**Q. What about BayBE, Ax, OMLT, and TabPFN?**
A. They are optional evaluation routes that keep the campaign manifest as the source of state. See [`docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md). BoFire remains the default constrained static DoE/BO route. BayBE is a low-data and hybrid-space comparison target; Ax/BoTorch is for custom modeling or trial lifecycle pilots; OMLT is a MIP-surrogate route for hard constraints; TabPFN is a token-gated low-data surrogate experiment.

**Q. Why is the verdict YELLOW for the demos?**
A. The demos use synthetic placeholder data with `readiness_expectation: YELLOW`. The verdict reflects that the demos are pre-experiment plans on synthetic inputs; the schema carries that readiness caveat through to anything consuming the manifest. The diagnostic walkthrough demo additionally exercises the validator's guidance path.

**Q. Can I use this for mammalian cell culture, not just microbial fermentation?**
A. Yes. The schema is organism-agnostic. Scale-bridge criteria like P/V and tip speed are common for shear-sensitive mammalian work; kLa is more common for microbial. See [`docs/SCALE_BRIDGE.md`](docs/SCALE_BRIDGE.md).

**Q. How is this different from a Jupyter notebook with pyDOE3?**
A. The toolkit adds a campaign manifest, input and measurement checks, source references, follow-up planning, and handoff files around design generation. You can use a notebook to inspect or extend those outputs.

**Q. Is the skill stateful or stateless?**
A. The skill itself is stateless. State lives in the campaign manifest file. The agent that uses the skill is responsible for persisting and updating that file across turns.

**Q. Does this work without an agent?**
A. Yes. The CLI runs standalone, and a scientist can call `ferm-doe validate`, `generate-design`, `analyze`, `plan-wave2`, and `finalize` directly. The repo is designed around agent harnesses because that is where multi-turn campaign state, parallel sub-agent dispatch, and cross-session handoff actually pay off, but the individual commands are useful on their own.

**Q. What about GxP / regulatory contexts?**
A. GxP batch records require a separately-validated execution pipeline. This tool covers the planning step that feeds one. See [`NON_CLAIMS.md`](NON_CLAIMS.md).

**Q. Can I use private data with this skill?**
A. Yes. Keep private campaigns in a separate non-public workspace and do not commit them here. `claim_level` is a provenance label, not a sanitization control; scanners, release checks, and secret checks still apply before anything is shared.

**Q. What does "long-running agent" mean concretely?**
A. An agent session that spans hours or days, accumulates context, may pause and resume, and may hand off to other agents or humans. Examples: a Claude Code session driving a multi-week design effort; a Codex worker that tracks a Linear project; a custom orchestrator running between waves.

## Status

Pre-alpha (`0.1.0a0`). Validators report advisory gaps as warnings and missing required inputs, structural contradictions, or public-safety violations as errors. Run `validate --summary` after campaign edits; use the full report to investigate failed checks.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Public-safe synthetic demos are welcome; do not include private process data in this repo.

## License

[MIT](LICENSE).

## Related Work

- [Garcia-Ochoa & Gomez 2009](https://doi.org/10.1016/j.biotechadv.2008.10.006): kLa review (cited in the scale-bridge demo)
- [Junker 2004](https://doi.org/10.1263/jbb.97.347): scale-up review
- [Jones & Nachtsheim 2011](https://www.tandfonline.com/doi/abs/10.1080/00224065.2011.11917841): Definitive Screening Designs
- [Jones & Nachtsheim 2009](https://doi.org/10.1080/00224065.2009.11917782): split-plot guidance
- [Studier 2005](https://doi.org/10.1016/j.pep.2005.01.016): lactose autoinduction

## Topics

`fermentation` `bioprocess` `biomanufacturing` `bioreactor` `cell-culture` `fed-batch` `perfusion` `design-of-experiments` `experimental-design` `doe` `bayesian-optimization` `optimization` `scale-up` `scale-down` `kla` `python` `biosafety` `agentic-ai` `ai-agents` `claude-code`
