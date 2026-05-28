# Data Model

## Campaign Manifest

Required fields:

- `schema_version`
- `campaign_id`
- `name`
- `objective`
- `readiness_target`
- `sources`
- `inputs`
- `constraints`
- `responses`
- `factors`
- `artifacts`

## Campaign Arms

`campaign_arms` is a first-class campaign contract field for coupled designs where one objective spans multiple physical formats, such as plate scouting plus flask confirmation plus controlled bioreactor DOE. Do not encode those formats only as categorical factors in a single flat run table.

Recommended arm fields:

- `arm_id`
- `name`
- `purpose`
- `format`
- `run_budget`
- `scale`
- `factor_space_ref`
- `constraint_refs`
- `response_refs`
- `assay_policy_ref`
- `execution_capabilities`
- `bridge_role`
- `readiness_verdict`

Each arm owns executable factors, constraints, vessel limits, sampling limits, and response semantics. Cross-arm planning belongs in bridge artifacts such as `arm_bridge_policy.md`, `per_arm_projection_summary.json`, and `wave_result_handoff.md`.

The dossier contract should preserve arm identity in selected designs, run sheets, cost projections, aliasing reports, variance reports, and follow-up decision rules. A run table that mixes plate-only and bioreactor-only factors without an active arm projection is non-executable and should receive a RED or YELLOW limitation, not a silent flattening.

## Adaptive follow-up

Adaptive follow-up planning starts from executed result rows, not from the original design table alone. The canonical packet is written by `ferm-doe plan-wave2` and includes:

- `result_ingestion_report.json` for row counts, excluded/QC-failed/low-trust rows, and warnings
- `wave2_recommendation.json` for action, best usable run, bridge status, negative memory, and caveats
- `assay_power_results.json` for response-level assay power status
- `locked_prior_runs.csv` for usable prior rows carried into augmentation
- `augment_design.csv` for planned next rows when the action is not `pause`, `stop`, or global multi-arm planning
- `adaptive_trace.json` for deterministic orchestration steps
- `learning_ledger.csv` and `hiccup_review.md` for self-learning campaign memory

The default claim level is `planned_wave2_design`. It is not evidence of optimized conditions, validated assay detectability, or scale transfer.

## Self-Learning Ledger

`learning_ledger.csv` records planning hiccups and follow-up actions. Recommended columns:

- `learning_id`
- `campaign_id`
- `wave`
- `arm_id`
- `event_type`
- `severity`
- `source_artifact`
- `symptom`
- `root_cause_hypothesis`
- `design_implication`
- `assay_power_implication`
- `bridge_implication`
- `recommended_follow_up`
- `status`
- `owner`
- `follow_up_validation`
- `claim_boundary`

Learning events are campaign memory. They can change future plans, but they are not validation evidence until executed rows join and claim checks pass.

## Run Ledger

Recommended columns:

- `run_id`
- `source_run_id`
- `source_type`
- `organism`
- `product`
- `scale`
- factor columns with units in names
- response columns with units in names
- `assay_time_h`
- `inclusion_status`
- `qc_status`
- `trust_score`
- `arm_id` when the campaign has multiple physical arms
- `source_doi`
- `data_license`
- `transformation_notes`

## Reagent Inventory

Recommended columns:

- `reagent_id`
- `name`
- `category`
- `approx_available_amount`
- `unit`
- `purity_or_grade`
- `storage`
- `constraints`
- `notes`

## Equipment Capacity

Recommended columns:

- `equipment_id`
- `type`
- `count`
- `working_volume_min_ml`
- `working_volume_max_ml`
- `parallel_runs`
- `temperature_range_c`
- `controls_available`
- `notes`

## Trust Scores

Use a simple 0-1 score:

- `1.0`: source data directly extracted from an allowed source or validated lab system
- `0.8`: normalized source data with clear transformations
- `0.6`: usable but missing metadata
- `0.4`: inferred, approximate, or incomplete
- `0.0`: excluded from modeling
