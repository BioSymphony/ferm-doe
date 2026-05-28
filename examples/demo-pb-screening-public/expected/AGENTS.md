# Agent handoff for `demo-pb-screening-public`

Closed-loop demo. Resume by running the steps in [`../README.md`](../README.md).

## State

- Profile: `screening`
- Checkpoint: 1 (planned)
- Family: Plackett-Burman, 8 runs, claim `exact`
- Readiness: `YELLOW` (assay qualification planned, synthetic results)
- Worst axis: none

## Open items

- Activity assay standard curve and matrix interference must be qualified before any physical execution.
- first-batch result rows in `inputs/wave1_results.csv` are synthetic public-safe placeholders; they exist so the analyze + plan-wave2 + finalize pipeline can be exercised end-to-end.

## Next step

Run `ferm-doe finalize examples/demo-pb-screening-public --out run_packet.md --results examples/demo-pb-screening-public/inputs/wave1_results.csv` to compose every available artifact into a single shippable run packet.
