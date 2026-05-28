# Demo: Diagnostic Warnings Walkthrough

A deliberately-underspecified manifest. The other three public demos validate cleanly (0 errors, 0 warnings, YELLOW from `readiness_expectation`); this one is here to **show what the validator actually does when it has guidance to give**.

Profile: `screening`. Verdict: `YELLOW`. `warning_count > 0` is the point.

What this demo intentionally surfaces:

- assay contract incomplete: assayed response declared without `assay_method`, `standard_curve`, or `matrix_effects_policy`
- mixture factor declared without `components`
- DoE family `definitive_screening` declared with `n_runs` below the family minimum
- profile-advised blocks `decision_rules` and `stop_rules` absent
- public-safety advised inputs `equipment_inventory` and `reagent_inventory` not provided

Run:

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary
```

Look at `failed_check_ids`. Each id maps to a validator branch, useful for a long-running agent to inspect *before* producing a similar shape in a real campaign.
