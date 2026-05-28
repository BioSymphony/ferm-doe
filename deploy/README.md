# Deployment scaffolding

The `biosymphony-ferm-doe` skill is runtime-agnostic. State lives in the
campaign manifest; every subcommand is short and stateless. This makes it a
clean fit for serverless deployment.

This directory ships two reference deployments:

| Path | Purpose | Compute footprint |
|---|---|---|
| [`aws-lambda/`](aws-lambda/) | Lightweight Lambda for stdlib subcommands behind API Gateway | ~50 MB image, ~200 ms cold start, 128 MB memory |
| [`modal/`](modal/) | Modal endpoint for BoTorch BO follow-up (CPU now, GPU-flag-ready) | ~1 GB image (torch + botorch), ~5 s cold start, scale-to-zero |

Both are *examples*, not production-ready stacks. They show the shape:
the same Python module serves laptop installs, AWS Lambda, and Modal/GPU
endpoints. The deployment surface changes, the code does not.

The examples default to a minimal public-safety posture:

- AWS API Gateway routes require an API key and include low default throttles.
- Modal requests require a runtime `FERM_DOE_API_TOKEN` supplied via a Modal secret.
- Runtime errors return generic public messages; detailed traces belong in provider logs.

Before any shared deployment, add site-specific auth, rate limits, request-size
limits, spend alarms, and logging retention rules.

## Deployment chooser

| Workflow | Use | Avoid |
|---|---|---|
| Local CLI | first run, CI, public demos, one-off planning | shared web API or multi-user queue |
| AWS Lambda | lightweight `validate`, `generate-design`, `analyze`, scale/cost/sampling helpers, and stdlib `plan-wave2` | filesystem scans, packet finalization, heavy BoTorch imports, or GPU work |
| Modal | `plan-wave2 --backend botorch`, optional GPU path, bursty heavy calls | low-latency stdlib commands that are cheaper locally or on Lambda |
| Custom platform | existing internal auth, state store, and observability | unreviewed multi-tenant public traffic |

The endpoint should not become the campaign brain. Keep durable state in an upstream store and treat cloud calls as bounded artifact tasks. See [`../docs/WORKFLOWS.md`](../docs/WORKFLOWS.md).

## Why two paths

The lightweight route family (`validate`, `generate-design`, `analyze`,
`scale-recipe`, `goals`, `assay-power`, `bridge-qualification`,
`sampling-plan`, `cost-rollup`, `doe-power`, `recommend-family`, and
stdlib `plan-wave2`) is small; each runs with zero heavy external
dependencies. AWS Lambda's free tier handles them at any realistic
scale. `audit` remains a local/CI filesystem scan, and packet
finalization stays on the local CLI unless you add a reviewed route for
your deployment.

The 14th subcommand, `plan-wave2 --backend botorch`, depends on
`torch + botorch + gpytorch` (~1 GB on disk, multi-second import). It
fits a different deployment shape:

- **CPU Modal endpoint** (default in this scaffolding); plenty for our
  workload (n ≤ 200 historical runs)
- **Modal with GPU flag**: flip `gpu="A10G"` when historical campaigns
  push n past ~1000
- **AWS container Lambda**: also works; needs provisioned concurrency
  to avoid 5-10 s cold starts on each call
- **GPU serverless providers**: same pattern as Modal; choose only after a
  provider-specific auth, budget, and cleanup review

The Modal scaffold ships as the canonical "heavy" path because it has
the cleanest GPU-flag flip and pay-per-second billing. Adapt for any
GPU cloud.

## Out of scope

- Production auth beyond the example API-key / runtime-token checks
- Multi-tenant rate limiting and request quotas
- Cost monitoring beyond provider-native billing dashboards
- Hot-reload during development (run `ferm-doe` locally; the whole
  stdlib path executes in milliseconds on a laptop)
