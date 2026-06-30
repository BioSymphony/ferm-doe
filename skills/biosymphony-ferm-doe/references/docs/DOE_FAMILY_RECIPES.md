# DoE Family Recipes

Recipes for swapping `doe.family` on an existing manifest to exercise different generators. For the underlying taxonomy and claim levels, see [`DOE_FAMILIES.md`](DOE_FAMILIES.md). This doc focuses on the manifest patch and the run command.

## How `doe.family` selection works

`ferm-doe generate-design` reads `doe.family` from the manifest and dispatches to the matching generator. Every row in every output CSV carries a `claim_level` label so a statistician can see how the matrix was produced. The generator is stdlib-only; no scientific extras required.

To swap families on a fixture, copy the manifest, edit `doe.family` (plus any family-specific fields), and run `generate-design`:

```bash
cp examples/demo-pb-screening-public/campaign_manifest.json /tmp/swap_test/campaign_manifest.json
# edit /tmp/swap_test/campaign_manifest.json: change doe.family
ferm-doe generate-design /tmp/swap_test --out /tmp/swap_test/wave1.csv --seed 0
```

For each recipe below, the manifest patch shows the minimum set of fields the generator needs. Anything not mentioned is unchanged from the source manifest.

## `full_factorial`

Use when factor count is small (k ≤ 4 numeric, or k ≤ 3 with several categoricals) and you want exhaustive coverage.

```json
{
  "doe": {
    "family": "full_factorial",
    "n_runs": null
  }
}
```

`n_runs` is computed from the factor levels, so leave it null or omit. Claim level: `exact`.

## `fractional_factorial`

Use when you have many 2-level factors and want main-effects-clear-of-2fi resolution.

```json
{
  "doe": {
    "family": "fractional_factorial",
    "resolution": "IV",
    "alias_structure": "I + ABCD + ABE + CDE + ..."
  }
}
```

The validator requires `resolution` to be declared. Standard generators are tabulated for k ≤ 8; for larger k, declare `generators` explicitly. Claim level: `exact`.

## `plackett_burman`

Cheapest main-effects screen. Number of runs is the next multiple of 4 ≥ k+1.

```json
{
  "doe": {
    "family": "plackett_burman",
    "n_runs": 12,
    "n_center": 3
  }
}
```

Williams construction is tabulated for `n_runs ∈ {8, 12, 16, 20, 24}`. Curvature is not estimable; pair with a center-point set to detect it. Claim level: `exact`. Exercised by [`demo-pb-screening-public`](../examples/demo-pb-screening-public/).

## `definitive_screening`

Detects active main effects and quadratic curvature in 2k+1 runs.

```json
{
  "doe": {
    "family": "definitive_screening",
    "n_center": 1
  }
}
```

Conference matrices are tabulated for `m ∈ {4, 6, 10}` → `k ∈ {3, 4, 5, 6, 9, 10}`. Claim level: `exact`. Exercised by [`demo-scale-bridge-public`](../examples/demo-scale-bridge-public/) and [`demo-warnings-walkthrough-public`](../examples/demo-warnings-walkthrough-public/).

## `central_composite`

Full quadratic. `2^k + 2k + n_center` runs.

```json
{
  "doe": {
    "family": "central_composite",
    "n_center": 4,
    "alpha": "rotatable"
  }
}
```

`alpha` choices: `face-centered` (default; alpha = 1), `rotatable` (alpha = (2^k)^(1/4)), `orthogonal`. The validator expects at least 3 center points. Claim level: `exact`.

## `box_behnken`

Rotatable quadratic without axial corner points. Use when corner combinations are infeasible.

```json
{
  "doe": {
    "family": "box_behnken",
    "n_center": 3
  }
}
```

Tabulated for `k ∈ {3, 4}` only. For larger `k`, the generator raises `ValueError`; install the optional `pydoe3` extra to access `k ≥ 5`. Claim level: `exact`.

## `latin_hypercube`

Space-filling design. Useful as a first-batch scout when the factor space is wide and the priors are weak.

```json
{
  "doe": {
    "family": "latin_hypercube",
    "n_runs": 24
  }
}
```

Stdlib generator does uniform-interval LHS, no maximin optimization. Install the optional `pydoe3` extra for maximin LHS. Claim level: `exact`.

## `scheffe_mixture`

Canonical mixture design. Components must sum to 1 (or a declared total).

```json
{
  "doe": {
    "family": "scheffe_mixture",
    "mixture_order": 2,
    "mixture_components": ["glucose_g_l", "yeast_extract_g_l", "peptone_g_l"]
  }
}
```

Runs depend on order: `C(q + m - 1, m)`. Validator checks that mixture component values sum to 1 ± tolerance in the design rows. Claim level: `exact`.

## `extreme_vertices_mixture`

For mixtures with bounded components. Enumerates the constrained vertices and centroid.

```json
{
  "doe": {
    "family": "extreme_vertices_mixture",
    "mixture_components": ["glucose_g_l", "yeast_extract_g_l", "peptone_g_l"],
    "mixture_bounds": {
      "glucose_g_l": {"low": 5, "high": 30},
      "yeast_extract_g_l": {"low": 0, "high": 15},
      "peptone_g_l": {"low": 2, "high": 20}
    }
  }
}
```

Claim level: `heuristic`. Review with a statistician before expensive runs.

## `optimal_d` and `optimal_i`

Coordinate-exchange optimal designs. `optimal_d` minimizes coefficient variance; `optimal_i` minimizes prediction variance over the region.

```json
{
  "doe": {
    "family": "optimal_d",
    "n_runs": 16
  },
  "model_terms": {
    "interactions": true,
    "quadratics": false,
    "max_interaction_order": 2
  }
}
```

The validator requires `model_terms` so the minimum-runs check can compare against the model parameter count. Claim level: `heuristic`. Exercised indirectly by [`reference-doe-custom-design`](../examples/reference-doe-custom-design/) via `ferm-doe engine utility custom-optimal`.

## `split_plot`

Hard-to-change whole-plot factors plus easy-to-change sub-plot factors.

```json
{
  "factors": [
    {"factor_id": "temp_c", "type": "numeric", "low": 28, "high": 37, "hard_to_change": true},
    {"factor_id": "do_pct", "type": "numeric", "low": 20, "high": 60, "hard_to_change": true},
    {"factor_id": "carbon_g_l", "type": "numeric", "low": 10, "high": 40}
  ],
  "doe": {
    "family": "split_plot",
    "whole_plot_reps": 4,
    "sub_plots_per_whole_plot": 3
  }
}
```

The validator requires at least one factor with `hard_to_change: true`. The design CSV carries a `whole_plot_id` column. Claim level: `exact`. Exercised by [`demo-split-plot-fedbatch-public`](../examples/demo-split-plot-fedbatch-public/).

## `custom_constrained`

For designs that honor hard constraints with no standard formula. Most BoFire-routed and reference-DOE flows land here.

```json
{
  "doe": {
    "family": "custom_constrained",
    "n_runs": 14,
    "alias_structure": "main effects + selected 2fi"
  },
  "constraints": [
    {"constraint_id": "media_total", "type": "linear", "expression": "glucose + ye + peptone == 30"},
    {"constraint_id": "cardinality", "type": "n_choose_k", "components": ["c1", "c2", "c3", "c4"], "k": 2}
  ]
}
```

The stdlib generator emits the manifest's declared rows or routes through the BoFire / ENTMOOT adapters when their extras are installed. Claim level: `heuristic`. Exercised by [`reference-doe-custom-design`](../examples/reference-doe-custom-design/), [`yeast-isoprenoid-2l-fedbatch`](../examples/yeast-isoprenoid-2l-fedbatch/), and [`demo-media-cost-bofire`](../examples/demo-media-cost-bofire/).

## `sequential_augmentation`

follow-up augmentation. Used by `ferm-doe plan-wave2` rather than `generate-design`.

```json
{
  "doe": {
    "family": "sequential_augmentation",
    "previous_wave_ref": "expected/selected_wave_1_design.csv"
  }
}
```

The validator requires `previous_wave_ref` to point at a valid first-batch design CSV. Claim level: `planned_wave2_design`. See [`ADAPTIVE_WAVE2.md`](ADAPTIVE_WAVE2.md) and [`WAVE2_BOTORCH.md`](WAVE2_BOTORCH.md).

## When the generator refuses

`ferm-doe generate-design` raises a `ValueError` with a specific reason when:

- the family is unrecognized
- the factor count is outside the supported range for the family (Box-Behnken k ≥ 5 without the `pydoe3` extra, conference-matrix DSD k not in {3, 4, 5, 6, 9, 10}, etc.)
- a family-specific required field is missing (e.g., `mixture_components` for mixture designs)

The error message names the family and the missing or invalid field. Fix the manifest and re-run. For families outside the supported set, install the optional adapter, route through BoFire / ENTMOOT, or hand off to a commercial DoE tool.

## Picking a family

If you do not know which family fits the campaign, run the recommender:

```bash
ferm-doe recommend-family examples/demo-pb-screening-public
```

It surfaces ranked candidates with rationale that names the factor count, the curvature prior, and the run-budget constraint. The recommendation is advice, not gating; the agent or the user makes the final call.
