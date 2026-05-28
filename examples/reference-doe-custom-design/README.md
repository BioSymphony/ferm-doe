# `reference-doe-custom-design`: custom-constrained design fixture

A 4-factor, 14-run custom-constrained design fixture used to exercise the reference-DOE-style utility path: custom-optimal row selection, design comparison, augment-design, and the engine utility CLI surface.

## What this demo shows

- **`custom_constrained` family** with 14 runs, claim level `heuristic`.
- **Four factors**: temperature (24-32 C), pH setpoint (5.5-6.8), feed rate (1-6 mL/h), nitrogen source (categorical: yeast extract / peptone / ammonium sulfate).
- **Forbidden-combination constraint** that excludes the high-temperature / low-pH corner (temperature_c >= 31 AND ph_setpoint <= 5.7).
- **Reference DOE parity** path through `ferm-doe engine utility custom-optimal`, `compare-designs`, and `augment-design`.
- **Equipment, reagent, evidence, and historical-run-ledger inputs** so the validator and utility commands have realistic fixtures to read.

## First commands

```bash
# 1) Validate the manifest.
ferm-doe validate examples/reference-doe-custom-design --summary

# 2) Generate a custom-optimal design at a tighter 12-run budget.
ferm-doe engine utility custom-optimal \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/custom-optimal \
  --run-budget 12

# 3) Compare candidate designs.
ferm-doe engine compare-designs \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/compare-designs
```

## What you should see

- **Step 1**: status `YELLOW`, `error_count == 0`. Warnings may appear for profile-advised inputs.
- **Step 2**: writes a 12-row custom-optimal design to `/tmp/custom-optimal/`, with row provenance and D-optimal diagnostics.
- **Step 3**: writes a design comparison report covering full factorial, fractional factorial, and the custom-constrained alternative against the same budget.

## Non-claims

This is a synthetic public-safe fixture. The `claim_level` is `public_synthetic_demo`. Custom-optimal generation is labeled `heuristic`; review with a statistician before expensive runs. See [`../../NON_CLAIMS.md`](../../NON_CLAIMS.md).
