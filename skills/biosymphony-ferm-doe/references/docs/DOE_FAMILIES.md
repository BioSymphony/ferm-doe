# DoE Families

The skill recognizes a fixed set of design families. Each family's validator is intentionally light: minimum-runs guidance, replication / center-point expectations, randomization presence, and per-family structural requirements. Confounding analysis, power calculation, and lack-of-fit live with a statistician; the skill labels its claims accordingly.

Statistical claim levels:

- `exact`: the validator computed the exact property (rare).
- `adapter_backed`: a recognized DoE adapter generated and labeled the design.
- `approximate`: the design follows a known family pattern but the skill did not compute exact properties.
- `heuristic`: the agent picked a sensible structure and it should be reviewed before execution.

## Families

### `definitive_screening` (DSD)

Jones & Nachtsheim 2011. Identifies active main effects and quadratic curvature in `2k+1` runs for `k` numeric factors. Use when curvature is plausible and the run budget is small.

### `plackett_burman` (PB)

Resolution III screening for main effects only. Number of runs is the next multiple of 4 ≥ `k+1`. Cheapest way to identify active main effects when curvature can be ignored.

### `fractional_factorial`

2-level fractional factorial. Runs = `2^(k-p)`. Resolution determines aliasing:

- III: main effects aliased with two-factor interactions
- IV: main effects clear of two-factor interactions
- V: main effects and two-factor interactions clear of each other

Validator requires `resolution` to be declared and `alias_structure` to be recorded.

### `full_factorial`

All combinations across declared levels. Runs = `prod(levels_per_factor)`. Practical only for small `k` or categorical-heavy designs.

### `central_composite` (CCD)

`2^k + 2k + n_center`. Full quadratic. Validator expects ≥3 center points.

### `box_behnken` (BBD)

`2k(k-1) + n_center` for `k ≥ 3`. Rotatable; no axial points outside the cube. Use when corner points are infeasible (e.g., extreme combinations are physically off-limits).

### `optimal_d` and `optimal_i`

Computer-generated. `optimal_d` minimizes the variance of estimated coefficients; `optimal_i` minimizes prediction variance over the design region. Validator requires `model_terms` to be declared so the minimum-runs check can compare against the model parameter count.

### `scheffe_mixture`

Canonical mixture design. Runs depend on order `m`: `C(q + m - 1, m)`. Requires at least one mixture factor. Validator checks that mixture component values sum to 1 ± tolerance in the design rows.

### `extreme_vertices_mixture`

For mixtures with bounded components. Validator notes constraints but does not generate the vertices.

### `split_plot`

For hard-to-change vs easy-to-change factors. Validator requires at least one factor with `hard_to_change: true`. The design CSV should carry a whole-plot identifier so randomization within whole-plots can be honored.

### `custom_constrained`

Design honoring hard constraints. No standard formula; declare `n_runs` explicitly and (advised) an `alias_structure` description.

### `sequential_augmentation`

follow-up augmentation of a prior wave. Validator requires `previous_wave_ref` to point at the prior design CSV.

## Generation

`ferm-doe generate-design <campaign> --out wave1.csv` emits the design CSV directly from the manifest's `doe.family`. Stdlib only.

Claim levels by family in this build:

| Family | Claim | Notes |
|---|---|---|
| `full_factorial` | `exact` | All factor types supported |
| `fractional_factorial` | `exact` | Standard generators tabulated for k ≤ 8; explicit `generators` honored |
| `plackett_burman` | `exact` | Williams construction for n ∈ {8, 12, 16, 20, 24} |
| `definitive_screening` | `exact` | Conference matrices for m ∈ {4, 6, 10} → k ∈ {3, 4, 5, 6, 9, 10} |
| `central_composite` | `exact` | Face-centered (default), rotatable, orthogonal |
| `box_behnken` | `exact` | k ∈ {3, 4} only; larger k errors out |
| `latin_hypercube` | `exact` | Uniform-interval LHS, no maximin optimization |
| `scheffe_mixture` | `exact` | Simplex-lattice and simplex-centroid |
| `optimal_d`, `optimal_i` | `heuristic` | Coordinate exchange; review with a statistician |
| `extreme_vertices_mixture` | `heuristic` | Basic constraint enumeration with centroid |

For families or k values outside the supported set, the generator raises a `ValueError` with a specific reason: pick a different family or hand off to JMP / Design-Expert / Modde.

## What the validator still does *not* do

- Compute exact alias structure beyond family-level guidance.
- Compute statistical power.
- Detect lack-of-fit.
- Recommend a family. That is the agent's call, ideally with the user.

For those, hand off to a statistician. The skill's job is to make the handoff legible and to ship a design that the statistician can review.
