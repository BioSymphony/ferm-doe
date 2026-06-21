# Adapter Map

Capability-centric map of optional extras. The README's [Optional extras](../README.md#optional-extras) table is install-centric; this one starts from "I want to do X" and tells you which extra activates it.

The CLI is stdlib-only at runtime. Every adapter degrades to a `not_available` report when its extra is missing, so the demos and the closed-loop path run on a clean install. Install the extra only when a campaign needs the capability.

## By capability

| I want to... | Extra | Install | CLI surface that activates it |
|---|---|---|---|
| Get Student-t p-values in first-batch analysis | `scipy` | `pip install "biosymphony-ferm-doe[scipy]"` | `ferm-doe analyze` (auto) |
| Get t-quantile in DoE power | `scipy` | `pip install "biosymphony-ferm-doe[scipy]"` | `ferm-doe doe-power --sigma S` (auto) |
| Generate Box-Behnken with k ≥ 5 | `pydoe3` | `pip install "biosymphony-ferm-doe[pydoe3]"` | `ferm-doe generate-design` with `doe.family = box_behnken` and 5+ numeric factors |
| Generate maximin Latin Hypercube | `pydoe3` | `pip install "biosymphony-ferm-doe[pydoe3]"` | `ferm-doe generate-design` with `doe.family = latin_hypercube` |
| Run follow-up Bayesian optimization with a Gaussian-process surrogate | `botorch` | `pip install "biosymphony-ferm-doe[botorch]"` | `ferm-doe plan-wave2 --backend botorch --acquisition qei` or `qucb` (see [`WAVE2_BOTORCH.md`](WAVE2_BOTORCH.md)) |
| Route constrained DoE through BoFire (linear, total-mass, NChooseK) | `bofire` | `pip install "biosymphony-ferm-doe[bofire]"` | `ferm-doe plan-wave2 --backend bofire` or auto-routing when the manifest declares non-box constraints (see [`BOFIRE_POSITIONING.md`](BOFIRE_POSITIONING.md)) |
| Route NChooseK DoE through BoFire main | `adaptive-nchoosek-doe` | `pip install "biosymphony-ferm-doe[adaptive-nchoosek-doe]"` | Use when a first-batch DoE screen has a load-bearing NChooseK `min_count`; see [`BOFIRE_CONSTRAINT_PATTERNS.md`](BOFIRE_CONSTRAINT_PATTERNS.md) |
| Route multi-fidelity scale-bridge planning through BoFire | `bofire` | `pip install "biosymphony-ferm-doe[bofire]"` | `ferm-doe scale-recipe` with `MultiFidelityVarianceBasedStrategy` declared in the manifest |
| Run NChooseK Bayesian optimization (cardinality is load-bearing in BO) | `entmoot` | `pip install "biosymphony-ferm-doe[entmoot]"` | ENTMOOT v2 adapter; the documented swap for BoFire's `SoboStrategy + NChooseK` stall (see [`ENTMOOT_SWAP_DESIGN.md`](ENTMOOT_SWAP_DESIGN.md)) |
| Run MIP-optimized surrogate planning over linear and NChooseK constraints | `omlt` | `pip install "biosymphony-ferm-doe[omlt]"` | OMLT adapter at `adapters/omlt_strategy.py`; activates from the planner when MIP routing fits the constraint shape |
| Use a token-gated foundation-model surrogate for low-data sequential planning | `tabpfn` | `pip install "biosymphony-ferm-doe[tabpfn]"` | TabPFN adapter at `adapters/tabpfn_strategy.py`; inactive unless `TABPFN_TOKEN` is set at runtime |
| Compare follow-up candidate-generators (BayBE, Ax against the in-repo BoTorch route) | `backend-eval` | `pip install "biosymphony-ferm-doe[backend-eval]"` | `examples/adaptive-backend-eval/` fixtures; see [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) |
| Run SALib Sobol / Morris sensitivity over first-batch result rows | `sensitivity` | `pip install "biosymphony-ferm-doe[sensitivity]"` | SALib adapter at `adapters/salib_sensitivity.py` |
| Render Plotly figures in the BoFire HTML report | `report` | `pip install "biosymphony-ferm-doe[report]"` | `reporters/bofire_html.py` |
| Frictionless-validate table contracts (run ledger, evidence, design, results) | `contracts` | `pip install "biosymphony-ferm-doe[contracts]"` | Validators that read `schemas/tables/*.yaml` |

## Catch-all install

```bash
pip install "biosymphony-ferm-doe[all]"
```

Installs everything that does not require a paid or token-gated service. ENTMOOT, OMLT, and TabPFN are not in the catch-all because they each pull in solver stacks (`pyomo` + `highspy` + `lightgbm`) or foundation-model weights. Install those individually when a campaign uses them.

## Routing rules

The planner picks an adapter route based on what the manifest declares plus optional CLI flags:

- **Box constraints only, n < 4 usable first-batch rows, or categorical-heavy**: stdlib closed-loop path. No extra needed.
- **Numeric factors, n ≥ 4 usable rows, primary response declared**: `botorch` route is available; pass `--backend botorch`.
- **Linear constraints, mixture sums, total-mass**: `bofire` route fits; routes automatically when the manifest declares non-box constraints. Pass `--backend bofire` to force.
- **NChooseK cardinality matters in the BO loop**: route to `entmoot`. BoFire's `SoboStrategy + NChooseK` stalls on upstream issue #450; the ENTMOOT swap is documented at [`ENTMOOT_SWAP_DESIGN.md`](ENTMOOT_SWAP_DESIGN.md).
- **Hard MIP constraints over a learned surrogate**: `omlt` route.
- **Low-data prediction with a foundation model**: `tabpfn` route, token-gated.

When the requested route's extra is missing, the adapter writes a `not_available` report and the planner falls back to the stdlib path. The orchestrator can surface the short-circuit reason to the user.

## Health check

```bash
ferm-doe doctor
```

Reports which extras are installed and which adapters are active. Useful for debugging "why did this campaign route through stdlib when I expected BoFire?".

## Adapter status from the tool registry

See [`TOOL_REGISTRY.md`](TOOL_REGISTRY.md) and [`tool-registry.json`](tool-registry.json) for the curated 37-tool surface that includes each adapter's routing rationale, current signal, fit, and risks.
