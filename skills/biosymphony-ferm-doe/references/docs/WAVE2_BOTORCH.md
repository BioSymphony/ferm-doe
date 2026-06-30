# Follow-Up Planning With BoTorch

Walkthrough of `ferm-doe plan-wave2 --backend botorch` against the existing `demo-pb-screening-public` fixture. The command name is stable, but the concept is follow-up planning after first-batch results, not a predetermined second experiment. For the conceptual model, see [`ADAPTIVE_WAVE2.md`](ADAPTIVE_WAVE2.md).

## What BoTorch adds to the closed loop

The default `plan-wave2 --backend stdlib` path computes a model-informed augmentation: it identifies active factors via the OLS analysis, applies tighter narrowing steps biased along the per-factor ascent direction, and emits `confirm`, `narrow`, `expand`, `pause`, `stop`, or `scale_or_downscale`.

The `--backend botorch` path fits a Gaussian-process surrogate over first-batch result rows and optimizes an acquisition function over the unit hypercube of coded factor values. It writes follow-up candidate rows labeled `claim_level: bayesian_optimization_planned` alongside the standard closed-loop artifacts. Useful when:

- First-batch evidence is dense enough for a GP fit (n >= 4 usable observations).
- Factor space is numeric and continuous (categorical and hard-to-change factors are not in scope for this backend).
- You want to explore-vs-exploit explicitly with an acquisition function rather than the deterministic ascent heuristic.

The BoTorch route does not replace the stdlib analysis. Both run; the BoTorch candidates are an additional artifact, and the orchestrator can choose which to ship.

## Install

```bash
pip install "biosymphony-ferm-doe[botorch]"
```

The extra installs `torch`, `botorch`, and `gpytorch`. The adapter is import-safe: if the extra is missing, `plan-wave2 --backend botorch` short-circuits with reason `not_available` and the stdlib path still runs.

## Run

```bash
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2_botorch \
  --backend botorch \
  --acquisition qei \
  --bo-n-candidates 6 \
  --remaining-budget 3
```

Flags:

- `--backend botorch` selects the BoTorch route. Default is `stdlib`.
- `--acquisition qei | qucb`. `qei` is q-batch Expected Improvement (standard BO baseline). `qucb` is q-batch Upper Confidence Bound; tunable explore vs exploit. Default `qei`.
- `--bo-n-candidates N` is the next-batch size. Default 3.
- `--remaining-budget N` constrains how many of the BO candidates the planner can recommend within the campaign's remaining run budget.

`--seed` is honored if you want reproducible candidate selection.

## What gets written

The output directory contains the standard follow-up packet plus the BoTorch-specific artifacts:

- `wave2_recommendation.json` and `wave2_recommendation.md`
- `adaptive_wave2_plan.json`
- `result_ingestion_report.json`
- `assay_power_results.json`
- `locked_prior_runs.csv`
- `augment_design.csv` (BoTorch candidate rows, labeled `bayesian_optimization_planned`)
- `botorch_strategy_report.json` (GP fit summary, acquisition function, restart count, raw-sample count, short-circuit reason if the adapter fell through)
- `adaptive_trace.json`
- `negative_result_memory.json`
- `learning_ledger.csv`
- `hiccup_review.md`
- `wave2_manifest.patch.json`

The `botorch_strategy_report.json` is the key artifact for review: it records which factors were modeled, the acquisition function used, the candidate coordinates in coded space, and the back-transform to manifest factor units.

## How to interpret the candidates

Each candidate row in `augment_design.csv` carries:

- `claim_level: bayesian_optimization_planned`
- the factor values in manifest units
- `acquisition_value` (the EI or UCB score at that point)
- `scoring_mode: bayesian_optimization`

A high `acquisition_value` means the GP posterior thinks that point has high expected improvement (qEI) or high upper confidence (qUCB). It does not mean the response is guaranteed to be higher there. A statistician should review the candidates against the campaign's decision rules, assay-power policy, and cost ceiling before any rows are committed to the lab.

## When the adapter short-circuits

The BoTorch adapter writes a `short_circuit_reason` and an empty candidate list when:

- `not_available`: `torch` / `botorch` / `gpytorch` imports failed. Install the `botorch` extra.
- `no_numeric_factors_for_bo`: the manifest has no numeric or ordinal factors with declared `low` and `high`. BoTorch needs numeric bounds.
- `no_primary_response_declared`: the manifest does not declare `objective.response_id`.
- `insufficient_observations_for_{rid}`: first-batch results CSV has fewer than 4 usable rows for the primary response after QC and inclusion filtering.
- `only_{n}_observations_need_at_least_4_for_bo`: same boundary, different phrasing for n < 4.
- `unsupported_acquisition_{name}`: passed `--acquisition` is not `qei` or `qucb`.

When BoTorch short-circuits, the stdlib closed-loop path still produces a full follow-up packet. The short-circuit reason is recorded in `botorch_strategy_report.json` for the orchestrator to surface.

## Backend choice

| Situation | Backend |
|---|---|
| First-batch evidence is small (n < 4 usable), categorical-heavy, or split-plot | `stdlib` |
| First-batch evidence is dense, numeric factors only, you want explicit explore/exploit | `botorch` with `qei` |
| Same as above but you want more exploration | `botorch` with `qucb` |
| Constraints are linear, mixture, or NChooseK | `bofire` (routes through `adapters/bofire_strategy.py`; see [`BOFIRE_POSITIONING.md`](BOFIRE_POSITIONING.md)) |
| NChooseK cardinality is load-bearing in the BO loop | `entmoot` (see [`ENTMOOT_SWAP_DESIGN.md`](ENTMOOT_SWAP_DESIGN.md)) |

The stdlib path is the default because it runs on a clean install, handles every campaign shape, and labels its outputs honestly. The BoTorch path is the right choice when you want GP-based BO and the manifest can support it.

## Non-claims

BoTorch candidates are planned BO output, not validated optimization. The GP posterior is only as good as the first-batch data used to fit it. A statistician should review the acquisition-function choice and the GP fit before driving expensive runs. See [`../NON_CLAIMS.md`](../NON_CLAIMS.md).
