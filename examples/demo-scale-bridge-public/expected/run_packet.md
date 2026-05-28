# Demo Run Packet: Scale-Bridge (Pilot 50 L → Bench 2 L)

This is a public-safe placeholder run packet for the downscale qualification demo.

## Claim Level

`public_synthetic_demo`

This packet is not a physical-execution instruction set. It illustrates the artifact shape expected from BioSymphony Ferm DoE for a downscale qualification campaign.

## Scale Bridge

- Direction: scale_down (pilot 50 L → bench 2 L)
- Primary criterion: kLa (matched at 250 1/h)
- Secondary criteria: P/V, mix_time
- Bridge factors needing retuning at bench: stir_rpm_bench, feed_rate_ml_per_h
- Recapitulation criterion: composite score (titer ratio + OUR shape distance) ≥ 0.85

## Measurement Readiness Caveat

Titer and OUR pipelines must be qualified at both scales before physical execution. Bench-side kLa-vs-RPM curve must be measured before first batch starts; otherwise the design's stir_rpm range is unfounded.

## Design Rows

See `selected_wave_1_design.csv`. Eleven rows covering one center and one-at-a-time excursions across five factors at the bench arm. Definitive Screening pattern; randomization is required at execution time.

## Stop Conditions

- Bench kLa outside ±10% of pilot reference target → pause, escalate to process engineering.
- Titer assay linearity not established → pause, escalate to analytics.

## Resume Path

If the campaign is paused, see `AGENTS.md` for the resume order.
