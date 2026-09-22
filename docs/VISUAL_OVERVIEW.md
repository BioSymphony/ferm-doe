# Visual Overview

The README contains three diagrams for the planning workflow, scale review, and bounded agent work. Each SVG is editable text with a title and description for accessibility.

## Planning Workflow

![Define the campaign, check inputs, generate a design, analyze supplied results, plan a follow-up batch, and assemble a review packet.](../assets/images/biosymphony-agent-loop.svg)

Analysis requires supplied result rows. The screening demo uses synthetic results. See the [agent quickstart](AGENT_QUICKSTART.md) for commands and expected outputs, or the [Mermaid version](diagrams/agent-loop-public.mmd) for a text-rendered flowchart.

## Scale Review

![Record source and target conditions, compare declared criteria, and resolve gaps or prepare a target-scale plan for review.](../assets/images/scale-bridge-review.svg)

The campaign declares its criteria and tolerances. Record the evidence for each comparison; see the [scale-bridge framework](SCALE_BRIDGE.md). Scale transfer is a campaign context, while a DoE family defines the design structure. The [design recipes](DOE_FAMILY_RECIPES.md) describe supported choices.

## Bounded Agent Work

![An orchestrator defines tasks, workers return scoped artifacts, and an integrator checks and assembles a packet for human review.](../assets/images/agent-work-packets.svg)

The orchestrator owns dispatch and dependencies. The toolkit supplies task contracts and artifact checks. See the [issue-pack runbook](ISSUE_PACK_GENERATION.md).
