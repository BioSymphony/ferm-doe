# Sidecar Architecture

## Purpose

Sidecars make a BioSymphony Ferm DoE campaign modular without moving orchestration outside the operator's chosen runner. A campaign can swap the goal, input pack, issue pack, or compute policy while keeping the same validation surface.

This is a planning-time readiness layer. Sidecars must not contain API keys, private strain data, customer batch records, unpublished sequences, confidential media formulations, or raw private process records.

## Swappable Slots

Each sidecar is a JSON document with `schema_version`, `sidecar_kind`, `id`, `name`, and the shared `biosymphony-ferm-doe.sidecar` interface block.

- `campaign_goal`: the objective, readiness target, stop policy, required inputs, expected artifacts, and data-safety rules.
- `input_pack`: the concrete public, synthetic, sanitized, or secure-store-referenced inputs for one campaign goal.
- `issue_pack`: the tracker issue set, dependencies, states, validation commands, and artifact expectations.
- `compute_policy`: the allowed local and provider-neutral compute profiles for a campaign.
- `provider_handoff`: the explicit contract a worker writes when provider mutation must be performed by an orchestrator or bridge service.

For coupled campaigns, sidecars preserve `campaign_arms` across goal, input, issue, and compute slots. Arm definitions are part of the engine and dossier contract, not an optional narrative appendix. Issue packs should assign separate lanes for arm contract, per-arm factor and constraint materialization, bridge policy, per-arm diagnostics, and dossier closeout so coupled plate, flask, and reactor work stays on separate tables.

The public templates live in:

```text
templates/sidecar-campaign-goal.json
templates/sidecar-input-pack.json
templates/sidecar-issue-pack.json
templates/sidecar-compute-policy.json
templates/sidecar-provider-handoff.json
```

## Composition Rule

Sidecars point to each other by stable refs:

```text
campaign_goal
  -> input_pack.campaign_goal_ref
  -> issue_pack.campaign_goal_ref + issue_pack.input_pack_ref
  -> compute_policy
  -> provider_handoff.campaign_goal_ref + input_pack_ref + issue_pack_ref + compute_policy_ref
```

The references are intentionally path-based for v1 so a worker can validate a local repo snapshot without network calls. A later tracker or artifact-store integration can map the same `id` fields to remote records.

## Validation

Use the stdlib validator before dispatching a sidecar bundle:

```bash
python3 skills/biosymphony-ferm-doe/scripts/sidecar_check.py \
  templates/sidecar-campaign-goal.json \
  templates/sidecar-input-pack.json \
  templates/sidecar-issue-pack.json \
  templates/sidecar-compute-policy.json \
  templates/sidecar-provider-handoff.json
```

The checker validates shape, required refs, readiness values, data classifications, issue validation commands, compute profiles, provider preflight, stage contracts, image-pull policy, fallback policy, and provider-handoff policy. It does not dereference paths or inspect private systems; that belongs in campaign-specific workers.

## Compute Boundary

The compute policy keeps the skill flexible while leaving cloud paths opt-in:

- `local-stdlib`: default path, no optional dependencies, suitable for workers and developer laptops.
- `local-extras`: allowed for users with NumPy, SciPy, BoFire, ENTMOOT, BoTorch, pyDOE3, SALib, or other adapter extras installed.
- `provider-neutral` cloud profiles: allowed as explicit adapters, and they must preserve the same validation, artifact, closeout, and tracker outcome contract.

Remote compute is off by default. A profile can describe a provider without granting launch permission.

## Provider Handoff Boundary

Paid provider mutation stays centralized. The worker validates and prepares; an orchestrator or trusted bridge creates resources, verifies artifacts, deletes resources, and posts closeout:

```text
tracker issue pack
  -> worker
  -> local validation
  -> optional remote launch bundle
  -> provider_handoff.json when paid mutation leaves the worker
  -> orchestrator or bridge create / verify / cleanup
  -> returned artifacts
  -> tracker outcome comment
```

A remote launch bundle (when one exists in the operator's private workspace) records the repo snapshot or commit, image or template, resource class, input pack ref, compute policy ref, expected outputs, validation commands, stop conditions, and closeout requirements. It should include:

- `provider_preflight`: image pull verification, actual container-state evidence, desired-status-as-intent handling, and max pending time.
- `stage_contract`: stage id, exact executable proof commands, expected outputs, timeout, heartbeat interval, progress ledger, done marker, resume command, and fail-closed behavior.
- `image_pull`: registry, visibility, digest pinning or accepted dev-smoke risk, and private registry auth reference when needed.
- `fallback_policy`: any fallback closes as degraded or partial; no silent fallback.
- `provider_handoff_policy`: worker-side provider reachability preflight, required artifact verification, required cleanup verification, and required tracker closeout.

Store secrets in a secure store and reference them by name. Tokens must stay out of sidecars.

A provider workload that has desired status `RUNNING` is intent, not proof. Closeout requires actual container state, workload progress ledger, done marker, and joined proof artifacts.

If a worker cannot resolve or reach the provider API, it emits `provider_handoff.json`, marks itself as validate / prepare only, and stops before paid mutation. A trusted orchestrator or bridge then handles create, verify, cleanup, post-cleanup prefix check, and the final tracker outcome.

## Minimal Adoption Path

1. Copy or adapt `templates/sidecar-campaign-goal.json` for the scientific goal.
2. Create an `input_pack` that references only public, synthetic, sanitized, or secure-store data.
3. Create an `issue_pack` from `templates/linear-issue.md`, keeping most work in Backlog and activating only the first readiness wave.
4. Select a compute profile, keeping `local-stdlib` as the default.
5. Add a `provider_handoff.json` when a bridge or orchestrator will perform remote mutation.
6. Run `sidecar_check.py`, `dossier_check.py`, and `ferm_doe_contract_self_check.py` before handoff.

Use `packs/issue-packs/campaign-arms-v1/` when the campaign requires first-class arm support before physical design selection.
