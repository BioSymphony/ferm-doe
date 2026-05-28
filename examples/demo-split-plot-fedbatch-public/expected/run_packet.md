# Demo Run Packet: Split-Plot Fed-Batch

This is a public-safe placeholder run packet for the split-plot fed-batch demo.

## Claim Level

`public_synthetic_demo`

This packet is not a physical-execution instruction set.

## Split-Plot Structure

- Whole-plot factors (hard-to-change): temperature_c, do_setpoint_pct
- Sub-plot factors (easy-to-change): carbon_concentration_g_per_l, nitrogen_concentration_g_per_l, trace_element_blend
- Whole-plot replication: each whole-plot combination is run in duplicate. Whole-plot variance is estimated from these replicates.

## Design Rows

See `selected_wave_1_design.csv`. Sixteen rows across four whole-plot combinations and four sub-plot combinations. `whole_plot_id` is preserved; randomization is required at execution time **within** each whole-plot, not across whole-plots.

## Stop Conditions

- Whole-plot replicate variance > 5x sub-plot variance → pause; the split-plot structure is unstable for the chosen whole-plot factors.

## Resume Path

See `AGENTS.md`.
