# `demo-split-plot-fedbatch-public`: split-plot fed-batch

Public-safe BioSymphony Ferm DoE demo for a fed-batch campaign with a split-plot design. Profile: `split_plot_fed_batch`.

## What this demo shows

- **Hard-to-change whole-plot factors**: temperature, DO setpoint. These are expensive to change run-to-run because they cascade through the controller.
- **Easy-to-change sub-plot factors**: carbon, nitrogen, trace blend. These can vary inside a whole-plot block.
- **Whole-plot annotation**: the validator checks for the `hard_to_change: true` annotation on whole-plot factors and warns when absent.
- **Two-level error structure** that a downstream statistician (or `ferm-doe analyze` with the split-plot path) needs to honor.

## First command

```bash
ferm-doe validate examples/demo-split-plot-fedbatch-public --summary
```

Then drive the rest of the loop:

```bash
ferm-doe recommend-family examples/demo-split-plot-fedbatch-public
ferm-doe generate-design examples/demo-split-plot-fedbatch-public \
  --out /tmp/demo-spp/wave1_design.csv --seed 0
ferm-doe sampling-plan examples/demo-split-plot-fedbatch-public \
  --out /tmp/demo-spp/sampling.csv --md-out /tmp/demo-spp/sampling.md
```

## What you should see

- **`validate --summary`**: status `YELLOW`, `error_count == 0`. Titer assay readiness is `planned`, not executed; whole-plot variance is unknown until first replication.
- **`recommend-family`**: surfaces `split_plot` as the top recommendation, with rationale that calls out the hard-to-change factors.
- **`generate-design`**: writes a design CSV with a `whole_plot_id` column so the run order honors the split-plot block structure.
- **`sampling-plan`**: schedules samples for the fed-batch profile across whole-plot blocks.

## Non-claims

Synthetic public-safe demo. The verdict stays `YELLOW` until the lab attaches executed assay rows and a whole-plot variance estimate. See [`../../NON_CLAIMS.md`](../../NON_CLAIMS.md).
