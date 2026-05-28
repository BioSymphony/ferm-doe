# Modal endpoint for BoTorch BO follow-up

Reference deployment for the heavy `plan-wave2 --backend botorch` path.
The lightweight stdlib subcommands live on AWS Lambda
([`../aws-lambda/`](../aws-lambda/)); this scaffold handles only the
GPU-flag-ready BoTorch endpoint.

## Why Modal (and not Lambda)

The BoTorch adapter pulls `torch + botorch + gpytorch` (~1 GB on disk,
multi-second import). On AWS Lambda this means container Lambda with
provisioned concurrency to avoid 5-10 s cold starts on every call.
Modal's strengths line up better:

- **Pay per second** with scale-to-zero between calls
- **Single GPU flag** flip (`gpu="A10G"` / `gpu="A100-40GB"`) when
  historical campaign portfolios outgrow CPU
- **Image rebuild on deploy** so dependency upgrades are one command
- **Web endpoint generation** as a `@modal.web_endpoint` decorator,
  with no API Gateway plumbing

The same pattern can be adapted to another GPU serverless provider after
provider-specific auth, spend limits, and cleanup behavior are reviewed.

## Deploy

Prereqs: Modal account + `modal` CLI installed and authenticated.

```bash
pip install modal
modal token new  # auth once
modal deploy deploy/modal/app.py
```

Modal will print the public webhook URL. Before sending traffic, create a
Modal secret named `biosymphony-ferm-doe-api` containing `FERM_DOE_API_TOKEN`.
Send that token with `Authorization: Bearer <runtime token>`. Do not commit
the token or paste a live token into examples.

## Request shape

```json
POST https://your-app--biosymphony-ferm-doe-bo-plan-bo-wave2-endpoint.modal.run
Authorization: Bearer <runtime token>
{
  "manifest": { ... campaign manifest ... },
  "results": [
    { "design_run_id": "D1", "x1": 0.5, "x2": 0.3, "y": 12.4 },
    ...
  ],
  "args": {
    "n_candidates": 3,
    "acquisition": "qei",
    "seed": 0
  }
}
```

Response is the dict returned by `botorch_wave2.plan_bo_wave2(...)`:

```json
{
  "claim_level": "bayesian_optimization_planned",
  "non_claim": "...",
  "primary_response_id": "y",
  "direction": "maximize",
  "acquisition": "qei",
  "n_observations": 16,
  "n_factors": 5,
  "n_candidates": 3,
  "candidate_design": [
    {
      "design_run_id": "BO-001",
      "claim_level": "bayesian_optimization_planned",
      "scoring_mode": "bayesian_optimization",
      "x1": 7.42,
      "x2": 4.18,
      ...
    },
    ...
  ],
  "best_observed_response": 28.4,
  "gp_posterior_at_best": { "mean": 27.1, "variance": 0.8 }
}
```

## Switch CPU → GPU

The default function uses CPU (`cpu=2, memory=4096`). For CPU, GP fits
of n ≤ 200 historical runs complete in seconds. Above that, flip the
GPU flag in `app.py`:

```python
@app.function(image=image, gpu="A10G", memory=8192, timeout=300)
```

`A10G` is a good balance for our workload size (~$0.60/hr, ~$0.0001 per
short call). `A100-40GB` only matters when n_factors and n_candidates
both grow past 50, which is overkill for typical fermentation campaigns.

## Cost profile (Modal)

- **CPU function:** ~$0.000131 per CPU-second; a typical BO call is 1-3
  CPU-seconds, so ~$0.0003 per invocation
- **GPU function (A10G):** ~$0.000167 per GPU-second active; warm calls
  finish in <1 s, cold starts ~10 s for the first call after idle
- **Egress:** included; manifests and result payloads are small JSON

Realistic budget: a 10-campaign-per-day team using BO follow-up spends
**under $10/month** on this endpoint.

## Public scaffold hardening

The endpoint rejects missing bearer auth with HTTP 401, uses constant-time
token comparison, rejects oversized request bodies, bounds result-row count,
and caps candidate/restart/raw-sample knobs. Keep these limits in place unless
you have a tenant-specific spend and rate-limit policy.

The example image pins dependency ranges and the package version used by this
pre-alpha public scaffold. When cutting a release, update
`biosymphony-ferm-doe[botorch]==...` in `app.py` at the same time as the tag.

## Out of scope

- Production identity: this scaffold checks a single bearer token from a
  provider secret. Use provider-managed identity, upstream auth, or per-tenant
  routing before serving end users.
- Multi-tenant routing: one Modal app per customer is the cleanest split
  if you go SaaS
- Result persistence: the function returns the result JSON directly; if
  the caller wants to store it, that lives upstream
- Spend alarms, external rate limits, and logging-retention policy
