# Adapter Design Notes

**Audience:** future contributors and reviewers reading the adapter source under [`../src/biosymphony_ferm_doe/adapters/`](../src/biosymphony_ferm_doe/adapters/). The why behind the load-bearing design decisions in each adapter, captured so the lessons are inspectable instead of buried in commit history.

Pairs with [`BACKEND_EVAL_FINDINGS.md`](BACKEND_EVAL_FINDINGS.md) (what the adapters actually shipped on a 6-fixture sweep) and [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) (the depth ladder).

## OMLT — lower-coupling for NChooseK indicators

**Adapter:** [`../src/biosymphony_ferm_doe/adapters/omlt_strategy.py`](../src/biosymphony_ferm_doe/adapters/omlt_strategy.py).
**Stack:** `omlt 1.2.2` + `pyomo 6.10.0` + `highspy 1.14.0` + `lightgbm 4.6.0` + `onnx 1.21.0` + `onnxmltools 1.16.0` + `scikit-learn 1.8.0`. All MIT/BSD/Apache.

### Decision 1: default surrogate is LightGBM gradient-boosted trees

OMLT supports three formulations: `GBTBigMFormulation` (gradient-boosted trees), `NeuralNetworkFormulation` (NN as MIP via ReLU big-M), and a linear-model formulation. The adapter defaults to GBT because:

- It matches ENTMOOT's default surrogate, so the OMLT slot is a drop-in alternative when ENTMOOT's leak rate is unacceptable or when an operator wants a different MIP encoding to compare against on the same fixture.
- The GBT MIP encoding is the most mature OMLT path. The NN formulation requires careful big-M selection per layer and can blow up to > 100k variables for a 4-layer ReLU MLP. GBT stays compact (constant-per-leaf indicators).
- Tree ensembles handle categorical splits natively, which matters for the `low_data_hybrid_transfer` and `adaptive_orchestration` fixtures.

The NN surrogate path is reserved; the adapter accepts `surrogate_kind="nn"` as a parameter but silently routes to GBT in this release with a recorded note. A future pass can ship the NN path once a real-world fixture asks for it.

### Decision 2: lower-coupling on NChooseK indicators

This is the load-bearing fix. The default OMLT (and ENTMOOT) NChooseK encoding uses big-M coupling on the active indicator:

```
x_i ≤ M · b_i
```

This admits the degenerate solution `(x_i = 0, b_i = 1)` as feasible — the binary indicator says "active" but the continuous amount is zero. Under a binary-indicator definition of "active count" the MIP is satisfying the constraint; under a lab-side `x_i > 0` definition (the actual amount being delivered) the MIP is leaking. Auto-fantasy resampling at batch ≥ 16 plus the larger candidate space makes the degenerate corner attractive.

The fix is a complementary lower-bound coupling that forces activated indicators to produce strictly positive amounts:

```python
# After x_i ≤ M · b_i:
for i, feature in enumerate(features):
    lo, hi = bounds[feature]
    span = hi - lo
    eps = 0.01  # 1% of span; small enough not to distort the surrogate
    m.addConstr(x[feature] >= (lo + eps * span) * b[i])
    # forces b_i=1 → x_i ≥ lo + 1% · span
```

The adapter ships this lower-coupling by default. Initial OMLT baseline sweep without the fix surfaced 8 / 10 NChooseK leaks on `cardinality_heavy_media`. With the lower-coupling in place: 0 / 10 leaks. The same fix is the recommended one-line patch for ENTMOOT (see "ENTMOOT — definition-correction" below).

### Decision 3: solution diversity via no-good cuts

HiGHS via Pyomo's APPSI does not expose a solution pool. To produce N diverse candidates, the adapter solves the MIP once, appends a no-good cut on the binary-indicator tuple (Hamming distance ≥ 1 from the previous solution's indicator pattern), and re-solves. For continuous-only manifests where no binary indicators are present, the fallback is ±5% perturbation from the previous solution.

The effect is that cardinality-heavy fixtures stop early when no-good cuts exhaust the feasible combinatorial space. `cardinality_heavy_media` (4 carbons, NChooseK(1, 2)) produces exactly 10 candidates — there are `C(4, 1) + C(4, 2) = 4 + 6 = 10` distinct binary indicator configurations. `static_constrained_media` (3 NChooseK features, NChooseK(1, 2)) produces 6 for the same reason. Both stop short of any `--budget 16` ceiling on purpose; duplicate-with-perturbation would not add information at fixed indicator patterns.

### Decision 4: HiGHS via APPSI

`appsi_highs` is the default solver. It raises a benign `RuntimeError: A feasible solution was not found` on the negative-control infeasible problem; the adapter catches that in `_solve_once` and surfaces it as `None`, which causes the wrapper to fail closed with a route reason. No false-positive solutions get through.

### Operating regime

- ≤ 50 numeric factors.
- ≤ 5 cardinality.
- Single-objective only (no native multi-objective; route declines if MO is required).
- Tree depth bounded; deep trees can blow up the MIP.

## TabPFN — Gaussian-approximation posterior wrap

**Adapter:** [`../src/biosymphony_ferm_doe/adapters/tabpfn_strategy.py`](../src/biosymphony_ferm_doe/adapters/tabpfn_strategy.py).
**Stack:** `tabpfn 8.0.3` + `botorch 0.17.2` + `torch 2.12.0`. Token-gated by Prior Labs.

### Decision 1: token gate is environment-only

TabPFN v3 / v2.5 / v2.6 require a license token issued by Prior Labs. The adapter checks for `TABPFN_TOKEN` in the environment at call time and routes-decline cleanly when absent. No token is ever stored in the manifest, fixture, registry, log, or any tracked file. The adapter is import-safe without the token: `is_available()` returns `False`, the `not_available` route reason is surfaced, and BioSymphony falls back to its stdlib augment-design path.

### Decision 2: Gaussian-approximation posterior wrap

TabPFN's native posterior is a 100-bucket `FullSupportBarDistribution` — an empirical bar histogram, not a Gaussian. BoTorch's acquisition machinery expects a `Posterior` object that exposes `.mean`, `.variance`, and (for q-acquisitions) `.rsample()`. Two implementation paths were considered:

1. **Gaussian-approximation wrap (chosen).** Query TabPFN with `output_type='quantiles', quantiles=[0.159, 0.5, 0.841]` to get q₁₆, median, q₈₄. Treat the marginal posterior at each point as Gaussian with `mean = q_50` and `sigma = (q_84 - q_16) / 2`. Wrap as `GPyTorchPosterior(MultivariateNormal(mean, diag(variance)))`. Covariance between query points is taken as zero (independence).
2. **Faithful subclass** of `botorch.posteriors.Posterior` that samples directly from the bar distribution via `criterion.icdf(uniform_sample)`. Slower, more code, no clear win at q=1.

The adapter ships path 1. The marginal mean and variance are exact for analytic Log-EI at q=1 (which is how the adapter scores the candidate pool); the diagonal-covariance simplification only enters if a sampler-driven q-acquisition is used, which the adapter does not. The faithful subclass remains the right next step if a future contributor needs calibrated higher-q sampling.

The trade-off: the Gaussian approximation may underestimate uncertainty in highly non-Gaussian regions (e.g. multimodal posteriors). On low-data low-dim regimes (n < 20, d ≤ 8) this is acceptable; for higher-data regimes a GP-based surrogate (BoTorch direct) is usually a better default anyway.

### Decision 3: sample-then-rank acquisition (no gradient through TabPFN)

TabPFN does not propagate gradients through `predict()`. BoTorch's default `optimize_acqf` L-BFGS-B path raises `RuntimeError: element 0 of tensors does not require grad`. Rather than wrap a non-existent gradient path, the adapter uses a sample-then-rank acquisition:

1. Sample a constraint-feasible pool of 512 candidates in the coded design space. NChooseK is enforced at sample time via random-active-subset; linear constraints via rejection sampling.
2. Score every pool point with analytic Log-EI from TabPFN's Gaussian-approximated marginal.
3. Pick top-q with greedy maximum-distance selection in coded space (single-point Log-EI plus half a unit of minimum-distance-to-already-chosen, normalized so the diversity term has weight at the same order of magnitude as the log-EI ranking term).

The result is gradient-free, deterministic for a given seed, and naturally constraint-aware.

### Decision 4: routing rules

Routing is OR-of-reasons. Any one match fires the adapter unless the operator hard-pinned a different backend (`stdlib`, `bofire`, `botorch`, `entmoot`, `baybe`, `pydoe`, `pydoe3`, `numpy`, `scipy`):

| Reason | Trigger |
|---|---|
| `low_data_regime` | `len(usable_rows) < 20` |
| `small_factor_count` | `1 ≤ len(eligible_factors) ≤ 8` |
| `operator_requested_tabpfn` | `backend="tabpfn"` passed explicitly |

Eligible factors are the design-active ones (continuous, numeric, ordinal, discrete, categorical), excluding role-metadata, response, and block-only factors. For ineligible cases (> 20 prior runs AND > 8 factors AND no explicit request), the route declines and BioSymphony falls back to its stdlib augment-design path. This matches the slot — TabPFN is the explicit low-data low-dim surrogate, never the workhorse.

### Operating regime

- n < 20 prior observations (TabPFN's strength).
- d ≤ 8 eligible factors.
- Single-objective only (sample-then-rank is single-output).
- TabPFN's fit scales O(n²) — at n > 500 a different surrogate is needed.
- Non-commercial license on v3 / v2.5 / v2.6. The older `v2-reg` is Apache-2.0.

## ENTMOOT — definition-correction

**Adapter:** [`../src/biosymphony_ferm_doe/adapters/entmoot_strategy.py`](../src/biosymphony_ferm_doe/adapters/entmoot_strategy.py).
**Swap design:** [`ENTMOOT_SWAP_DESIGN.md`](ENTMOOT_SWAP_DESIGN.md).

### The two definitions of "NChooseK active count"

There are two parallel definitions in active use, and the adapter and the lab-side contract emitter were enforcing different ones:

| Definition | Source | Pass criterion |
|---|---|---|
| Binary indicator | adapter-internal `cardinality_ok` flag | `b_i ≥ 0.5` (the MIP indicator says active) |
| Lab semantic | contract-emitter `check_constraints` | `x_i > 0` (the actual amount delivered is nonzero) |

Both are measurements of "NChooseK active count," but they answer different questions. The adapter's internal closure (`cardinality_ok = True` on the binary indicator) holds at all tested batch sizes. The lab-side check (was any actual reagent delivered?) surfaced 5 / 16 leaks on the `cardinality_heavy_media` fixture. Same code path, two different definitions — not a batch-size dependence.

### Root cause

`EntmootStrategy._apply_nchoosek` enforces only the one-directional big-M coupling: `x_i ≤ M · b_i`. The MIP is free to set `b_i = 1, x_i = 0` (degenerate ON-but-empty). Auto-fantasy resampling at batch=16, plus the larger candidate space the MIP explores at higher q, makes the degenerate corner increasingly attractive as q grows.

### Recommended fix (one line)

Add the complementary lower-bound coupling — identical to the one OMLT ships:

```python
# After x_i ≤ M·b_i:
for i, feature in enumerate(features):
    lo, hi = bounds[feature]
    span = hi - lo
    eps = 0.01  # OMLT uses 0.01; small frac of span
    m.addConstr(x[feature] >= (lo + eps * span) * b[i])
    # forces b_i=1 → x_i ≥ lo + 1% · span
```

This is empirically validated against the same fixture: OMLT (which ships the lower-coupling by default) gets 0 / 10 NChooseK leaks where the same surrogate (LightGBM) and the same MIP encoding without the lower-coupling gets 8 / 10. The diagnosis is the encoding choice, not the surrogate.

### Disposition

For new campaigns: prefer OMLT — the fix ships by default. For existing rigs with ENTMOOT in place: the one-line patch above is straightforward. The depth ladder in [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md) signals the swap.

## BoTorch direct — wrapper-side cost-weighting trap

**Scope note:** the public repo's BoTorch adapter ([`../src/biosymphony_ferm_doe/adapters/botorch_wave2.py`](../src/biosymphony_ferm_doe/adapters/botorch_wave2.py)) is a simpler follow-up route around `qEI` / `qUCB` / `qTS`, without cost weighting and without post-hoc NChooseK filtering. The trap described below comes from a separate cost-weighted BoTorch direct wrapper that wraps `qLogExpectedImprovement` (single-objective) or `qLogExpectedHypervolumeImprovement` (multi-objective) in `InverseCostWeightedUtility` when a cost constraint is declared, and applies post-hoc NChooseK filtering. That wrapper does not ship in this public repo today. The pattern is documented here because anyone building a cost-aware BoTorch wrapper is likely to hit it.

### The trap

On `cardinality_heavy_media` (4 carbons, NChooseK(1, 2), 4 prior observations, no cost constraint declared in the manifest), a cost-weighted wrapper still applies cost-weighting if it builds an unconditional fallback `cost(x) = sum(|x|) + 1e-3` cost model whenever no cost constraint is declared. With 4 prior observations the GP posterior is essentially flat over the bulk of the cube (the wrapper's GP fit returns a constant predicted titer for points away from the prior set). The cost-weighted acquisition is then dominated by the cost term, and the joint optimizer collapses every candidate to the cost minimum — the origin.

Budget transition:

| Budget | Raw emitted | Kept (PASS NChooseK) | Active-factor distribution |
|---|---|---|---|
| 16 | 16 | 0 | all 16 at active=0 (origin) |
| 64 | 64 | 0 | all 64 at active=0 |
| 256 | 256 | 37 | spread across active ∈ {1, 2, 3, 4} |

At q=256 the joint-batch acquisition cannot collapse all candidates to one point; the optimizer spreads. The phase transition is between q=64 and q=256.

### Recommended fix (wrapper-side)

Make any cost-model build step conditional on the fixture actually having a `type=linear` cost constraint declared on the manifest. When no cost constraint is declared, use plain `qLogExpectedImprovement` without the cost-weighting wrap:

```python
has_cost_constraint = any(
    c.type == "linear" and c.role == "cost"
    for c in manifest_constraints
)
if has_cost_constraint:
    acq = CostWeightedAcquisition(base_acq, cost_model)  # only when a cost constraint exists
else:
    acq = base_acq  # plain qLogEI; no unconditional cost weighting
```

This is wrapper-side, not BoTorch upstream. For typical 16-candidate budgets on cardinality fixtures with no explicit cost constraint, prefer OMLT or ENTMOOT-with-fix instead of bumping BoTorch's budget to 256.

## Multi-objective BO — memory knobs

The same scope note as the BoTorch direct trap above: this section captures findings from a cost-aware multi-objective BoTorch wrapper that does not ship in the public repo today. Documented here as a design pattern for anyone building or evaluating one. A cost-aware multi-objective path on `cost_aware_multiobjective` initially OOM'd at q=16 on commodity hardware; the relevant findings:

### 1. `optimize_acqf(sequential=True)` is the biggest RAM lever

For MO BO at q ≥ 8, the single biggest RAM lever is `optimize_acqf(sequential=True)`, not the choice between `qLogEHVI` and `qLogNEHVI`. Sequential mode optimizes the q candidates one at a time, which drops the autograd graph size by roughly `q ×` (from `O(q · n_obs · M)` to `O(n_obs · M)`). On the 4-response `cost_aware_multiobjective` fixture at q=8, this is the difference between an out-of-memory run and a comfortable one on commodity hardware.

### 2. Env-driven knobs (recommended defaults)

If you build an env-driven MO wrapper, the recommended defaults that have been observed to reproduce on commodity hardware are:

```
BOTORCH_MO_ACQUISITION   default qLogEHVI    (opt-in qLogNEHVI)
BOTORCH_MO_MC_SAMPLES    default 32          (down from BoTorch default 512)
BOTORCH_NUM_RESTARTS     default 3           (down from a typical hard-coded 10)
BOTORCH_RAW_SAMPLES      default 64          (down from a typical hard-coded 256)
BOTORCH_MO_SEQUENTIAL    default 1           (passes sequential=True)
BOTORCH_MO_DROP_DERIVED  default 1           (drops measurement_type ∈ {derived, calculated})
BOFIRE_MO_ACQUISITION    default qLogEHVI    (same default for the BoFire MO route)
```

Operators can opt-in to `qLogNEHVI` or larger MC samples when needed.

### 3. Cost-weighted acquisition wrapper must expose `X_pending`

A latent bug pattern: `optimize_acqf(sequential=True)` reads `acq.X_pending` between solves to avoid re-picking points it already picked this batch. If a cost-weighted acquisition wrapper does not expose `X_pending`, `sequential=True` raises `AttributeError: '<WrapperClass>' object has no attribute 'X_pending'`. The fix is a property + setter that proxies to the base acquisition:

```python
class CostWeightedAcquisition(...):
    @property
    def X_pending(self):
        return self.base_acquisition.X_pending

    @X_pending.setter
    def X_pending(self, value):
        self.base_acquisition.X_pending = value

    def set_X_pending(self, X):
        self.base_acquisition.set_X_pending(X)
```

This kind of bug stays latent until sequential mode is first exercised in tests. Worth a unit test that exercises `optimize_acqf(sequential=True)` on a small MO fixture for any new cost-weighting wrapper.

### 4. Drop derived / calculated responses from the surrogate fit

When ≥ 3 responses are declared and the manifest tags some as `measurement_type ∈ {derived, calculated}` (e.g. productivity computed from titer / time, cost-per-mg computed from cost / titer), an MO wrapper can drop those from the surrogate-fit response set. This collapses a 4-response 16-orthant FastNondominatedPartitioning to 2 GPs + 4-orthant partitioning, well within budget. Derived responses can still appear on the candidate table as predicted values for downstream review; they're just not fit as separate GPs.

## Quick reference: which knob fixes which symptom

| Symptom | Adapter | Knob | Notes |
|---|---|---|---|
| NChooseK leak on cardinality fixture (`x_i = 0` with `b_i = 1`) | OMLT, ENTMOOT | add `x_i ≥ (lo + 0.01 · span) · b_i` lower-coupling | OMLT ships it; ENTMOOT does not yet |
| BoTorch direct emits 0 NChooseK-feasible candidates at q ≤ 64 | BoTorch direct | bump q to ≥ 256, or make cost-weighting conditional on declared cost constraint | wrapper-side; consider switching to OMLT instead |
| MO BO OOM at q ≥ 8 | BoTorch direct, BoFire | `optimize_acqf(sequential=True)` | drops autograd graph by `q ×` |
| MO BO still OOM after sequential | wrapper | `MC_SAMPLES=32`, `num_restarts=3`, `raw_samples=64` | `MC_SAMPLES` is the bigger lever |
| MO BO still slow with 4 responses, some derived | wrapper | `BOTORCH_MO_DROP_DERIVED=1` | 4 → 2 GPs collapses the partitioning order |
| `optimize_acqf(sequential=True)` raises `AttributeError: X_pending` under cost weighting | BoTorch wrapper (external) | add `X_pending` property + setter on the cost-weighting wrapper class | proxy to the base acquisition |
| TabPFN raises `RuntimeError: element 0 of tensors does not require grad` | TabPFN | use sample-then-rank acquisition (don't call `optimize_acqf`) | gradient-free; deterministic at fixed seed |

## What was not tested

The same caveats as in [`BACKEND_EVAL_FINDINGS.md`](BACKEND_EVAL_FINDINGS.md): single seed (42), synthetic fixtures, no large-n behavior characterization, no multiple-strategy probes against upstream BoFire main beyond the documented PR set. The design decisions captured here are intended to be inspectable; before treating any of them as load-bearing in a new campaign, verify against current upstream behavior of the underlying library — these notes anchor in a specific mid-2026-05 snapshot.

## Pointers

- 6-fixture sweep results per backend: [`BACKEND_EVAL_FINDINGS.md`](BACKEND_EVAL_FINDINGS.md).
- Depth ladder: [`BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`](BIOMANUFACTURING_ADAPTIVE_BACKENDS.md).
- BoFire routing: [`BOFIRE_POSITIONING.md`](BOFIRE_POSITIONING.md), [`BOFIRE_CONSTRAINT_PATTERNS.md`](BOFIRE_CONSTRAINT_PATTERNS.md).
- ENTMOOT swap design: [`ENTMOOT_SWAP_DESIGN.md`](ENTMOOT_SWAP_DESIGN.md).
- Capability-centric map of optional extras: [`ADAPTER_MAP.md`](ADAPTER_MAP.md).
- The actual adapter source: [`../src/biosymphony_ferm_doe/adapters/`](../src/biosymphony_ferm_doe/adapters/).
