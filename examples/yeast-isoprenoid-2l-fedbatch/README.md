# `yeast-isoprenoid-2l-fedbatch`: hydrophobic product fed-batch fixture

A 6-factor, 16-run optimization-RSM fixture for a yeast hydrophobic isoprenoid campaign running shake-flask to 2 L fed-batch. Demonstrates the product-class shape for hydrophobic, pellet-associated products with derived productivity and cost responses.

## What this demo shows

- **Profile `optimization_rsm`** with `custom_constrained` family and 16 runs.
- **Six factors**: production temperature, pH setpoint, inducer X concentration, production feed rate, harvest time, nitrogen supplement.
- **Three responses**: isoprenoid titer (primary, maximize), productivity (mg/L/h, derived), cost (USD/L, minimize). The objective composes titer, productivity, and a 5 USD/L cost ceiling.
- **Scale and process annotations** that fit a 2 L benchtop reactor: DO probe cascade, controlled pH, offgas O2/CO2, antifoam policy, bounded fed-batch feed after induction, 120 h maximum harvest.
- **Hydrophobic-product framing**: whole-broth and pellet-associated titer accounting in the response definition.

## First command

```bash
ferm-doe validate examples/yeast-isoprenoid-2l-fedbatch --summary
```

Then exercise the planning loop on the manifest:

```bash
ferm-doe recommend-family examples/yeast-isoprenoid-2l-fedbatch
ferm-doe generate-design examples/yeast-isoprenoid-2l-fedbatch \
  --out /tmp/yeast-isoprenoid/wave1_design.csv --seed 0
ferm-doe goals examples/yeast-isoprenoid-2l-fedbatch \
  --out /tmp/yeast-isoprenoid/goals.json
ferm-doe cost-rollup examples/yeast-isoprenoid-2l-fedbatch \
  --out /tmp/yeast-isoprenoid/cost.json
```

## What you should see

- **`validate --summary`**: status `YELLOW`, `error_count == 0`. The readiness verdict reflects that the fixture is a planning artifact on synthetic inputs.
- **`recommend-family`**: surfaces `custom_constrained` and adjacent RSM families with reasoned tradeoffs.
- **`generate-design`**: 16-run candidate design CSV labeled with `claim_level: heuristic`.
- **`goals`**: Derringer-Suich desirability composed across titer, productivity, and cost with the 5 USD/L ceiling.
- **`cost-rollup`**: per-run cost estimate against the declared unit prices and run budget.

## Non-claims

This is a synthetic public-safe fixture. Numbers in `inputs/` are illustrative; the readiness verdict stays `YELLOW` because no executed assay or scale-bridge evidence is attached. Use this fixture to verify the manifest contract for hydrophobic-product campaigns, not as a recipe. See [`../../NON_CLAIMS.md`](../../NON_CLAIMS.md).
