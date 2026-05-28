# `demo-shakeflask-to-2l-bofire`: shake flask to 2 L scale-bridge

Public synthetic fixture that exercises the BoFire multi-fidelity routing pattern for a 10 mL shake-flask scout arm informing a 2 L controlled bioreactor target arm. Profile: `scale_up_bridge`.

## What this demo shows

The fixture demonstrates the manifest shape a multi-fidelity adapter needs:

- **Shared recipe factors** across the shake-flask and 2 L reactor rows.
- **`campaign_arms`** with explicit low-fidelity (shake flask) and high-fidelity (2 L reactor) roles.
- **`scale_context`** naming the 2 L reactor as the target fidelity, with kLa as the primary bridge criterion.
- **Prior synthetic rows from both scales** in `inputs/` so adapter smoke tests have something to read.

The BoFire `MultiFidelityVarianceBasedStrategy` route activates when the optional `bofire` extra is installed; the smoke command also runs without the extra and produces a `not_available` report so the integration shape is testable on any laptop.

## First command

```bash
ferm-doe validate examples/demo-shakeflask-to-2l-bofire --summary
```

To exercise the multi-fidelity routing path:

```bash
pip install "biosymphony-ferm-doe[bofire]"
ferm-doe scale-recipe examples/demo-shakeflask-to-2l-bofire \
  --out /tmp/demo-shakeflask/scale_recipe.json \
  --md-out /tmp/demo-shakeflask/scale_recipe.md
```

## What you should see

- **`validate --summary`**: status `YELLOW`, `error_count == 0`. Bridge criteria are declared but unqualified until a real run attaches kLa measurements.
- **`scale-recipe`** with the `bofire` extra: a derived 2 L recipe (RPM, sparge rate, agitator power, predicted kLa) bridged from the shake-flask scout policy.
- **`scale-recipe`** without the extra: a stdlib-only recipe and an explicit `bofire_route: not_available` note in the JSON.

## Non-claims

Synthetic public-safe fixture. Claim level is `public_synthetic_demo`. Before physical execution, the scale recipe and kLa assumptions still need vessel-specific qualification. See [`../../NON_CLAIMS.md`](../../NON_CLAIMS.md) and [`../../docs/SCALE_BRIDGE_METHODOLOGY.md`](../../docs/SCALE_BRIDGE_METHODOLOGY.md).
