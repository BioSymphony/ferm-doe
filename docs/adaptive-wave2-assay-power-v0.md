# Adaptive follow-up + Assay Power V0

`adaptive-wave2-assay-power-v0` turns completed first-batch rows into a planned follow-up packet only after the rows join the declared design, pass trust/QC filters, preserve arm scope, satisfy bridge policy, and clear response-level assay-power checks.

## Contract

Main command:

```bash
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2 \
  --selected-design examples/demo-pb-screening-public/expected/selected_wave_1_design.csv \
  --remaining-budget 3
```

Standalone assay check:

```bash
ferm-doe assay-power examples/demo-pb-screening-public
```

Required follow-up artifacts:

- `adaptive_wave2_plan.json`
- `result_ingestion_report.json`
- `wave2_recommendation.json` and `wave2_recommendation.md`
- `locked_prior_runs.csv`
- `augment_design.csv`
- `adaptive_trace.json`
- `learning_ledger.csv`
- `hiccup_review.md`
- `negative_result_memory.json`
- `wave2_manifest.patch.json`
- `assay_power_results.json` and `assay_power_report.md`
- `bofire_strategy_report.json` when the optional BoFire route fires

Claim level defaults to `planned_wave2_design`. The packet may recommend `confirm`, `narrow`, `expand`, `pause`, `stop`, or `scale_or_downscale`, but it must not claim optimized conditions, validated assay detectability, production readiness, or scale-transfer success.

## Response Policy

Assayed responses can declare `assay_power_policy` with:

- `minimum_detectable_effect`
- `expected_effect_size`
- `noise_sd` or `cv_percent`
- `replicate_count`
- `target_power`
- `lod`, `loq`
- `dynamic_range`
- `matrix_recovery_min`
- `turnaround_h`

Derived metrics such as cost, duration, and calculated productivity remain `NOT_APPLICABLE` for assay power instead of receiving invented assay requirements.

## Adaptive Rules

- QC-failed, excluded, and low-trust rows do not drive recommendations.
- Negative-result memory records the arm and factor snapshot that produced a poor result.
- Multi-arm result ledgers cannot globally narrow a mixed factor space; they require per-arm follow-up planning.
- `scale_or_downscale` is blocked unless bridge eligibility passes.
- Weak primary-response assay power pauses fitted or confirmatory follow-up claims.
- BoFire can propose candidates only for routed constrained, multi-objective, or scale-fidelity cases; missing or untranslated optional dependencies fall back to stdlib planning with a route report.

## Self-Learning Setup

Every `plan-wave2` packet writes a learning surface:

- `learning_ledger.csv` records join, QC, trust, assay-power, bridge, pause/stop, and arm-scope hiccups with source artifact, severity, follow-up, and claim boundary.
- `hiccup_review.md` summarizes those events for the operator and future agents.
- `wave2_manifest.patch.json` carries the deterministic design-policy patch proposal.

If a hiccup is broadly reusable, promote it to a dated `logs/YYYY-MM-DD-<campaign>-learnings-review.md` note and link it from `artifacts/<campaign>/AGENTS.md`. See `docs/self-learning-doe-runbook.md`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.test_adaptive_wave2_assay_power -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
