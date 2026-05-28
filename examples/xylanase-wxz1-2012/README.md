# `xylanase-wxz1-2012`: public-paper starter

Public-paper-derived starter fixture. Normalizes the Plackett-Burman and Box-Behnken xylanase fermentation data from Cui & Zhao 2012 into the BioSymphony manifest contract so the validator, factor-space audit, and first-batch planning workflow have a realistic historical-data shape to work with.

## Source

- Title: *Optimization of Xylanase Production from Penicillium sp. WX-Z1 by a Two-Step Statistical Strategy: Plackett-Burman and Box-Behnken Experimental Design*
- Authors: F. J. Cui and L. M. Zhao
- Year: 2012
- DOI: [`10.3390/ijms130810630`](https://doi.org/10.3390/ijms130810630)
- License: CC BY 3.0
- Use here: numeric run table normalized into the demo historical ledger with attribution. Prose is not copied.

See [`source/`](source/) for the full source catalog and additional candidate sources flagged for future curation.

## What this demo shows

- **Profile `screening`** with `custom_constrained` family.
- **Five numeric media factors**: wheat bran, yeast extract, sodium nitrate, magnesium sulfate, calcium chloride.
- **One response**: xylanase activity (U/mL), maximize.
- **47-row historical run ledger** at `inputs/historical_run_ledger.csv` derived from the paper's Plackett-Burman and Box-Behnken tables. Each row carries `inclusion_status`, `trust_score`, `source_doi`, and `data_license` so the validator can audit provenance.
- **Factor-space evidence** in `inputs/evidence_table.csv` with citations.
- **Pre-populated Linear issue** at `linear_issues/wave0-readiness.md` showing how the readiness verdict maps to a tracker entry.

This fixture exercises the historical-data-rescue path (turning scattered public-paper data into a trusted run ledger) and the upstream-readiness audit that runs before any first-batch planning.

## First command

```bash
ferm-doe validate examples/xylanase-wxz1-2012 --summary
```

Then exercise the historical-aware planning loop:

```bash
ferm-doe inspect-campaign examples/xylanase-wxz1-2012
ferm-doe recommend-family examples/xylanase-wxz1-2012
ferm-doe generate-design examples/xylanase-wxz1-2012 \
  --out /tmp/xylanase/wave1.csv --seed 0
```

## What you should see

- **`validate --summary`**: status `YELLOW`, `error_count == 0`. The verdict reflects the planning-fixture status; the historical ledger is `trusted` but no executed first-batch evidence is attached yet.
- **`inspect-campaign`**: surfaces the source-attributed provenance, the 5 numeric factors, the single response, and the `screening` profile.
- **`recommend-family`**: suggests families compatible with 5 numeric factors and the maximize objective. Plackett-Burman or definitive screening are typical first choices given the paper's history.
- **`generate-design`**: writes a 4-row screening design CSV labeled `claim_level: heuristic` (the manifest declares `custom_constrained` with a 4-run budget; swap `doe.family` to `plackett_burman` or `box_behnken` per [`../../docs/DOE_FAMILY_RECIPES.md`](../../docs/DOE_FAMILY_RECIPES.md) for richer designs).

## Non-claims

This is a public-paper-derived planning fixture, not a lab execution recommendation. The numeric run table is normalized from the cited paper for software and planning workflow exercises. Before any physical execution, the organism, assay, safety, and equipment must be reviewed locally. Claim level: `public_synthetic_demo`. See [`../../NON_CLAIMS.md`](../../NON_CLAIMS.md) and [`source/source_catalog.md`](source/source_catalog.md).
