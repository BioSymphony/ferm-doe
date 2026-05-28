# Cost-constrained media optimization (BoFire smoke)

**Status:** public synthetic demo. `claim_level: public_synthetic_demo`. Authored 2026-05-15.

## What this demo proves

The stdlib design generators in this engine honor `low` / `high` factor bounds
but ignore declared mixture / cost / cardinality constraints. A campaign with
non-box constraints produces designs where some rows are infeasible and the
lab team hand-filters them at handoff.

This fixture exercises the BoFire-routed adapter
(`src/biosymphony_ferm_doe/adapters/bofire_strategy.py`) on three constraint
types simultaneously:

1. **Linear mass constraint:** total carbon ≤ 100 g/L (osmotic ceiling)
2. **N-choose-k cardinality:** between 1 and 2 carbon sources active
   (culture-prep logistics)
3. **Linear cost budget:** total media cost ≤ $0.80/L

The cost constraint is the load-bearing teaching point. It is expressed as a
plain `LinearInequalityConstraint` where coefficients are `$/g` and the RHS
is `$/L`:

```
Σ (concentration_i × cost_per_gram_i)  ≤  cost_budget_per_L
```

No new adapter code is required; the existing `_bofire_constraints` translator
handles cost as just another linear inequality.

## Factor table

| Factor | Range (g/L) | $/kg bulk | Notes |
|---|---|---|---|
| glucose | 0-50 | $0.70 | Food/feed grade |
| glycerol | 0-50 | $1.70 | USP 99.7% |
| lactose | 0-50 | $0.90 | Food grade |
| sucrose | 0-50 | $1.10 | Refined food |
| xylose | 0-50 | $2.00 | CP 95%; priciest commodity carbon |
| ammonium_sulfate | 0.5-10 | $0.25 | Fert/tech grade |
| corn_steep_liquor | 0-30 | $0.80 | 50% solids basis |
| yeast_extract | 0-25 | $3.50 | Commodity grade |
| tryptone | 0-20 | $12.00 | Casein peptone; most expensive N |

## Constraint hand-calc

- Min feasible spend (minimal AS only): ~$0.0003/L
- Max-N + cheap 2-carbon (50 glucose + 50 lactose + max-N stack):
  `0.080 + 0.354 ≈ $0.434/L` → feasible
- Max-N + expensive 2-carbon (50 xylose + 50 glycerol + max-N stack):
  `0.185 + 0.354 ≈ $0.539/L` → feasible
- Max-N + 80 g/L xylose alone (n-choose-k=1, would need higher carbon caps):
  excluded by `low: 0, high: 50` per-carbon caps anyway

The budget is binding at the upper corners but allows interior exploration,
appropriate for a 12-run D-optimal screening design.

## Routing expectation

With three non-box constraints declared, `routing_decision` should return:

```json
{
  "should_route": true,
  "strategy_kind": "constrained_doe",
  "reasons": ["non_box_constraints"]
}
```

Strategy dispatch: `DoEStrategy.make(domain=domain, criterion=DOptimalityCriterion(formula="linear"))`.
The adapter does not require observed data for the constrained-DoE path.

## Local execution (without BoFire installed)

```bash
python -m biosymphony_ferm_doe.cli plan-wave examples/demo-media-cost-bofire/campaign_manifest.json \
  --backend bofire \
  --out expected/bofire_strategy_report.json
```

Expected outcome: `adapter_status: "not_available"`, `domain_spec` populated
with the translated `Domain`, `candidate_design: []`, fallback to stdlib
augment-design path. This proves the routing fires and translation succeeds
without requiring the optional dependency.

## Remote execution (with BoFire installed)

Run the same CLI invocation inside a container or remote host that has the
optional `bofire[optimization]` extras installed (torch, cvxpy, botorch,
gpytorch). A PyTorch base image avoids re-downloading torch (~360 MB
uncompressed) as part of the BoFire install.

Expected outcome: `adapter_status: "executed"`, `candidate_design` populated
with 12 feasible rows, all satisfying total-carbon ≤ 100, cardinality ≤ 2,
and cost ≤ $0.80/L. HTML report emitted to
`expected/bofire_strategy_report.html`.

## Cost-pricing sources (2026 Q1-Q2 bulk indicative)

- Glycerine: ChemAnalyst Q1 2026, Selina Wamucii US wholesale
- Yeast extract corridor: Accio market survey ($2.50-30/kg)
- Ammonium sulfate: Intratec US ($675/ton 2026)
- Lactose: IndexBox spray-dried corridor
- Xylose: ScienceDirect techno-economic study (Q1 2026)
- E. coli defined-media cost analysis: ScienceDirect (Sridhar et al.)
- BioProcess International cost-modeling reference

Research-grade Sigma pricing is **10-50× higher** than bulk for commodity
components. Using Sigma prices in a demo would produce media that appears to
cost $10-30/L when the same recipe at process scale is $0.30-$2/L. Always
declare bulk pricing in the fixture and surface the spread as teachable.

## Non-claim

Pricing is teachable, not procurement-quote accurate. Strain, vessel, and
titer expectations are synthetic. The recipe is not benchtop-validated.
BioSymphony readiness gates and dossier checks remain authoritative for any
handoff.
