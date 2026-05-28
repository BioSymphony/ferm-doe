# Simulator v2, Mechanistic Spec

> **STATUS: SPEC ONLY, NOT IMPLEMENTED.**
> This document describes a planned simulator v2; no production code exists yet.
> Implementation is gated on entry of a new campaign that needs the v2 surface.

**Status:** specification (not implementation) · 2026-05-16

This document specifies a second-generation titer simulator that closes the
four gaps surfaced by public-safe *E. coli* BL21 periplasmic-protein
media-optimisation stress tests. It is a **specification**; no code is
implemented here. The migration plan in §7 governs how the spec moves into
the adapter layer.

The simulator's role in BioSymphony Ferm DoE is unchanged: produce a
plausibility surface for the BO loop **until** the handoff packet returns
real assayed titers, at which point the simulator is retired in favour of a
surrogate fit on observed data. v2 raises the floor on plausibility; it
must not actively mislead the BO ranker into the kind of cost-model artifact
that ranks a chemically-implausible factor level highly because the v1
linear placeholder has no direct dose-response term for that factor.

---

## Contents

1. v1 to v2 framing and the four gaps
2. Per-factor dose-response curves
3. Osmotic stress penalty
4. Acetate-overflow / Crabtree-analog penalty
5. Mechanistic catabolite repression (lac operon trigger)
6. Composed v2 titer equation
7. Migration plan v1 to v2
8. Calibration disclosure, what v2 still cannot do

---

## 1 · v1 to v2 framing and the four gaps

v1 is a heuristic linear model with one nonlinear element (the lactose ×
glucose synergy bonus, gated by a `> 0` threshold). The public stress test
demonstrated that this structure cannot discriminate between 1 g/L and
30 g/L lactose. Because the lactose term is binary in v1, the cost-minimising
BO ranker selects the **lowest-cost lactose loading that still triggers
synergy**, which the v1 cost model misreads as 30 g/L (since 30 g/L lactose
is $0.027/L, cheaper than the equivalent glucose loading at $0.0007/g).
The artifact is a known failure mode of cost-per-mg objectives over
non-mechanistic titer surfaces.

v2 replaces each of these with a structurally grounded term:

| Gap (v1) | v2 response |
|---|---|
| No lactose dose-response, flat above zero | §2.1 Studier-type Westers-kinetic curve in g/L |
| No osmotic stress term | §3 BL21 tolerance threshold above baseline mOsm/kg |
| No acetate overflow / catabolite repression penalty | §4 Crabtree-analog μ-coupled penalty |
| Synergy threshold = `lactose > 0 AND glucose > 0` | §5 glucose-depletion-triggered switch (Monod-style) |

v2 is still a simulator. It is a **simplified** structural model with
hand-picked coefficients, not a digital twin. Its purpose is to give the BO
ranker a surface that respects the right shape: monotone in true growth
substrates over their useful range, peaked in the autoinduction window for
lactose, penalised by osmolarity and acetate, and gated by glucose
depletion for the lac promoter. §8 lists every phenomenon it still
deliberately omits.

---

## 2 · Per-factor dose-response curves

### 2.1 Lactose, Studier-type autoinduction kinetics

Lactose enters the cell via LacY (lactose permease) and is hydrolysed by
LacZ to glucose + galactose; the intracellular allolactose pool releases
LacI from the lac operator and induces target expression. The dose-response
is non-monotone: too little lactose under-induces, optimal autoinduction
sits in the 1–10 g/L window (Studier 2005; Hosseinzadeh 2020,
PMC7401236), and excess lactose produces no further induction benefit while
imposing osmotic and metabolic costs (the latter modelled separately in
§3–§4).

The proposed shape is a saturable induction term times a soft mid-range
optimum:

```
f_lactose(L) = T_lac_max · ( L / (K_lac + L) ) · exp( -((L - L_opt) / σ_L)^2 / 2 )
```

where:

- `L` = lactose concentration, g/L
- `T_lac_max` = maximum titer contribution from lactose induction, mg/L
  (initial seed: 60 mg/L)
- `K_lac` = half-saturation, g/L (initial seed: 1.0 g/L per Westers-type
  LacY uptake kinetics)
- `L_opt` = mid-range optimum, g/L (initial seed: 4.0 g/L per Studier
  ZYP-5052 nominal lactose; consistent with Menacho-Melgar 2024
  PMID 39059674)
- `σ_L` = optimum half-width, g/L (initial seed: 6.0 g/L)

The first factor (Hill / Michaelis form) captures rising induction below
saturation. The Gaussian envelope captures the empirical observation that
above ~10 g/L the autoinduction benefit plateaus and then drops, not
because more lactose hurts induction *per se*, but because the v2 spec
factors out the osmotic and acetate contributions into §3 and §4, leaving
the lactose curve itself to encode the induction window. The Gaussian is a
convenience form; a piecewise sigmoid-plateau would be equally valid and
the calibration plan in §7 allows either.

**References.**

- Studier FW. *Protein production by auto-induction in high-density
  shaking cultures.* Protein Expr Purif (2005) 41:207–234.
- Hosseinzadeh R *et al.*, autoinduction kinetics review,
  PMC7401236 (2020).
- Menacho-Melgar R *et al.*, lactose-only autoinduction,
  PMID 39059674 (2024).

**Lab-team disclosure.** v2 has `L_opt = 4 g/L`; the handoff packet
must continue to recommend sweeping lactose at three levels (1, 5, 10 g/L)
in the shake-flask tier before bioreactor commitment. The simulator's
optimum is a prior, not a prediction.

#### Sample pseudocode (lactose dose-response)

```python
import math

def lactose_titer_contribution(
    lactose_g_per_l: float,
    *,
    t_lac_max_mg_per_l: float = 60.0,
    k_lac_g_per_l: float = 1.0,
    l_opt_g_per_l: float = 4.0,
    sigma_l_g_per_l: float = 6.0,
    induction_gate: float = 1.0,
) -> float:
    """Lactose contribution to product titer (mg/L).

    Saturable Michaelis-Menten uptake × Gaussian autoinduction window.
    `induction_gate` is the catabolite-repression gate from §5 ∈ [0, 1].
    All other physical penalties (osmotic, acetate) are applied in §3-§4.

    Returns the titer contribution in mg/L. Not a prediction; a prior shape
    for BO surrogate ranking. Replace with surrogate fit once Phase 1
    ELISA returns observed titers.
    """
    if lactose_g_per_l <= 0.0:
        return 0.0
    uptake = lactose_g_per_l / (k_lac_g_per_l + lactose_g_per_l)
    window = math.exp(
        -((lactose_g_per_l - l_opt_g_per_l) ** 2)
        / (2.0 * sigma_l_g_per_l ** 2)
    )
    return t_lac_max_mg_per_l * uptake * window * induction_gate
```

This pseudocode shows the **shape** of the lactose term only. The
`induction_gate` multiplier comes from §5 (catabolite repression). All
v2 contributions then compose multiplicatively or additively per §6.

### 2.2 Glucose, Monod growth × Crabtree-analog penalty

Glucose is the BL21 preferred carbon source. The biomass contribution
follows a Monod term in batch and a half-fed Monod term in fed-batch; the
titer contribution is biomass × specific productivity, with specific
productivity suppressed by (a) catabolite repression of the lac operon
(§5) and (b) acetate burden (§4). The 3 Biotech 2025 review
(DOI 10.1007/s13205-025-04490-4) catalogues the acetate-overflow regime in
high-cell-density fermentation (HCDF) for *E. coli*; this is the
load-bearing structural reference.

```
f_glucose(G) = T_glc_max · (G / (K_glc + G)) · ϕ_acetate(G, μ) · (1 - I_cr(G))
```

where:

- `K_glc` = 0.05 g/L (typical *E. coli* glucose half-saturation;
  Monod constant)
- `T_glc_max` = 40 mg/L (carbon-flow titer ceiling from glucose alone,
  without induction; initial seed)
- `ϕ_acetate` is the acetate penalty defined in §4
- `I_cr(G)` is the catabolite-repression switch defined in §5

The Monod uptake is genuinely saturable around 0.1–0.2 g/L; the
useful dose-response in the design space is dominated by the catabolite
repression gate (which removes the lactose induction term when glucose is
present) and by the acetate penalty (which suppresses productivity above
~5 g/L residual glucose). The first-factor form is included for
mechanistic continuity.

**Reference.** *Acetate overflow metabolism in E. coli: regulation,
control, and metabolic engineering for high-density fermentation.*
3 Biotech (2025), DOI 10.1007/s13205-025-04490-4.

### 2.3 Glycerol, slow-uptake / HCDF-favourable term

Glycerol uptake in *E. coli* is gluconeogenic and substantially slower
than glucose uptake; it does **not** trigger catabolite repression of
the lac operon and is the textbook HCDF carbon source for IPTG- and
autoinduction-driven recombinant expression. Long *et al.* (2024,
PMID 38214104) provides a dFBA framework for glycerol HCDF in BL21 and is
the load-bearing reference for the proposed coupling.

```
f_glycerol(Gly) = T_gly_max · (Gly / (K_gly + Gly)) · ϕ_acetate(Gly, μ)
```

- `K_gly` = 0.1 g/L (Monod-form half-saturation; conservative)
- `T_gly_max` = 35 mg/L (initial seed; lower than glucose because
  growth rate is lower but titer ceiling is comparable due to reduced
  acetate burden, see §4)

Glycerol does **not** appear in the catabolite-repression gate
(§5). The lactose autoinduction window in §2.1 is preserved at
all glycerol concentrations. This is the structural answer to "why was
glycerol+lactose a favoured pair in the v1 training data": v2 keeps it
favoured, but now for the *right* reasons.

**Reference.** Long Q *et al.* *Dynamic flux balance modelling of
recombinant protein production in E. coli HCDF on glycerol.*
PMID 38214104 (2024).

### 2.4 IPTG, Hill saturation curve with temperature interaction

IPTG is a gratuitous inducer (non-metabolisable lactose analog) whose
intracellular concentration saturates the lac operon. The induction
response is a Hill curve in the 5–500 μM range; above ~1 mM the response
is flat or mildly inhibitory due to inclusion-body formation, particularly
at high temperatures.

```
f_iptg(I, T) = T_iptg_max · (I^n / (K_iptg^n + I^n)) · θ_temp(T, I)
```

where:

- `I` = IPTG concentration, mM
- `K_iptg` = 0.1 mM (typical T7-system half-saturation)
- `n` = 2 (Hill coefficient, moderate cooperativity)
- `T_iptg_max` = 50 mg/L (initial seed; assumes IPTG is the sole inducer)
- `θ_temp(T, I)` = inclusion-body penalty,
  `1.0 - max(0, (T - 25)/5) · max(0, (I - 0.5)/0.5)`
  (v1's `iptg_high_suppression_delta_mg_per_L` survives as the slope of
  this term; v2 makes it continuous instead of stepwise)

The mechanism: high IPTG at 28–30 °C accelerates ribosome loading and
saturates the periplasmic translocon (Sec/Tat), producing cytoplasmic
inclusion bodies and depressing **periplasmic** product titer specifically.
Below 28 °C the penalty is suppressed because folding chaperone capacity
keeps pace.

The IPTG term must be **additive** with the lactose term in v2, capped
by `T_induction_ceiling` (§6); they are alternative routes to the same
operator and the simulator should not double-count.

---

## 3 · Osmotic stress penalty

BL21 (and *E. coli* K-12 in general) tolerates a baseline of ~300 mOsm/kg
in defined media; growth slows above ~700 mOsm/kg, and titer collapses
above ~1000 mOsm/kg as cytoplasmic K⁺ and proline accumulation overwhelm
osmoregulation. A 30 g/L lactose loading contributes
~88 mOsm/kg from lactose alone (not catastrophic, but stacked on
ammonium sulfate, yeast extract / tryptone / corn-steep-liquor, and
glycerol it pushes the medium into the regime where titer is sensitive
to small additions).

### 3.1 Osmolarity composition

Cumulative osmolarity is the sum of solute contributions:

```
Π_total = Π_baseline_salts + Σ_i (c_i / M_i) · ν_i · 1000
```

where for each medium component `i`:

- `c_i` = concentration, g/L
- `M_i` = molar mass, g/mol
- `ν_i` = van't Hoff factor (effective particles per formula unit;
  lactose = 1, glucose = 1, glycerol = 1, ammonium sulfate = 3 in
  full dissociation but ~2.4 effective at fermentation ionic strength)

Initial seed values (mOsm/kg per g/L):

| Component | M_i | ν_i | mOsm/kg per g/L |
|---|---|---|---|
| Glucose | 180.16 | 1.0 | 5.5 |
| Glycerol | 92.09 | 1.0 | 10.9 |
| Lactose | 342.30 | 1.0 | 2.9 |
| Sucrose | 342.30 | 1.0 | 2.9 |
| Xylose | 150.13 | 1.0 | 6.7 |
| Ammonium sulfate | 132.14 | 2.4 | 18.2 |

Baseline salts (phosphates, magnesium, trace metals) contribute roughly
200–250 mOsm/kg in M9-derived media; a seed value of 220 mOsm/kg is the
v2 default.

### 3.2 Penalty function

```
ϕ_osm(Π) = 1 / (1 + exp( (Π - Π_50) / k_osm ))
```

- `Π_50` = 800 mOsm/kg (titer drops 50 % at 800 mOsm/kg above zero,
  conservative, mid-range of BL21 published tolerance)
- `k_osm` = 100 mOsm/kg (sigmoid width, 90 % → 10 % over 440 mOsm/kg)

The sigmoid form is preferred over a hard threshold because the BO
acquisition function needs a differentiable surface; sigmoid penalties
are well-conditioned for the GP-EI ranker in BoFire's SoboStrategy.

**Reference.** Osmolyte tolerance in *E. coli* BL21, Cayley & Record
(2003); modern HCDF practice surveyed in 3 Biotech 2025 review (loc. cit.).

**Effect on the example artifact.** At 30 g/L lactose alone, lactose
contributes 87 mOsm/kg, baseline contributes 220, ammonium sulfate at
0.5 g/L contributes 9, total ~316 mOsm/kg. This is well below the
sigmoid threshold; osmotic stress is **not** the dominant penalty against
the 30 g/L lactose recommendation. The dominant penalty is §2.1; lactose
at 30 g/L is far past `L_opt = 4 g/L`. The osmotic term becomes
load-bearing for compound recipes that pile lactose, glycerol, and
complex nitrogen together.

---

## 4 · Acetate-overflow / Crabtree-analog penalty

### 4.1 Mechanism summary

*E. coli* under aerobic excess-glucose conditions exhibits acetate
overflow, a metabolic regime where carbon flux through glycolysis
exceeds TCA-cycle capacity and the excess is excreted as acetate. The
acetate accumulates in the medium, lowers periplasmic pH, dissipates the
proton motive force, and suppresses recombinant protein expression
(particularly periplasmic-targeted recombinant proteins). Bhandari *et
al.* (bioRxiv 2026, DOI 10.64898/2026.02.02.703372) revisits this
phenomenon with modern flux-coupling analysis; the 3 Biotech 2025 review
(loc. cit.) summarises the engineering-relevant regime.

The behaviour is mathematically analogous to the Crabtree effect in
*S. cerevisiae*, a μ-coupled threshold above which fermentative
by-product flux rises sharply. We use the term "Crabtree-analog" in the
spec to denote the structural form without claiming the underlying
biology is the same enzyme system.

### 4.2 Penalty function

Specific growth rate μ is a derived quantity in v2 (computed from
glucose + glycerol + complex nitrogen contributions using a Monod-Pirt
form, see §6). The acetate penalty is:

```
ϕ_acetate(μ) = 1 / (1 + exp( (μ - μ_crit) / k_μ ))
```

- `μ_crit` = 0.35 h⁻¹ (μ above which acetate flux turns on; typical
  BL21 value at 37 °C, lower at 25–30 °C)
- `k_μ` = 0.05 h⁻¹ (sigmoid width)

Below μ_crit, ϕ_acetate ≈ 1.0 (no penalty). Above μ_crit, ϕ_acetate
drops toward 0 as acetate flux saturates the cytoplasmic stress
response.

The μ used here is a **simulated** μ computed from the chosen factors,
not an observed value. v2 documents this as a *prior shape*. The
calibration plan in §7 retires this surrogate as soon as off-gas OUR/RQ
or HPLC-measured acetate is available in the data return.

### 4.3 Coupling to glucose dose

Because glucose is the dominant μ driver, the acetate penalty appears in
the glucose contribution (§2.2) and in the glycerol contribution (§2.3,
weaker; glycerol is gluconeogenic and contributes less acetate per unit
biomass). The lactose contribution (§2.1) is **not** multiplied by
ϕ_acetate directly; lactose hydrolysis releases glucose, but at lactose
levels in the autoinduction window the intracellular flux is too small to
drive measurable acetate excretion. This is a deliberate v2 modelling
choice that the calibration plan (§7) flags for assessment once Phase 2
returns assayed acetate.

**Reference.** Bhandari N *et al.* *Acetate overflow in E. coli HCDF,
flux-coupled penalty on recombinant product titer.* bioRxiv (2026)
DOI 10.64898/2026.02.02.703372.

---

## 5 · Mechanistic catabolite repression, lac operon trigger

### 5.1 The v1 failure

v1's synergy bonus fires whenever `lactose > 0 AND glucose > 0`. This
is the opposite of the real lac operon behaviour: glucose **suppresses**
lac transcription via CRP-cAMP-mediated catabolite repression, and the
operon is only fully derepressed once glucose is depleted (or near-zero).
The Studier autoinduction paradigm is built around this: a small amount
of glucose is consumed first, biomass accumulates without induction
burden, glucose is depleted, lactose is then taken up, and induction
begins. The operon is *catabolite-repressed* while glucose is
available and *autoinduced* once glucose is gone.

v1's `> 0` threshold inverts this dynamic and rewards the simulator for
combinations the lab team would never run.

### 5.2 v2 proposal, Monod-style depletion switch

Define the catabolite repression gate as the inverse Monod function on
glucose:

```
I_cr(G) = G / (K_cr + G)
```

- `K_cr` = 0.5 g/L (typical concentration at which CRP-cAMP is
  half-suppressed; *E. coli* literature consensus 0.1–1 g/L)

Then in §2.1 the lactose contribution is multiplied by `(1 - I_cr(G))`:

- At `G = 0`: `1 - I_cr = 1.0` → lactose induction at full strength.
- At `G = 0.5 g/L`: `1 - I_cr = 0.5` → 50 % derepression.
- At `G = 5 g/L`: `1 - I_cr ≈ 0.09` → fully repressed.

The `induction_gate` parameter in the §2.1 pseudocode is precisely
`(1 - I_cr(G))`.

### 5.3 Autoinduction window, corrected synergy semantics

The classical Studier protocol uses ~0.05 % (w/v) = 0.5 g/L glucose plus
0.2 % (w/v) = 2 g/L lactose. v2 must reproduce this regime as favourable.
Under §5.2, at `G = 0.5 g/L` and `L = 4 g/L`:

- `(1 - I_cr(G=0.5)) = 0.5` (partial derepression)
- f_lactose at L=4 g/L is at its Gaussian peak

This means in a **batch** simulator, the trace-glucose Studier condition
shows ~50 % of the lactose ceiling. That under-rewards autoinduction
relative to its empirical performance. The Studier protocol *works*
because glucose is rapidly depleted in early growth; the time-average
of `I_cr(G(t))` is much lower than `I_cr(G_0)`.

v2 introduces a **time-resolved approximation** for batch protocols:

```
ḡ_cr = ∫_0^{t_harvest} I_cr(G(t)) dt / t_harvest
```

where `G(t)` is computed from a simple exponential depletion model:

```
G(t) = G_0 · exp( -μ · t / Y_xs )
```

with `Y_xs` = 0.5 g biomass / g glucose (BL21 textbook value).

For shake-flask runs at typical OD600 = 0.5 at induction and harvest at
24 h, the mean `I_cr` over the run drops to ~0.1 for `G_0 = 0.5 g/L`,
yielding `(1 - ḡ_cr) ≈ 0.9`, full autoinduction credit for the
Studier condition.

This is a **simplified** time-resolution layer. It is not a kinetic
solver. The Migration Plan in §7 flags whether v2 ships with the
instantaneous form (5.2) or the time-resolved form (5.3); the
time-resolved form is preferred for correctness but doubles the
simulator's parameter count.

**Reference.** Görke B & Stülke J. *Carbon catabolite repression in
bacteria: many ways to make the most out of nutrients.* Nat Rev
Microbiol (2008) 6:613–624. Plus Studier 2005 (loc. cit.).

---

## 6 · Composed v2 titer equation

The v2 titer prediction composes the per-factor contributions:

```
T_predicted(x) = clip(
    [ f_lactose(L; gate=1-ḡ_cr)
      + f_iptg(I, T_ind)
      + f_glucose(G)
      + f_glycerol(Gly)
      + complex_nitrogen_terms(YE, T, CSL)
    ] · ϕ_osm(Π_total(x))
      · ϕ_acetate(μ(x))
      · θ_temp(T_ind, I)
      · θ_folding(T_ind)
    , [titer_floor, titer_ceiling]
)
```

with multiplicative noise `T_observed = T_predicted · (1 + ε)`,
`ε ~ N(0, σ²)`, `σ = 0.15` carried over from v1.

The complex-nitrogen terms (yeast extract, tryptone, corn-steep liquor)
retain v1's linear-with-cap form; they are reasonably modelled as
amino-acid pools that displace amino-acid biosynthesis flux. v2 does not
change them; the load-bearing artifact is not driven by complex nitrogen.

The folding penalty `θ_folding(T_ind)` survives from v1 essentially
unchanged: BL21 periplasmic-protein folding is sensitive to induction
temperature, peaking near 25 °C and tailing off above 30 °C. The v1
form `1.0 - 0.02 · |T_ind - 25|` is acceptable.

### 6.1 Numerical safety

Both ϕ functions are sigmoids in [0, 1]. Their product is also in
[0, 1]. The additive sum of induction + growth terms is naturally
bounded above by the choice of `T_*_max`, so the multiplicative
penalty composition cannot produce non-physical negative or runaway
values. The final `clip` to `[titer_floor, titer_ceiling]` is a guard
rail, not the primary mechanism. This matters for GP-EI acquisition
functions, which need smooth derivatives; sigmoids are preferred over
piecewise-linear or hard thresholds throughout v2.

---

## 7 · Migration plan v1 to v2

v2 ships in three milestones. Each milestone is checkpointable, ranked
against a held-out set of literature observations, and reversible (v1
remains the documented fall-back).

### Milestone M1, refit v1 with continuous lactose, no other changes

- Replace the binary synergy bonus with the Hill-only form of §2.1
  (`f_lactose_simple(L) = T_lac_max · L / (K_lac + L)`), no Gaussian
  envelope, no catabolite gate.
- Hold all other v1 coefficients fixed.
- **Validation:** re-rank the seed D-optimal candidates; the 30 g/L
  lactose candidate must rank below the 1–5 g/L candidates
  on cost-per-mg.
- **Output:** `bofire_phase2_report_v2m1.json` with same schema as v1.

This is the minimal viable fix for the load-bearing artifact. It is reversible
and small. Planning packets that rely on this simulator should carry the same
sub-box refit caveat at lactose 1–10 g/L.

### Milestone M2, add osmotic + acetate penalties (mechanistic gates)

- Apply §3 and §4 as multiplicative gates on the M1 surface.
- Apply §5.2 (instantaneous catabolite repression), no time
  resolution yet.
- **Validation:** re-rank Phase 1; the glycerol-heavy candidates that
  ranked well in v1 must drop, but not so far that they fall below the
  1–5 g/L lactose autoinduction candidates. Cross-check against Long 2024
  (PMID 38214104) HCDF titer curves.
- Cross-check the predicted titer for a Studier-classic condition
  (0.5 g/L glucose + 4 g/L lactose, 25 °C, 0.5 mM IPTG): should land in
  60–80 mg/L periplasmic product (per Hosseinzadeh 2020 for periplasmic
  recombinant proteins).
- **Output:** `bofire_phase2_report_v2m2.json`.

### Milestone M3, time-resolved catabolite repression + Gaussian lactose window

- Replace the simple Michaelis lactose term in M1 with the full §2.1
  Gaussian-windowed form.
- Replace the §5.2 instantaneous gate with the §5.3 time-resolved
  approximation.
- **Validation:** the Studier 0.5 g + 4 g condition must now rank in
  the top 3 of any sub-box sweep.
- **Output:** `bofire_phase2_report_v2m3.json`. This is the v2 default
  going forward.

### Acceptance criteria across all milestones

- The instantaneous v1 surface remains computable for diff and audit.
- Every released milestone JSON includes a `simulator_version` field
  and the literature anchors it claims to honour.
- BoFire adapter (`adapters/bofire_strategy.py`) gains a
  `simulator_kind` argument and refuses to mix surfaces inside a
  single campaign.
- The handoff packet's CSV must carry `simulator_version` per row.

### Out of scope for v2

- Real-time off-gas-driven μ estimation (deferred to v3 when off-gas
  data exists in the dossier).
- Plasmid-copy-number dynamics (deferred, see §8).
- Strain-specific calibration (the spec assumes BL21(DE3); a
  K-12-derived strain or BL21 Star would need its own coefficient set).

---

## 8 · Calibration disclosure, what v2 still cannot do

v2 is a structural prior, not a digital twin. The following phenomena are
**deliberately** out of scope and should be flagged on every v2 report:

1. **Single-cell heterogeneity.** v2 is a population-mean simulator. It
   does not model the bimodal induction observed in single-cell
   fluorescence studies (Khlebnikov 2002, Megerle 2008), where a
   fraction of cells remain uninduced even at high IPTG. The handoff
   packet should not interpret v2 titers as cell-uniform.

2. **Plasmid copy number dynamics.** v2 assumes the plasmid backbone is
   fixed and the copy number is constant. pET / pBR322-class backbones
   show measurable copy number drift with media composition and growth
   rate. v2 cannot predict plasmid loss or yield instability across
   ≥24 h runs.

3. **Strain-specific calibration.** Initial seeds (μ_crit, K_lac,
   L_opt, Π_50) are nominal BL21(DE3) values. v2 does not auto-tune
   when the campaign manifest declares a different strain.

4. **Inclusion body partitioning.** v2's `θ_temp(T, I)` is a scalar
   penalty on periplasmic titer. It does not predict total expression
   (which may rise even as periplasmic falls). For QbD purposes the
   periplasmic projection is the right output, but the simulator
   cannot inform inclusion-body recovery decisions.

5. **Mixing / mass transfer at scale.** v2 is a 0-D well-mixed model.
   Scale-up issues (kLa-limited DO, CO₂ stripping, glucose pulse
   gradients) are handled in `docs/SCALE_BRIDGE.md` and are not
   simulated here.

6. **Time-dependent feed profiles.** v2 produces a scalar titer per
   recipe; the recipe declares the *concentration set point*, not the
   trajectory. Phase 3 fed-batch recipes need an additional simulator
   class (out of scope for v2).

7. **Strain-engineering interventions.** Knockouts (ΔackA, ΔpoxB
   for acetate reduction; ΔlacY for IPTG control) shift μ_crit, K_cr,
   and K_iptg substantially. v2 does not encode the strain-engineering
   library.

8. **Quality attributes other than titer.** Aggregation, glycoform,
   N-terminal heterogeneity, none are modelled. v2 produces a single
   periplasmic mg/L number. The QTPP table in the handoff packet must
   continue to declare every CQA the simulator silently does not address.

Every v2 report must reproduce items 1–8 verbatim in its
`non_claim` field. The simulator is a planning surface; the lab team
is the source of truth.

---

## Implementation hooks

- v2 lives in `src/biosymphony_ferm_doe/simulators/` (new module).
- BoFire adapter exposes `simulator_kind: v1_linear | v2m1 | v2m2 | v2m3`.
- The `simulator_coefficients` block in `bofire_phase2_report.json`
  grows to include the v2-specific seeds documented above.
- The handoff-packet `design_table.csv` gains a `simulator_version`
  column.

None of these are implemented by this document.

---

## References

- Studier FW (2005) *Protein Expr Purif* 41:207–234.
- Hosseinzadeh R *et al.* (2020) PMC7401236.
- Menacho-Melgar R *et al.* (2024) PMID 39059674.
- 3 Biotech (2025) *Acetate overflow metabolism in E. coli HCDF.*
  DOI 10.1007/s13205-025-04490-4.
- Long Q *et al.* (2024) PMID 38214104, dFBA glycerol HCDF.
- Bhandari N *et al.* (2026) bioRxiv DOI 10.64898/2026.02.02.703372.
- Görke B, Stülke J (2008) *Nat Rev Microbiol* 6:613–624, catabolite
  repression review.
- Cayley S, Record MT (2003), osmolyte tolerance in *E. coli*.
- Khlebnikov A *et al.* (2002), Megerle JA *et al.* (2008),
  single-cell induction heterogeneity (cited for §8 only).

---

**Issued by:** simulator-spec authoring pass · 2026-05-16
**Next review:** at Milestone M1 completion, refit the seed candidates
and update the candidate-ranking caveat with the new ranking.
