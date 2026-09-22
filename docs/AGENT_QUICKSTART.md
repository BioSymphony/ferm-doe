# Agent Quickstart

Use an agent that can read campaign files and call the CLI or Python adapters. The [README walkthrough](../README.md#run-the-demo-with-your-agent) contains the prompt and runnable commands for this checkout.

## Select And Chain Tools

1. Read the [repository skill](../skills/biosymphony-ferm-doe/SKILL.md), [tool registry](tool-registry.json), and [adapter map](ADAPTER_MAP.md). Use `ferm-doe doctor` to inspect dependency availability.
2. Start with the synthetic screening demo. Check its inputs, select a design method, and inspect the generated candidates.
3. Analyze the bundled result rows and plan a follow-up batch. Read each report before choosing another call.
4. Report which tools ran, the candidate files they produced, and any unresolved input or method limits.

CLI commands and Python adapters have different inputs. Use the adapter map and each command's `--help`; a registry entry alone does not establish a callable integration.

## Use Your Own Campaign

Copy the [manifest template](../templates/campaign_manifest.template.json) into a separate campaign workspace. Fill in the objective, responses, factors, constraints, and input-table references. Keep private inputs and generated results in that workspace.

Save the campaign files and [learning records](SELF_LEARNING_DOE.md) so another session can continue. [Workflows](WORKFLOWS.md) describes optional task dispatch and tracker integration.
