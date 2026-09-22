# BioSymphony Ferm DoE

BioSymphony Ferm DoE gives scientists and AI agents tools to choose experiments, compare designs, analyze results, and plan the next batch. It combines design of experiments (DoE), optional optimization adapters, and a tool knowledge base that explains when to use each method.

![BioSymphony Ferm DoE banner](assets/images/biosymphony-ferm-doe-banner.png)

[![CI](https://github.com/BioSymphony/ferm-doe/actions/workflows/ci.yml/badge.svg)](https://github.com/BioSymphony/ferm-doe/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

Your agent reads the repository skill, selects a tool, calls the CLI or a Python adapter, and inspects the returned JSON or CSV before choosing the next call. A shared `campaign_manifest.json` carries the objective, factors, responses, and constraints across those calls.

## What You Can Do

| Task | Tools and knowledge included | Result |
|---|---|---|
| Choose an experimental design | Family recommendations, classical generators, and candidate comparison | Run settings, design diagnostics, and selection reasons |
| Use specialized optimizers | BoTorch, BoFire, ENTMOOT, OMLT, and TabPFN adapters | Candidate experiments with method and availability reports |
| Learn from supplied results | Regression, assay-power checks, and sequential planning | Effect estimates, follow-up candidates, and reasons to continue or pause |
| Compare process scales | Scale criteria, engineering calculations, and bridge checks | Declared transfer conditions and evidence gaps |
| Connect the work across sessions | Shared campaign files, result tables, and learning records | Inputs and decisions that another agent can reuse |

Outputs are plans for scientific review. Lab execution and experimental validation remain separate; see [scope and limitations](NON_CLAIMS.md).

## Tool Knowledge Base

The [tool registry](docs/TOOL_REGISTRY.md) and its [machine-readable JSON](docs/tool-registry.json) describe 54 tools and research candidates. Entries record use cases, routing reasons, package requirements, source links, checked dates, and limitations. The [adapter map](docs/ADAPTER_MAP.md) gives the actual call surfaces.

![An agent reads tool knowledge, selects and calls a tool, then uses its JSON or CSV result to choose the next call.](assets/images/tool-use-loop.svg)

| Read or run | What it tells your agent |
|---|---|
| [Repository skill](skills/biosymphony-ferm-doe/SKILL.md) | How to frame the campaign and use the planning tools |
| [Tool registry](docs/tool-registry.json) | Which tools fit the task and which are implemented, evaluation candidates, or watchlist entries |
| [Adapter map](docs/ADAPTER_MAP.md) | How to call each implemented adapter and interpret its output |
| `ferm-doe doctor` | Repository configuration and dependency availability |
| [Design recipes](docs/DOE_FAMILY_RECIPES.md) | How factor types, constraints, and run budgets affect design choice |

The registry is a reference your agent reads. Tools marked `evaluate_next` or `watch`, including Docling, PaperQA2, and GOLLuM, are research candidates. Their presence does not install or connect them.

## Planning Workflow

Chain calls through campaign files and inspect each result before continuing. Your agent controls the sequence; the tools return files it can read, compare, and reuse.

![Campaign inputs feed design tools. Supplied result rows feed analysis and follow-up planning, producing the next candidate batch.](assets/images/biosymphony-agent-loop.svg)

| Call | Read before the next call |
|---|---|
| `validate` → `recommend-family` | Input errors, proposed family, and its rationale |
| `generate-design` | Design CSV, method metadata, and factor bounds |
| `analyze --results …` | Effect estimates, uncertainty, and model diagnostics |
| `plan-wave2 --results …` | Recommendation, candidate rows, excluded results, and manifest patch |

`analyze` and `plan-wave2` each read the supplied result CSV and campaign manifest. The analysis JSON helps your agent assess the plan; it is not a required planner input. The demo includes synthetic results, so you can try the chain without running a lab experiment.

## Start Here

### Install

```bash
git clone https://github.com/BioSymphony/ferm-doe.git
cd ferm-doe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ferm-doe doctor
```

The base package uses the Python standard library. Add scientific dependencies when you need their adapters; see [Optional Extras](#optional-extras).

### Run The Demo With Your Agent

Open the checkout in an agent that can read files and run commands. Paste:

```text
Read skills/biosymphony-ferm-doe/SKILL.md, docs/tool-registry.json,
and docs/ADAPTER_MAP.md. Run ferm-doe doctor.

Use examples/demo-pb-screening-public and write outputs under /tmp/demo-pb.
Validate the inputs, explain the design-family recommendation, and generate
a design. Analyze the bundled synthetic results, then plan a follow-up batch
with a remaining run budget of 3. Inspect each output before the next call.

Explain which tools ran, why they fit, what the results support, and which
inputs need attention. Keep the fixtures unchanged and all outputs local.
```

### Drive It By Hand

The same tool chain runs in a shell:

```bash
ferm-doe validate examples/demo-pb-screening-public --summary
ferm-doe recommend-family examples/demo-pb-screening-public
ferm-doe generate-design examples/demo-pb-screening-public \
  --out /tmp/demo-pb/wave1_design.csv \
  --metadata-out /tmp/demo-pb/wave1_design.metadata.json --seed 0
ferm-doe analyze examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/wave1_analysis.json --seed 0
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2 --remaining-budget 3
```

Validation returns `error_count: 0` and `status: YELLOW` for this synthetic demo. Inspect `wave2/wave2_recommendation.json` for the next action and `wave2/augment_design.csv` for candidate runs. Resolve blocking errors before generating a design.

## Choose A Tool

| Need | Callable route | Key condition |
|---|---|---|
| Classical screening, response surfaces, or mixtures | `generate-design` | Choose the family in the manifest; inspect method labels |
| Compare candidate designs | `engine compare-designs` | Review feasibility, model diagnostics, and selection reasons |
| Gaussian-process Bayesian candidates | `plan-wave2 --backend botorch` | Numeric factors, prepared results, and the `botorch` extra |
| Constrained or multi-fidelity candidates | BoFire Python adapter | Translate supported constraints and inspect the route report |
| Cardinality constraints, such as choosing at most three components | ENTMOOT or OMLT Python adapter | Compatible solver and supported constraint forms |
| Foundation-model surrogate candidates | TabPFN Python adapter | Optional dependencies and model access |
| Sensitivity analysis | SALib Python adapter | Inputs appropriate for the selected sensitivity method |

The [adapter map](docs/ADAPTER_MAP.md) links the Python entry points. BoFire, ENTMOOT, OMLT, and TabPFN are callable modules; the public follow-up CLI does not dispatch them automatically. The BoTorch CLI emits a separate candidate report; its [walkthrough](docs/WAVE2_BOTORCH.md) explains preparation and outputs.

## Optional Extras

Install only the adapters you plan to call, for example:

```bash
python -m pip install -e '.[bofire]'
```

| Extra | Adds |
|---|---|
| `botorch` | Gaussian-process models and acquisition functions |
| `bofire` | Constrained and multi-fidelity candidate generation |
| `entmoot`, `omlt` | Solver-backed surrogate optimization |
| `tabpfn` | Foundation-model surrogate; model access required |
| `scipy`, `pydoe3` | Additional statistics and classical design methods |
| `sensitivity` | SALib sensitivity analysis |
| `report`, `contracts` | Plotly reports and Frictionless table checks |

Availability and execution are separate. Inspect the returned adapter status, candidate count, and issues; a package can be installed without running on a particular call. The supported BoFire adapter has a documented Bayesian `NChooseK` limit; see [ENTMOOT and OMLT guidance](docs/ENTMOOT_SWAP_DESIGN.md).

## Demos

| Try | What you learn |
|---|---|
| [Screening walkthrough](examples/demo-pb-screening-public/) | Connect design, result analysis, and follow-up planning |
| [Constrained media design](examples/demo-media-cost-bofire/) | Call BoFire on synthetic constraint examples |
| [Cardinality constraints](examples/entmoot-nchoosek-smoke/) | Evaluate the ENTMOOT adapter |
| [Multi-arm campaign](examples/engine-multi-arm-scale-transfer-public/) | Keep designs and results scoped to each campaign arm |
| [Scale bridge](examples/demo-scale-bridge-public/) | Compare declared source and target conditions |
| [Custom design](examples/reference-doe-custom-design/) | Inspect candidate comparisons and design diagnostics |

See the [use-case guide](docs/USE_CASES.md) for other starting points. Examples use synthetic data or documented public sources. Keep your own campaign inputs in a separate workspace.

## Agent Harness Integration

Use any agent that can read files and call the CLI or Python. Your harness owns model calls and task dispatch. For parallel work, [task contracts and issue packs](docs/ISSUE_PACK_GENERATION.md) define inputs, outputs, and dependencies. Linear and OpenAI Symphony are optional orchestration choices; see [harness configurations](agents/) and [workflows](docs/WORKFLOWS.md).

## Documentation

| Topic | Read |
|---|---|
| Tools and methods | [Registry](docs/TOOL_REGISTRY.md), [adapter map](docs/ADAPTER_MAP.md), [capability index](docs/superpowers.md) |
| Commands and examples | [CLI reference](docs/CLI_REFERENCE.md), [agent quickstart](docs/AGENT_QUICKSTART.md) |
| Visual guides | [Tool use and workflow](docs/VISUAL_OVERVIEW.md), [Mermaid workflow](docs/diagrams/agent-loop-public.mmd) |
| Planning details | [Design recipes](docs/DOE_FAMILY_RECIPES.md), [scale criteria](docs/SCALE_BRIDGE.md), [cost estimates](docs/COST_MODEL_REALISM_CHECK.md) |
| Continuing a campaign | [Learning records](docs/SELF_LEARNING_DOE.md), [task contracts](docs/CONTRACTS.md) |
| Sharing work | [Security model](docs/PUBLIC_SECURITY_MODEL.md), [release checklist](docs/RELEASE_READINESS_CHECKLIST.md) |

The [documentation map](docs/README.md) includes reporting, deployment, and extended workflow references.

## Status

Pre-alpha (`0.1.0a0`). Review method labels, constraint coverage, and data quality before using candidate experiments. See [scope and limitations](NON_CLAIMS.md).

## Contributing

See [Contributing](CONTRIBUTING.md). Run `make release-check` for tests, example validation, and release checks. Before public sharing, `make public-ready` also scans the history and working tree for secrets.

## License

[MIT](LICENSE).
