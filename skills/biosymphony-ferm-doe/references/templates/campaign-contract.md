# Campaign Contract

## Summary

<One or two sentences describing the upstream process goal and the physical experiment packet to produce.>

## Objective

- Primary objective: <maximize/minimize/diagnose/validate>
- Secondary objectives: <robustness, cost, viability, productivity, purity, time>
- Stop policy: <confidence target, budget exhaustion, plateau, readiness blocker>

## Inputs

- Historical data: <paths, source systems, or none>
- Reagent inventory: <path or approximate list>
- Equipment capacity: <path or approximate list>
- Assay method: <description and readiness status>
- Prior knowledge: <papers, protocols, failed campaigns, operator notes>

## Responses

- `<response>` - <unit, assay method, acceptable range, decision threshold>

## Candidate Factors

- `<factor>` - <unit, allowed range, fixed/default value, constraints>

## Constraints

- Run budget:
- Checkpoint count:
- Max duration:
- Available vessels:
- Sampling limits:
- Forbidden combinations:
- Safety/process limits:

## Readiness Verdict Criteria

- [ ] Objective and response variables are unambiguous.
- [ ] Factor ranges are feasible and safe.
- [ ] Assay can detect expected differences.
- [ ] Reagent and equipment constraints are sufficient for first-batch.
- [ ] Result capture template is defined before physical setup.
- [ ] follow-up decision rules are pre-registered.

## Required Artifacts

- `campaign_manifest.json`
- `historical_run_ledger.csv`
- `data_trust_report.md`
- `factor_space.yaml`
- `assay_readiness_report.md`
- `feasibility_report.md`
- `selected_wave_1_design.csv`
- `run_sheet.md`
- `result_capture_template.csv`
- `wave_2_decision_rules.md`
- `provenance.md`
