# Adaptive Follow-Up Planning

Adaptive follow-up planning turns completed first-batch result rows into auditable next-step artifacts. The stable CLI and file identifiers still use `wave2` (`ferm-doe plan-wave2`, `planned_wave2_design`) because they are part of the repo contract. That label means "the next planning checkpoint after first-batch results," not a predetermined second experiment. Outputs are deliberately conservative: `planned_wave2_design`, not optimized, validated, production-ready, or scale-transfer proven.

## What It Does

`ferm-doe plan-wave2` reads:

- `campaign_manifest.json`
- a first-batch results CSV
- optional selected-design CSV presence check

It writes:

- `adaptive_wave2_plan.json`
- `result_ingestion_report.json`
- `assay_power_results.json`
- `wave2_recommendation.json`
- `wave2_recommendation.md`
- `locked_prior_runs.csv`
- `augment_design.csv`
- `adaptive_trace.json`
- `negative_result_memory.json`
- `learning_ledger.csv`
- `hiccup_review.md`
- `wave2_manifest.patch.json`
- `bofire_strategy_report.json` when the BoFire routing rule fires

## Recommendation Actions

The public planner can recommend the next action:

- `confirm`: repeat or confirm a modest winner.
- `narrow`: plan local candidate rows near a strong non-boundary winner.
- `expand`: the best row is on a factor boundary, so factor-space review comes before local narrowing.
- `pause`: results are missing, low-trust, nonnumeric, cross-arm pooled without an active arm, or bridge eligibility blocks the requested move.
- `stop`: the primary response is flat enough that more runs may not be useful under the current objective.
- `scale_or_downscale`: only when explicitly requested and bridge eligibility passes. This still means planning next-arm candidates, not validated transfer.

## Result CSV Shape

Minimum columns:

```csv
design_run_id,arm_id,qc_status,inclusion_status,trust_score,primary_response
R001,plate,pass,include,0.95,12.4
```

Recommended columns:

- `design_run_id` or `run_id`
- `arm_id`
- `qc_status`
- `inclusion_status`
- `trust_score`
- one column per measured response
- factor columns from the selected design, when available

Rows with failed QC, explicit exclusion, or trust score below `0.6` do not drive recommendations.

## Manifest Slot

```json
{
  "adaptive_wave2": {
    "claim_level": "planned_wave2_design",
    "primary_response_id": "product_titer_g_l",
    "active_arm_id": "shake_flask",
    "allowed_actions": ["confirm", "narrow", "expand", "pause", "stop"],
    "require_assay_power": true,
    "self_learning": {
      "enabled": true,
      "learning_ledger_path": "wave2/learning_ledger.csv",
      "hiccup_review_path": "wave2/hiccup_review.md",
      "negative_memory_scope": "arm"
    }
  }
}
```

Use `active_arm_id` when multiple arms are present. Without it, the planner will not pool incompatible plate, flask, and reactor rows into one narrowing decision.

## Optional BoFire Route

`plan-wave2` can route through `adapters/bofire_strategy.py` when the campaign declares non-box constraints, multiple optimized responses, scale fidelity, or `--backend bofire`.

BoFire remains optional. If `bofire[optimization]` is missing, or if the adapter cannot safely translate a declared constraint, the packet records `bofire_strategy_report.json` and falls back to the stdlib augmentation path. BoFire-backed rows keep the same `planned_wave2_design` claim boundary.

## CLI

```bash
ferm-doe assay-power examples/demo-xylanase-public

ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir wave2_public_plan \
  --selected-design examples/demo-pb-screening-public/expected/selected_wave_1_design.csv \
  --remaining-budget 3
```

## Non-Claims

The public planner does not:

- generate commercial-grade optimal designs
- validate assay data
- validate scale transfer
- approve lab execution
- replace statistical review
- write GxP batch records

It creates a deterministic planning packet so an agent or scientist can review the next move without losing the evidence trail.
