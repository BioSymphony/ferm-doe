# AWS Lambda deployment (lightweight, stdlib subcommands)

Reference deployment for the lightweight stdlib routes of
`biosymphony-ferm-doe`. Single dispatch Lambda behind API Gateway. The
heavy BoTorch path is in [`../modal/`](../modal/); filesystem audit and
packet finalization stay local/CI unless you add a reviewed route.

## Architecture

```
API Gateway (REST)
  - API key required on every route
  - default method throttles in the SAM template
  POST /v1/validate
  POST /v1/generate-design
  POST /v1/analyze
  POST /v1/scale-recipe
  POST /v1/goals
  POST /v1/assay-power
  POST /v1/doe-power
  POST /v1/recommend-family
  POST /v1/bridge-qualification
  POST /v1/sampling-plan
  POST /v1/cost-rollup
  POST /v1/plan-wave2
        │
        ▼
Lambda biosymphony-ferm-doe-light
  - Python 3.11, arm64, 256 MB, 60 s timeout
  - handlers.handler.handler dispatches by event['action']
  - Stdlib only; no torch / scipy / pyDOE3 in the image
```

## Request shape

```json
POST /v1/validate
{
  "action": "validate",
  "manifest": { ... campaign manifest ... },
  "args": {
    "summary": true
  }
}
```

For subcommands that consume first-batch results (`analyze`, `plan-wave2`):

```json
POST /v1/analyze
{
  "action": "analyze",
  "manifest": { ... },
  "results": [ { "design_run_id": "D1", "x1": 0.5, "y": 12.4 }, ... ],
  "args": { "seed": 0, "permutations": 1000, "alpha": 0.05 }
}
```

Response:

```json
{
  "statusCode": 200,
  "body": "{ ... result JSON ... }",
  "headers": { "Content-Type": "application/json" }
}
```

## Deploy

Prereqs: AWS CLI configured, `sam` (AWS SAM CLI) installed.

From repo root:

```bash
# Stage the source into the Lambda code directory
mkdir -p deploy/aws-lambda/biosymphony_ferm_doe
cp -r src/biosymphony_ferm_doe/* deploy/aws-lambda/biosymphony_ferm_doe/

cd deploy/aws-lambda
sam build
sam deploy --guided
```

The first `sam deploy --guided` prompts for stack name, region, and
confirms the IAM capabilities. After that, redeploys are
`sam deploy --no-confirm-changeset`.

After deployment, create and distribute an API key through your normal
secret-management channel. Do not commit keys, generated SAM outputs, or
request examples that include live credentials.

The repo ignores common generated deployment outputs such as `.aws-sam/`,
`samconfig*.toml`, and packaged templates. Keep any environment-specific
state, API keys, stack outputs, and packaged artifacts out of commits.

## Public scaffold hardening

- API Gateway requires an API key on every route.
- SAM method settings throttle requests by default.
- The handler rejects oversized request bodies and result lists.
- The handler validates top-level payload shapes before dispatch.
- Errors returned to callers avoid stack traces; stack traces stay in
  provider logs with the request id.

Before a shared endpoint, add a Lambda Authorizer, IAM auth, WAF rules,
spend alarms, CloudWatch retention policy, and tenant-specific logging
review.

## Cost profile

- **Lambda invocations:** Free tier covers 1M calls / month + 400,000
  GB-seconds. At our compute footprint (~50 ms × 256 MB per call) you
  fit hundreds of thousands of calls inside the free tier.
- **API Gateway:** Free tier covers 1M REST API calls / month. After
  that, ~$3.50 per million calls.
- **Data transfer:** Negligible; manifests are small JSON.

For a private internal deployment serving a single team, expect
**~$0/month** indefinitely. For a multi-tenant SaaS, scale linearly
with traffic; even 100k campaigns/month is well under $50.

## Out of scope

- Production identity: the template requires API keys, but production
  deployments should add a Lambda Authorizer, IAM auth, or another
  site-specific identity layer before serving end users
- Persistence: route long-lived state to S3 / DynamoDB explicitly;
  this Lambda is stateless
- Observability: hook CloudWatch Logs Insights queries when you scale
  past one team
- Spend alarms, WAF rules, and logging retention: add them before any shared or public endpoint

## Caveats

- The `audit` subcommand walks the local filesystem; it returns a stub
  in this Lambda. Run `ferm-doe audit` locally or in CI.
- Handler exceptions are logged privately with a request id; HTTP callers
  receive a generic `internal_error` response.
- The `plan-wave2` Lambda response embeds every follow-up artifact inline
  in the response body. API Gateway has a 6 MB body limit; for typical
  campaigns (n_runs < 50, k < 10) you are well under that. For larger
  campaigns, persist artifacts to S3 and return references.
- Cold start on the Light Lambda is ~200 ms with stdlib-only code. If
  you want sub-50 ms cold starts, attach provisioned concurrency.
