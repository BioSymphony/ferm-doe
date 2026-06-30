# Use Cases

Pick the closest job-to-be-done, run the suggested demo, then let your agent adapt the manifest to your real planning question in a separate local workspace.

First adaptation step:

```bash
mkdir -p /tmp/my-ferm-campaign/inputs /tmp/my-ferm-campaign/expected
cp templates/campaign_manifest.template.json /tmp/my-ferm-campaign/campaign_manifest.json
cp templates/operator-intake.md /tmp/my-ferm-campaign/operator-intake.md
ferm-doe validate /tmp/my-ferm-campaign --summary
```

Replace template placeholders before using the output for decisions, and keep private or unpublished inputs out of this public checkout.

| I want to... | Start with | Why it helps |
|---|---|---|
| Learn the full loop in under ten minutes | [`../examples/demo-pb-screening-public/`](../examples/demo-pb-screening-public/) | Validates, generates a Plackett-Burman design, analyzes bundled synthetic results, plans follow-up, and finalizes a packet. |
| Check whether my campaign is underspecified | [`../examples/demo-warnings-walkthrough-public/`](../examples/demo-warnings-walkthrough-public/) | Shows how validator warnings become an agent worklist instead of vague review comments. |
| Plan a simple enzyme-production screen | [`../examples/demo-xylanase-public/`](../examples/demo-xylanase-public/) | Small manifest with source-tracked evidence and assay-readiness gates. |
| Build a scale-down qualification plan | [`../examples/demo-scale-bridge-public/`](../examples/demo-scale-bridge-public/) | Exercises kLa, P/V, tip speed, OUR, and recapitulation criteria before design generation. |
| Work with hard-to-change fed-batch factors | [`../examples/demo-split-plot-fedbatch-public/`](../examples/demo-split-plot-fedbatch-public/) | Keeps whole-plot and subplot factors explicit so the design does not pretend every factor is equally easy to vary. |
| Route constrained media optimization through BoFire | [`../examples/demo-media-cost-bofire/`](../examples/demo-media-cost-bofire/) | Demonstrates linear cost and total-mass constraints with clean fallback behavior when optional extras are missing. |
| Explore NChooseK Bayesian optimization | [`../examples/entmoot-nchoosek-smoke/`](../examples/entmoot-nchoosek-smoke/) | Shows the ENTMOOT route for cardinality-heavy BO, where the BoFire route has a documented trap. |
| Compare adaptive backends | [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) | Frames BoFire, BayBE, Ax/BoTorch, ENTMOOT, OMLT, and TabPFN as routable backends behind the same readiness gates. |
| Generate local issue packs for a larger agent run | [`ISSUE_PACK_COOKBOOK.md`](ISSUE_PACK_COOKBOOK.md) | Turns one manifest into bounded local work packets without requiring a cloud orchestrator. |
| Run a Linear-backed planning program | [`../agents/linear.md`](../agents/linear.md) | Maps issues, sub-issues, comments, statuses, and labels to campaign state and readiness verdicts. |
| Serve validation or follow-up planning through cloud resources | [`WORKFLOWS.md`](WORKFLOWS.md) | Shows when to stay local, when to use AWS Lambda, and when the Modal BoTorch endpoint is the better fit. |
| Prepare an example for sharing | [`PUBLIC_SECURITY_MODEL.md`](PUBLIC_SECURITY_MODEL.md) | Shows the release checks and artifact boundaries to run after the useful work is done. |

## Example Agent Requests

Use these as starting prompts for a coding agent that can read the repo and run shell commands.

```text
Use skills/biosymphony-ferm-doe/SKILL.md. Run the demo-pb-screening-public closed loop, explain each artifact, and tell me what would need to change before adapting this to my own campaign.
```

```text
Use skills/biosymphony-ferm-doe/SKILL.md. Inspect my local campaign manifest, run ferm-doe validate --summary, and turn failed_check_ids into a prioritized edit plan. Do not generate a design until structural blockers are gone.
```

```text
Use skills/biosymphony-ferm-doe/SKILL.md. Compare BoFire, ENTMOOT, OMLT, and the stdlib path for this manifest. Keep readiness gates as the decision authority, and write the route recommendation into a short markdown note.
```

```text
Use skills/biosymphony-ferm-doe/SKILL.md. Build a scale-bridge readiness report from my local manifest and equipment tables. If the bridge conditions are not met, return RED with the specific missing measurements.
```

```text
Use skills/biosymphony-ferm-doe/SKILL.md and agents/linear.md. Treat my Linear issue as one campaign, post only tracker-safe validate --summary fields as a comment after each substantive update, and create sub-issues only for follow-up or bounded issue-pack work.
```

```text
Use docs/WORKFLOWS.md. Tell me whether this campaign should stay local, use the AWS Lambda scaffold, or use the Modal BoTorch endpoint. Keep state outside the endpoint and list the auth, rate-limit, spend, and logging controls needed before sharing it.
```

## Good Public Demos Look Like This

- Synthetic or public-source rows only.
- Explicit `claim_level` and `readiness_expectation` fields.
- A manifest that validates with `error_count == 0`.
- A short README that names the first command and expected status.
- Generated artifacts under `expected/` when they are useful for comparison.
- No credentials, workstation paths, customer records, or exact proprietary recipes.

## What This Repo Is Not

It is not a LIMS, ELN, robotics controller, GxP batch-record system, or real-time bioreactor control layer. It is the pre-experiment planning and readiness layer that helps decide whether the next design is worth review.
