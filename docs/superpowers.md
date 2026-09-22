# Tool And Planning Capabilities

BioSymphony Ferm DoE connects tool selection, design generation, result analysis, and follow-up planning through shared campaign files. Your agent reads the tool references and controls the calls.

| Capability | What to use | Output to inspect |
|---|---|---|
| Select a method | [Tool registry](TOOL_REGISTRY.md), [adapter map](ADAPTER_MAP.md), `recommend-family` | Task fit, dependency requirements, and design-family rationale |
| Generate experiments | `generate-design` | Factor settings and method metadata |
| Compare designs | `engine compare-designs` | Feasibility checks, design diagnostics, and selection reasons |
| Add a specialized optimizer | [Python and CLI adapter calls](ADAPTER_MAP.md) | Candidate rows, adapter status, and constraint coverage |
| Analyze results | `analyze` | Effect estimates, uncertainty, and model diagnostics |
| Plan another batch | `plan-wave2` | Next action, candidate rows, excluded results, and learning records |
| Compare scales | `scale-recipe`, `bridge-qualification` | Declared criteria, calculations, and evidence gaps |
| Estimate resources | `cost-rollup`, `sampling-plan` | Cost assumptions and proposed sampling schedule |

## Chain Tools Through Files

Keep factors, responses, and constraints in the campaign manifest. Generate a design, then supply result rows with run IDs and QC information. Analysis and follow-up tools read those rows; the agent reviews their reports before another call.

For specialized candidate generators, read the [adapter map](ADAPTER_MAP.md). Entry points differ by tool: some are CLI commands, others are Python functions. Install the selected extra, prepare its inputs, and inspect the returned status and candidates.

## Continue Across Sessions

Save the manifest, result tables, and planning outputs together. [Learning records](SELF_LEARNING_DOE.md) retain excluded results and reasons for pausing or changing the next batch. Another agent can use those files to continue the campaign.

For parallel work, [task contracts](CONTRACTS.md) and [issue packs](ISSUE_PACK_GENERATION.md) define bounded inputs and outputs. Model calls and dispatch belong to your chosen harness.
