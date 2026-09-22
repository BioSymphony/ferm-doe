# Follow-Up Candidates With BoTorch

The public CLI fits a Gaussian-process surrogate and optimizes a qEI or qUCB acquisition function. It returns candidate factor settings for a numeric search space.

## Prepare The Inputs

Use a manifest with supported numeric factors and a primary response. Prepare at least four usable observations. Review run IDs, exclusions, trust, and QC before passing the result CSV: this CLI branch passes rows directly to the adapter and does not run the stdlib ingestion checks.

The adapter uses factor bounds as its search space. It does not enforce additional process constraints; use an appropriate constrained adapter when those constraints determine feasibility. See the [adapter map](ADAPTER_MAP.md).

## Call The Tool

Install the extra in your checkout:

```bash
python -m pip install -e '.[botorch]'
```

Try the bundled synthetic results:

```bash
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/botorch \
  --backend botorch --acquisition qei --bo-n-candidates 3
```

`--bo-n-candidates` sets the candidate count. This branch does not apply `--remaining-budget`; set the count within your available budget. The CLI exposes `qei` and `qucb`. For explicit seed and optimizer settings, use `adapters.botorch_wave2.plan_bo_wave2` in Python.

## Read The Output

| File | Contents |
|---|---|
| `bo_wave2_plan.json` | Adapter report, model details or a short-circuit reason, and candidate records |
| `bo_wave2_design.csv` | Candidate rows, written when the report contains candidates |

The command returns after this adapter call. It does not also write the stdlib follow-up recommendation, learning records, or manifest patch. To obtain those artifacts, run the default `plan-wave2` workflow separately and compare the reports.

If the extra cannot be imported, the CLI exits with an error. Insufficient or unsupported inputs produce a short-circuit report. Inspect the report and candidate count before choosing another call; an exit status alone does not establish that candidates were generated.

Candidates carry `claim_level: bayesian_optimization_planned`. Review the model, factor coverage, and bounds before selecting experiments.
