# Visual Overview

## Tool Selection And Calling

![Tool knowledge informs the agent, which calls the CLI or a Python adapter and uses JSON or CSV results to choose its next call.](../assets/images/tool-use-loop.svg)

The [registry](TOOL_REGISTRY.md) records task fit and implementation status. The [adapter map](ADAPTER_MAP.md) identifies callable entry points. Your agent reads those references and controls the sequence. See the [Mermaid version](diagrams/agent-loop-public.mmd).

## Chaining Calls

![Campaign inputs feed design selection and generation; supplied results feed analysis and follow-up planning.](../assets/images/biosymphony-agent-loop.svg)

Commands share campaign inputs and result tables. The agent inspects each output before choosing the next call. Analysis JSON informs that review; the follow-up planner reads the supplied result rows directly. See the [README walkthrough](../README.md#planning-workflow).

## Scale Review

![Source and target conditions feed a comparison that identifies evidence gaps or produces a target-scale plan for review.](../assets/images/scale-bridge-review.svg)

The campaign declares criteria and tolerances. Record the evidence for each comparison; see the [scale-bridge framework](SCALE_BRIDGE.md).
