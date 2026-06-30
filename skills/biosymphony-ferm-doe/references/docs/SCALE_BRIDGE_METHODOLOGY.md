# Scale-Bridge Methodology, Shake Flask to 1–2 L Stirred-Tank Bioreactor for *E. coli* BL21 Periplasmic Expression

> Companion to `docs/SCALE_BRIDGE.md` (framework).
> Status: methodology reference; numerical ranges are literature-grounded engineering priors,
> not vessel-qualified setpoints. Vessel-specific kLa-vs-RPM characterization remains
> required before declaring scale-down qualified per ICH Q11.

This document supplies the **specific equations, coefficient values, and acceptable
ranges** used by `scale-recipe` derivation and by the `scale_down_qualification`
packet contract. It targets the *E. coli* BL21 periplasmic-protein expression arc
(250–500 mL Erlenmeyer / Ultra-Yield shake flask to 1–2 L bench stirred-tank
bioreactor with Rushton or Rushton+pitched-blade impeller stack).

The skill's `scale_recipe.json` derivation reads the constants tabulated here through
`scale_context.correlation_overrides`; the defaults baked into the engine are the values
in §2.1 and §3 below.

---

## 1. Scope and operating regime

| Endpoint | Working volume | Aspect ratio H/D | Impeller(s) | Sparger | Aeration | Agitation |
|---|---|---|---|---|---|---|
| Shake flask (small) | 25–100 mL in 250–500 mL Erlenmeyer (1:5–1:10 fill) | n/a (orbital) | n/a (orbital throw 25 or 50 mm) | n/a (headspace) | passive, foam-stopper headspace turnover | 200–300 rpm |
| Bench STR (target) | 1.0–1.5 L in 2 L vessel | 1.5–2.0 | 1× or 2× Rushton (D/T ≈ 0.33–0.40); optional axial upper | Ring sparger or open pipe below lowest impeller | 0.5–2.0 vvm air; O₂ enrichment as required | 400–1200 rpm with DO cascade |

**Regime classification.** *E. coli* BL21 under fed-batch in this volume class is a
coalescing-to-weakly-non-coalescing aqueous broth at modest viscosity (≤ 5 mPa·s
through DCW ≈ 60 g/L), with turbulent Reynolds number Re = ρND²/μ ≈ 10⁵–10⁶ at typical
RPM. Fully turbulent for all correlations below.

---

## 2. Equation set

### 2.1 Van't Riet kLa correlation (STR)

The canonical relation for volumetric oxygen mass transfer in a sparged stirred tank
([Van't Riet 1979](https://pubs.acs.org/doi/abs/10.1021/i260072a001),
codified in `docs/SCALE_BRIDGE.md` §"Built-in correlations"):

```
kLa = C · (P/V)^α · vg^β            (Eq. 1)
```

with kLa in [s⁻¹] (multiply by 3600 for h⁻¹), P/V in [W/m³], superficial gas velocity
vg in [m/s] (vg = Q_gas / A_cross-section).

| Medium regime | C | α | β | Source |
|---|---|---|---|---|
| **Coalescing (water, dilute glucose)** | **0.026** | **0.4** | **0.5** | Van't Riet 1979 |
| **Non-coalescing (≥ 0.1 M salt, peptone, complex protein-rich)** | **0.002** | **0.7** | **0.2** | Van't Riet 1979 |
| Microbial fermentation (mixed-coalescence broth, *E. coli* fed-batch) | ≈ 0.01 | 0.55 | 0.35 | Engineering rule, span of the two above |

**Practical pick for BL21 periplasmic media.** A semi-defined batch with
glucose/glycerol + tryptone + (NH₄)₂SO₄ + Mg/trace salts is **weakly non-coalescing
once cells are present** (cell density and DOC suppress bubble coalescence). Use
**C = 0.002, α = 0.7, β = 0.2** as the prior and treat the kLa estimate as ±50%
until a sulfite or gassing-out kLa measurement is taken in the actual vessel. The
campaign default is locked in `scale_context.correlation_overrides.kla` if a vessel
characterization run is available; otherwise the engine uses the coalescing prior
and emits a YELLOW warning in `scale_recipe.json`.

### 2.2 Power input

Ungassed power for a single impeller in turbulent flow:

```
P = N_p · ρ · N³ · D⁵                (Eq. 2)
```

with P [W], N_p the impeller power number [-], ρ liquid density [kg/m³], N impeller
speed [rev/s], D impeller diameter [m]. The skill's default power numbers (engine
`scale_recipe.py`):

| Impeller | N_p (ungassed) | N_p,g/N_p (gassed) at typical Q_gas | Comment |
|---|---|---|---|
| Rushton 6-blade disk | **5.5** | 0.5–0.7 | Workhorse for *E. coli*; high shear, high local ε |
| Pitched-blade 4-blade (PBT-45°) | 1.27 | 0.7–0.8 | Axial flow; good top impeller for bulk pump |
| Marine propeller | 0.35 | ~0.8 | Light blending only |
| Lightnin A310 | 0.30 | ~0.9 | Hydrofoil; low shear, low power |
| Lightnin A315 | 0.84 | ~0.8 | Hydrofoil; *E. coli* OK |

Gassed P/V is then `P_gassed/V_working`. For dual-impeller stacks (lower Rushton +
upper axial) add the two impeller powers; this is the typical 2-L STR configuration
for HCDF *E. coli*.

### 2.3 Mixing time (Nienow / Grenville-Nienow)

For a single Rushton impeller, fully turbulent regime,
[Nienow 1997](https://www.sciencedirect.com/science/article/abs/pii/S1369703X05002275)
and the [Grenville-Nienow consensus correlation](https://www.sciencedirect.com/science/article/abs/pii/S0009250911002089)
for H/T ≈ 1:

```
N · t_m95 = c_m                       (Eq. 3a, single-impeller form)

t_m95 ≈ 5.9 · T^(2/3) · (P/V)^(-1/3) · ρ^(1/3)    (Eq. 3b, Grenville-Nienow)
```

with t_m95 the time to reach 95% homogeneity [s], N rotation [rev/s], T vessel
diameter [m], P/V [W/m³], ρ [kg/m³], and c_m an impeller-dependent constant. The
skill's defaults (engine `scale_recipe.py`):

| Impeller | c_m (Nienow form) | Typical t_m95 at 800 rpm, 2 L | Comment |
|---|---|---|---|
| Rushton | 38 | ~3–4 s | Compartmentalized; multi-Rushton gives ~2× single |
| PBT-45° | 14 | ~1.5 s | Better axial blending |
| Lightnin A310 | 6.5 | ~0.7 s | Best mix time per unit P |

**Acceptable t_m95 for *E. coli* HCDF**: ≤ 10 s at the bench scale and ≤ 30 s at
pilot. Above 30 s, glucose/feed-pulse heterogeneity drives overflow metabolism within
**2 s** of exposure to a high-substrate / low-O₂ zone
([Vasilakou et al. 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7260802/);
[Käß et al. 2014, gradient modelling](https://researchgate.net/publication/326993600);
[Anane et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8223794/)). Formate,
acetate, lactate, and non-canonical amino acid accumulation
(norvaline, norleucine) follow within minutes. **For 2 L bench STR with 1.0–1.5 L
working volume, single Rushton at ≥ 400 rpm comfortably hits t_m95 ≤ 10 s; mixing
time is not a binding scale-bridge constraint between 50 mL flask and 2 L STR. It
becomes binding above 50 L and dominant above 1 m³.**

### 2.4 Tip speed and shear (Kolmogorov microscale)

Impeller tip speed:

```
v_tip = π · N · D                     (Eq. 4)
```

with v_tip [m/s], N [rev/s], D [m]. For *E. coli* the upper safe limit is ~2.5 m/s
([Garcia-Ochoa & Gomez 2009](https://www.sciencedirect.com/science/article/abs/pii/S0734975008001110)
review of microbial fermentation engineering); shear damage is not the binding
constraint for *E. coli* (rod, ~1×2 µm, robust outer membrane) until pellet
disintegration or periplasmic leakage is observed, typically only above v_tip ≈
3.5–4 m/s in the bench class.

Kolmogorov microscale (smallest turbulent eddy):

```
η = (ν³ / ε)^(1/4)                    (Eq. 5)
```

with η [m], ν kinematic viscosity [m²/s] (≈ 10⁻⁶ m²/s for water), ε specific energy
dissipation rate [W/kg ≈ m²/s³]. Local ε near a Rushton blade can be ~50× the
volume-average P/V/ρ ([Cellbase scale-up review](https://cellbase.com/blogs/news/scaling-bioreactors-shear-stress-modelling-techniques)).

**E. coli sensitivity threshold**: eddies in the 10–50 µm range can interact with
filamentous or aggregated cell forms; for individual BL21 cells (~1 µm) shear is
**not** the binding constraint at η ≥ 5 µm. At 1000 rpm, D = 50 mm Rushton in 2 L
water:

- volume-average ε = (P/ρV) ≈ 3 W/kg → η ≈ 24 µm (volume-average)
- local ε near tip ≈ 150 W/kg → η ≈ 9 µm (worst case)

Both are above the ~5 µm threshold where rod-form *E. coli* show membrane-leakage
effects ([Gao et al. 2020 BL21 rheology study](https://www.researchgate.net/publication/330010017),
[Mass transfer & rheology in STR for BL21](https://link.springer.com/article/10.1007/s12257-020-0028-3)).
**Shear is therefore NOT the binding scale-bridge constraint for BL21 periplasmic expression at the
2 L scale.** The binding constraint is kLa for periplasmic Dsb-pathway redox
maintenance.

### 2.5 Superficial gas velocity, VVM, and sparger

Superficial gas velocity:

```
vg = Q_gas / (π · T² / 4)              (Eq. 6)
```

with vg [m/s], Q_gas [m³/s], T tank diameter [m]. VVM (volume per volume per minute)
= Q_gas (at STP) / V_working.

**Operational ranges for *E. coli* bench STR**
([Riesenberg & Guthke 1999](https://link.springer.com/article/10.1007/s002530051506),
[Thermo Fisher fermentation app note](https://documents.thermofisher.com/TFS-Assets/BPD/Application-Notes/scale-up-microbial-fermentation-using-recombinant-ecoli-app-note.pdf),
[Sartorius HCDF protocol](https://www.sartorius.com/download/10104/appl-biostat-d-dcu-high-cell-density-cultivation-e-coli-sbt1015-e-data.pdf)):

| Parameter | Range | Notes |
|---|---|---|
| VVM | **0.5–2.0** (start 1.0) | > 2 vvm risks flooding the impeller and foaming |
| Q_gas at 2 L, 1.0 vvm | 1.0 SLPM | Increase with O₂ enrichment instead of air past 1.5 vvm |
| vg (at 1 vvm, 2 L STR, T ≈ 0.12 m) | 1.5×10⁻³ m/s | Well below the flooding limit of ~0.04 m/s for a 50 mm Rushton |
| Flooding criterion (Fr_g) | Q_gas / (N · D³) ≤ 0.025 | Above this the impeller cavitates; gassed N_p drops sharply |

**Sparger choice for *E. coli*.** Open-pipe and ring (drilled-hole) spargers are
standard for microbial fermentation; the impeller, not the sparger, dominates bubble
breakup at *E. coli* P/V (≥ 1000 W/m³). Microporous sintered spargers (kLa 150–200 h⁻¹)
are favored for mammalian cell culture, not *E. coli*; they foul rapidly in microbial
broths
([BPI Bioreactor Scale-Up Part 4](https://www.bioprocessintl.com/bioreactors/lessons-in-bioreactor-s-scale-up-part-4-physiochemical-factors-affecting-oxygen-transfer-and-the-volumetric-mass-transfer-coefficient-in-stirred-tanks)).
**Recommendation: ring sparger or open pipe with 6–12 × 1 mm holes, mounted below the
lowest Rushton, gives kLa 100–500 h⁻¹ at 1–2 L scale.**

### 2.6 Shake-flask kLa (Maier–Büchs)

For an orbital shake flask, kLa cannot be analytically derived from `P/V·vg` because
there is no sparger and the gas-liquid surface is the shaken film. The
Maier–Büchs correlation
([Maier, Losen & Büchs 2004](https://www.sciencedirect.com/science/article/abs/pii/S1369703X04000222))
expresses kLa as a function of shaking frequency n [rpm], flask volume V_F, fill
volume V_L, shaking diameter d_s, and a hydrodynamic mass-transfer prefactor:

```
kLa = 6.67×10⁻⁶ · n^1.16 · V_L^(-0.83) · d_s^0.38 · V_F^0.27      (Eq. 7, approximate)
```

with kLa [s⁻¹], n [rpm], volumes in [mL], d_s in [cm]. Worked numerical examples:

| Flask | Fill | n [rpm] | d_s [cm] | Predicted kLa [h⁻¹] | Source check |
|---|---|---|---|---|---|
| 250 mL Erlenmeyer | 50 mL | 200 | 2.5 | ~15 (low-shake-diameter regime) | matches Maier-Büchs survey |
| 500 mL baffled (PreSens) | 100 mL | 200 | 5.0 | **~133** | [Krause et al. 2010 measurement](https://pmc.ncbi.nlm.nih.gov/articles/PMC8718739/) |
| 250 mL Ultra-Yield | 50 mL | 300 | 2.5 | 80–200 (vendor data) | [HTS Labs Ultra-Yield FAQ](https://htslabs.com/faquyf) |
| 250 mL Erlenmeyer | 10 mL | 750 | 2.5 | **~650 (OTRmax ≈ 135 mmol/L/h)** | upper bound, Klöckner & Büchs |

**Translation:** with a 5-cm orbital throw, baffled 500 mL flask at 200 rpm and 100 mL
fill, kLa at the flask scale **already matches the lower end of the 2 L STR range
(100–500 h⁻¹)**. Unbaffled 250 mL flasks at 200 rpm with a 2.5 cm orbital throw run
at kLa 15–30 h⁻¹ and **will oxygen-limit BL21 above DCW ≈ 5–10 g/L**, a known cause
of failed shake-flask to bioreactor transitions for periplasmic-protein expression.

### 2.7 Shake-flask power input (Büchs–Klöckner)

For unbaffled shake flasks
([Büchs et al. 2000a,b](https://pubmed.ncbi.nlm.nih.gov/10799983/);
[Peter, Suzuki & Büchs 2006, baffled flasks](https://www.sciencedirect.com/science/article/abs/pii/S0009250905009632)):

| Flask | n [rpm] | P/V [W/m³] |
|---|---|---|
| 250 mL unbaffled, 50 mL fill, 2.5 cm throw | 200 | 100–300 |
| 250 mL unbaffled, 50 mL fill, 2.5 cm throw | 300 | 500–1500 |
| 250 mL baffled, 50 mL fill, 2.5 cm throw | 200 | 1000–3000 |
| 250 mL baffled, 50 mL fill, 5 cm throw | 300 | up to 7000 (highest reported) |

**Order-of-magnitude span**: shake-flask volumetric power is **0.1–7 kW/m³**,
overlapping the bench STR P/V range. Baffled flasks at ≥ 200 rpm on a 5-cm throw
are within ~3× of the 2 L STR P/V, which is one reason they are the preferred
scale-down vessel for *E. coli*, provided headspace O₂ supply is adequate.

---

## 3. P/V matching: when to use it as the primary criterion

P/V is the canonical scale-up criterion for microbial fermentation when **oxygen
transfer is the rate-limiting biology**, which is true for HCDF *E. coli*. The
classical rule of thumb is **constant P/V from bench to pilot** as long as Reynolds
number and impeller flooding limits are respected.

**Typical P/V envelopes**:

| Scale | P/V [W/m³] | Notes |
|---|---|---|
| Shake flask (baffled, 200 rpm, 5-cm throw) | **1000–3000** (peak 7000) | Span overlaps STR; not constant |
| Shake flask (unbaffled, 200 rpm, 2.5-cm throw) | **100–500** | Often O₂-limited for *E. coli* > OD 10 |
| 2 L STR, *E. coli* HCDF, 600–1200 rpm, 2 Rushton | **1000–5000** | Typical operating window |
| 100 L pilot, *E. coli*, geometric similarity | 500–3000 | Constant P/V scale-up target |
| 10 m³ production | 500–2000 | Below this P/V, oxygen-limited |
| Mammalian 2000 L | 10–100 | Shear-limited; different regime entirely |

**Decision rule.**
- **MATCH P/V** between flask and STR when designing for OTR-equivalent oxygen
  supply (the main case for BL21 periplasmic expression). Target STR P/V ≈ 1500–3000 W/m³ during the
  high-OUR phase (post-induction).
- **DO NOT match P/V** as the sole criterion if shear is the binding constraint
  (mammalian, hybridoma, fragile organelles). Use tip speed or kLa instead.
- For *E. coli* the most defensible criterion ordering is:
  **(a) kLa primary → (b) P/V secondary → (c) tip-speed ceiling check → (d) mixing
  time check**, exactly the ordering encoded in `scale_context.bridge_strategy`
  defaults.

---

## 4. What to MATCH versus what CHANGES between scales

### 4.1 Match (transferable factors, `bridge_factors.transferable`)

| Parameter | Target | Tolerance | Why |
|---|---|---|---|
| Temperature | 30 °C (growth) → 25–30 °C (induction) | ± 0.5 °C | Biology, ribosome efficiency, IPTG induction kinetics |
| pH | 7.0 ± 0.2 | ± 0.2 in STR; **open-loop ± 0.5 in flask** | Periplasmic Dsb pathway pH-sensitive |
| DO setpoint | ≥ 30% saturation | ≥ 30% | Below this, Dsb redox / disulfide formation drop |
| Inoculum OD₆₀₀ | 0.05–0.1 | ± 0.02 | Growth phase phase-locking |
| Induction OD₆₀₀ | 0.6–1.0 (typical) | ± 0.1 in STR, ± 0.2 in flask | Determines biomass at induction |
| Inducer concentration (IPTG / lactose) | as designed | exact | Factor of the DoE |
| Carbon source identity & concentration | as designed | exact | Factor of the DoE |
| Antifoam class | identical (PPG 2000 or Antifoam 204) | qualitative | Antifoam interferes with kLa; keep class constant |

### 4.2 Change (re-tuned at each scale, `bridge_factors.needs_retuning`)

| Parameter | Shake flask | 2 L STR | Acceptable change |
|---|---|---|---|
| Agitation (RPM) | 200–300 rpm orbital | 400–1200 rpm Rushton | Re-derived from kLa target |
| Aeration | passive (headspace turnover) | 0.5–2 vvm sparged | Re-derived from kLa target |
| Mixing time | < 5 s (effectively well-mixed at flask scale) | 3–10 s at 600–1200 rpm | Both well below 30-s overflow threshold |
| Kolmogorov microscale η | not applicable (no impeller) | 8–30 µm | Above 5 µm safety threshold |
| Volume turnover (pumping) | n/a | ≥ 5 turnovers/min | At 1000 rpm Rushton, ~30 turnovers/min |
| Feed strategy | not feasible (batch only) | exponential or DO-stat fed-batch | Cannot be matched; feed enables the high-titer regime |

### 4.3 Not applicable (`bridge_factors.not_applicable`)

| Parameter | Comment |
|---|---|
| Off-gas O₂/CO₂ monitoring | STR-only (off-gas analyzer); not feasible in shake flask |
| pH cascade with base addition | STR-only; flask is open-loop |
| DO cascade (agitation → O₂ enrichment) | STR-only |
| Real-time OUR/CER | STR-only |
| Continuous foam break | flask uses surfactant only |

---

## 5. Acceptable per-scale ranges (engineering recipe inputs)

Locked defaults the engine uses when `scale_context` does not override them. These
values match the priors in `scale_recipe.py` and feed the scale-recipe derivation.

### 5.1 Shake flask scale-down model (250–500 mL baffled, 5-cm throw recommended)

| Parameter | Recommended | Min | Max | Source |
|---|---|---|---|---|
| Flask volume | 250 or 500 mL | 125 mL | 1 L | Geometry constraint |
| Fill volume / Vflask | 1:5 | 1:10 | 1:4 | Higher fill = lower kLa; > 1:4 risks splash and O₂-limitation |
| Shaking frequency | 220–280 rpm | 180 rpm | 350 rpm | < 180 = under-aerated; > 350 = splash and out-of-phase mixing |
| Orbital throw | 50 mm | 25 mm | 50 mm | 50 mm gives ~3× the kLa of 25 mm at same n |
| Baffles | 4-baffle preferred for HCDF | 0 (unbaffled) | 4 | Unbaffled OK for low-OD growth screens |
| Closure | foam stopper or AirOtop / membrane | n/a |, | Sealed caps will gas-deplete |
| Target kLa | 80–150 h⁻¹ | 50 | 200 | Below 50 h⁻¹ = O₂-limited for BL21 above OD ≈ 5 |

### 5.2 2 L STR (1.0–1.5 L working volume)

| Parameter | Recommended | Min | Max | Source |
|---|---|---|---|---|
| Vessel | 2 L glass with jacket | n/a |, | Sartorius / Eppendorf / Applikon class |
| H/D | 1.7 | 1.3 | 2.5 | Standard bench |
| Working volume | 1.2 L (60% full) | 0.8 L | 1.5 L | Headspace for foam |
| Impeller | 2× Rushton (or Rushton + PBT upper) | 1× Rushton | 2× Rushton | Single OK at < 1 L; dual for HCDF |
| Impeller diameter D | 50 mm (D/T ≈ 0.4) | 40 mm | 60 mm | D/T 0.3–0.5 |
| Impeller spacing | 1.0 × D | 0.8 D | 1.5 D | Below 0.8 D = stack interaction |
| Baffles | 4 × T/12 wide, full height | n/a |, | Standard |
| Sparger | Ring or open pipe under lowest impeller, 6–12 × 1 mm holes | n/a |, | Avoid sintered for *E. coli* |
| Agitation | 400–1200 rpm (DO cascade) | 300 rpm | 1500 rpm | Cascaded to DO 30% |
| Aeration | 1.0 vvm air, O₂ enrichment to maintain DO ≥ 30% | 0.5 vvm | 2.0 vvm | Above 2 vvm flooding risk |
| Target kLa | 200–500 h⁻¹ at high-OUR phase | 100 | 800 | Linek-Vacek 1981 supports up to 800 h⁻¹ |
| Target P/V (high-OUR) | 1500–3000 W/m³ | 500 | 5000 | Coalescing-prior dependent |
| Tip speed | 2.0–2.5 m/s | 1.5 m/s | 3.0 m/s | *E. coli* ceiling |
| t_m95 | 3–8 s | n/a | 30 s | Above 30 s overflow risk |
| DO setpoint | 30% | 20% | 50% | Below 20% Dsb pathway impaired |
| pH | 7.0 ± 0.2 (NH₄OH for base, H₃PO₄ for acid) | 6.7 | 7.3 | Closer than 0.1 risks oscillation |

---

## 6. Worked example: shake flask to 2 L STR for BL21 periplasmic expression

**Scale-down model**: 500 mL baffled flask, 100 mL fill, 220 rpm, 50-mm throw.

- kLa (Eq. 7) ≈ **130 h⁻¹**
- P/V (Büchs–Klöckner) ≈ **2 kW/m³** (peak local; volume-averaged ~1 kW/m³)
- t_m ≪ 5 s
- Headspace O₂ supply caps OTR ≈ 50 mmol/L/h
- Safe operating window: DCW ≤ 15 g/L before O₂-limitation

**Scale-up target**: 2 L STR, 1.2 L working volume, 2 × Rushton (D = 50 mm), open
ring sparger, 1.0 vvm air, DO 30% cascade.

To MATCH the flask kLa floor of 100–150 h⁻¹ at the early-induction window
(P/V coalescing prior, C=0.026, α=0.4, β=0.5):

- vg = 1 vvm × 1.2 L/min / (π · 0.06²) ≈ 7.1×10⁻³ m/s → vg^0.5 ≈ 0.084 (SI units)
- target kLa = 0.025 s⁻¹ (90 h⁻¹) → (P/V)^0.4 = kLa / (C · vg^0.5) =
  0.025 / (0.026 · 0.084) ≈ 11.4 → **P/V ≈ 530 W/m³** (RPM ≈ 600)

To MATCH the high-OUR phase target kLa of 400 h⁻¹ (post-induction, OD 40+):

- target kLa = 0.11 s⁻¹ → **P/V ≈ 6500 W/m³** (RPM ≈ 1100, gassed N_p ≈ 3.5)

These are the kinds of values the engine writes to `scale_recipe.json` for a campaign
at this shape, with a recipe-warning if `engineering_targets.power_per_volume` declared
in the manifest disagrees by > 20%.

---

## 7. Risks specific to BL21 periplasmic-protein scale-bridging

Ordered by likely impact on cost-per-mg.

1. **kLa shortfall in the shake-flask phase** → masked O₂-limitation suppresses
   periplasmic Dsb-pathway redox cycling → disulfide misformation /
   inclusion-body partitioning → titer reads correlate with **headspace O₂
   availability**, not media composition. *Mitigation*: baffled flask, 5-cm
   throw, fill ≤ 1:5, sulfite-method kLa calibration of the actual shaker before
   the screening campaign begins.

2. **Substrate-pulse / overflow metabolism at the bioreactor scale** → glucose
   feed at the surface near the impeller creates a high-glucose / low-O₂ pocket.
   *E. coli* commits to mixed-acid fermentation within 2 s of exposure. At 2 L
   STR with t_m95 ≤ 10 s the risk is small; at pilot it dominates.
   *Mitigation*: sub-surface feed addition, feed rate ≤ µ_max·X·V, monitor acetate
   directly.

3. **Acetate accumulation independent of mixing** → above µ ≈ 0.3 h⁻¹ on glucose,
   BL21 commits to overflow regardless of O₂. *Mitigation*: glucose-limited
   fed-batch, glycerol substitution, lactose induction.

4. **pH gradient near base addition port at 2 L** → 25% NH₄OH addition creates a
   local pH spike near the sparger; pelB cleavage and Dsb both pH-sensitive in
   the 7.5–8.0 window. *Mitigation*: subsurface dip-tube for base, dilute base to
   5%, paired pH cascade with slow ramp.

5. **DO probe lag** → polarographic DO probes have ~30-s response time. At
   bench scale, slow-response DO control can cause DO oscillation that masquerades
   as kLa instability. *Mitigation*: optical DO probe (Hamilton VisiFerm), pre-
   calibrated probe-response qualification per ICH Q11.

6. **Antifoam interference with kLa** → silicone antifoams reduce kLa by 30–50%
   at typical dosing. *Mitigation*: PPG 2000 at minimum titrated dose; consume
   the same antifoam class at both scales.

7. **Inducer leakage / cleavage differences**. IPTG behaves identically across
   scales but lactose induction (which the campaign tests) depends on lactose
   permease (LacY) activity which is glucose-repressed. Residual glucose at
   induction differs between scales because of feed-strategy differences.
   *Mitigation*: ensure glucose depletion confirmed before lactose addition at
   both scales.

8. **Foam → kLa collapse / cell entrainment** → foam at high agitation traps
   biomass at the surface. *Mitigation*: defoamer dosing on level-sensor trigger;
   never run > 70% working volume during high-OUR phase.

---

## 8. Engineering targets the campaign should declare in `scale_context`

For a typical 500 mL baffled flask → 2 L STR scale-bridge (`from_scale: shake_flask_500mL_baffled`
to `to_scale: bench_str_2L`):

```yaml
bridge_strategy:
  primary_criterion: kLa
  secondary_criteria: [p_per_v, mix_time]
  rationale: |
    Oxygen transfer is the rate-limiting biology for BL21 periplasmic-protein
    expression. kLa is matched at the high-OUR phase (post-induction OD ≥ 20).
    P/V tracks kLa as the secondary criterion. Tip speed and mixing time are
    well within safety windows at the 2 L scale and are checked, not matched.

correlation_overrides:
  kla:
    C: 0.002    # non-coalescing prior; refine after vessel sulfite calibration
    alpha: 0.7
    beta: 0.2
  power_number:
    rushton: 5.5
    pbt45: 1.27
  mix_time_constant:
    rushton: 38
    pbt45: 14
  liquid_density_kg_per_m3: 1000

engineering_targets:
  from_scale:    # 500 mL baffled flask
    kla_per_h: 130
    p_per_v_w_per_m3: 1500    # peak local; volume-avg ~1000
    tip_speed_m_per_s: null   # not applicable
    mix_time_s: 3
    do_setpoint_pct: null     # open-loop
    vvm: null
  to_scale:      # 2 L STR
    kla_per_h: 400            # high-OUR phase target
    p_per_v_w_per_m3: 2500
    tip_speed_m_per_s: 2.3
    mix_time_s: 6
    do_setpoint_pct: 30
    vvm: 1.0

recapitulation_criterion:
  metric: composite_titer_and_DO_shape
  formula: |
    (measured_titer_str / measured_titer_flask) ×
    (1 - DO_trajectory_distance_normalized)
  tolerance: ≥ 0.85
  evidence_required:
    - measured kLa at both scales (sulfite or gassing-out)
    - paired DO trajectories from at least 3 matched runs
    - paired titer + soluble fraction
```

---

## 9. The three most-load-bearing equations

For the BL21 periplasmic scale-bridge, in order of impact on the engineering decision:

1. **Van't Riet kLa** (Eq. 1): `kLa = C·(P/V)^α·vg^β`, with C, α, β picked from
   the coalescence regime. **This single equation sets the RPM and air-flow
   targets of the bioreactor.**
2. **Shake-flask kLa, Maier–Büchs** (Eq. 7): `kLa = 6.67e-6 · n^1.16 · V_L^-0.83
   · d_s^0.38 · V_F^0.27`. **This is what determines whether the scale-down
   model is meaningful at all.** If the flask kLa is < 50 h⁻¹, the screening
   campaign measures oxygenation, not media.
3. **Mixing time, Grenville-Nienow** (Eq. 3b): `t_m95 ≈ 5.9·T^(2/3)·(P/V)^(-1/3)
   ·ρ^(1/3)`. **The check that confirms the scale-bridge does not need a
   sub-surface feed re-design.** At ≤ 2 L it is reassuring; above 50 L it
   dominates.

---

## 10. Biggest scale-bridge risk for BL21 periplasmic expression

**The shake-flask scale-down model masks oxygen limitation**, and the simulator's
literature-prior titers in `predicted_titer_mg_per_L` cannot tell apart a
poor-recipe outcome from a poor-aeration outcome at the small scale.

Concretely: a 250 mL unbaffled flask at 200 rpm with a 25-mm orbital throw has
kLa ≈ 15–30 h⁻¹ and OTR_max ≈ 5–10 mmol O₂/L/h. *E. coli* BL21 at µ ≈ 0.3 h⁻¹ has
OUR ≈ 4 mmol O₂/g·DCW·h, so the flask oxygen-limits at DCW ≈ 1.5–3 g/L
(OD₆₀₀ ≈ 4–9), **well before product titer signals would meaningfully separate the
media recipes**. The ranking that comes out of such a campaign reflects which
recipes happen to slow growth enough to stay under the OTR ceiling, not which
recipes support best periplasmic expression. A bioreactor at 2 L with
kLa = 400 h⁻¹ will then rank-disagree with the flask data, and the apparent
"failure to translate" will be misdiagnosed as a media-formulation problem.

**The campaign-level mitigation that must hold** before any handoff packet is
acted upon: (a) flask kLa measured (sulfite oxidation or gassing-out, single
20-min characterization) and ≥ 100 h⁻¹, (b) baffled 500 mL flask with 5-cm orbital
throw at ≥ 220 rpm and ≤ 1:5 fill, (c) flask DO ≥ 30% confirmed via a PreSens
patch on at least one flask of every batch. None of these is the simulator's job;
they are entry conditions for the simulator's predictions to mean anything.

---

## 11. References

Primary correlations:

- Van't Riet, K. (1979). *Review of measuring methods and results in nonviscous
  gas-liquid mass transfer in stirred vessels.* Ind. Eng. Chem. Process Des. Dev.
  18(3), 357–364. [DOI](https://pubs.acs.org/doi/abs/10.1021/i260072a001)
- Maier, U., Losen, M., & Büchs, J. (2004). *Advances in understanding and modeling
  the gas-liquid mass transfer in shake flasks.* Biochem. Eng. J. 17, 155–167.
- Büchs, J., Maier, U., Milbradt, C., & Zoels, B. (2000). *Power consumption in
  shaking flasks I & II.* Biotechnol. Bioeng. 68(6), 589–605.
  [PubMed](https://pubmed.ncbi.nlm.nih.gov/10799983/)
- Peter, C. P., Suzuki, Y., & Büchs, J. (2006). *Volumetric power consumption in
  baffled shake flasks.* Chem. Eng. Sci. 61, 3771–3779.
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0009250905009632)
- Nienow, A. W. (1997). *On impeller circulation and mixing effectiveness in the
  turbulent flow regime.* Chem. Eng. Sci. 52, 2557–2565.
- Grenville, R. K. & Nienow, A. W. (2004). *Blending of miscible liquids* in
  Paul, Atiemo-Obeng, Kresta (eds.) Handbook of Industrial Mixing, Wiley.
- Linek, V., Vacek, V., & Beneš, P. (1987). *A critical review and experimental
  verification of the correct use of the dynamic method for the determination of
  oxygen transfer in aerated agitated vessels to water...* Chem. Eng. J. 34, 11–34.

*E. coli* scale-up and physiology:

- Garcia-Ochoa, F. & Gomez, E. (2009). *Bioreactor scale-up and oxygen transfer
  rate in microbial processes: an overview.* Biotechnol. Adv. 27(2), 153–176.
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0734975008001110)
- Riesenberg, D. & Guthke, R. (1999). *High-cell-density cultivation of micro-
  organisms.* Appl. Microbiol. Biotechnol. 51, 422–430.
  [Springer](https://link.springer.com/article/10.1007/s002530051506)
- Käß, F. et al. (2018). *Modelling concentration gradients in fed-batch
  cultivations of E. coli, towards the flexible design of scale-down
  experiments.* [ResearchGate](https://researchgate.net/publication/326993600)
- Vasilakou, K. et al. (2020). *Escherichia coli metabolism under short-term
  repetitive substrate dynamics: adaptation and trade-offs.* Microb. Cell Fact.
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7260802/)
- Anane, E. et al. (2021). *Glucose-Limited Fed-Batch Cultivation Strategy to
  Mimic Large-Scale Effects in Escherichia coli.* Bioengineering.
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8223794/)
- *Mass Transfer and Rheological Characteristics in a Stirred Tank Bioreactor
  for Cultivation of E. coli BL21* (2020). Biotechnol. Bioprocess Eng.
  [Springer](https://link.springer.com/article/10.1007/s12257-020-0028-3)
- *High cell density cultivation of E. coli in shake flasks for the production
  of recombinant proteins* (2021).
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8718739/)
- *Scale-up of microbial fermentation using recombinant E. coli*, Thermo
  Fisher application note.
  [Thermo Fisher](https://documents.thermofisher.com/TFS-Assets/BPD/Application-Notes/scale-up-microbial-fermentation-using-recombinant-ecoli-app-note.pdf)
- *High-cell-density cultivation of E. coli in a BIOSTAT D-DCU*, Sartorius
  application note.
  [Sartorius](https://www.sartorius.com/download/10104/appl-biostat-d-dcu-high-cell-density-cultivation-e-coli-sbt1015-e-data.pdf)

Scale-down framework and shear:

- *Scale-down bioreactors, comparative analysis of configurations* (2025).
  Bioprocess Biosyst. Eng. [Springer](https://link.springer.com/article/10.1007/s00449-025-03182-w)
  / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12460589/)
- Neubauer, P. & Junne, S. (2010). *Scale-down simulators for metabolic analysis
  of large-scale bioprocesses.* Curr. Opin. Biotechnol. 21, 114–121.
- *Shear-Proof Design Space: Scaling Stirred-Tank Bioreactors for Cell Culture
  Processes*, BioProcess International.
  [BPI](https://www.bioprocessintl.com/bioreactors/shear-proof-design-space-scaling-stirred-tank-bioreactors-for-cell-culture-processes)
- *Lessons in Bioreactor Scale-Up Parts 4 & 5*, BioProcess International (kLa
  and OTR physiochemistry).
  [BPI Part 4](https://www.bioprocessintl.com/bioreactors/lessons-in-bioreactor-s-scale-up-part-4-physiochemical-factors-affecting-oxygen-transfer-and-the-volumetric-mass-transfer-coefficient-in-stirred-tanks)
  / [BPI Part 5](https://www.bioprocessintl.com/bioreactors/lessons-in-bioreactor-scale-up-part-5-theoretical-and-empirical-correlations-for-predicting-the-mass-transfer-coefficient-in-stirred-tank-bioreactors)
- *Scaling Bioreactors: Shear Stress Modelling Techniques*, Cellbase.
  [Cellbase](https://cellbase.com/blogs/news/scaling-bioreactors-shear-stress-modelling-techniques)

Regulatory anchor:

- ICH Q11 (2012, R1 2017). *Development and manufacture of drug substances
  (chemical and biotechnological/biological entities).*

---

## 12. Companion documents in this repository

- `docs/SCALE_BRIDGE.md`, schema, primary-criterion picker, anti-patterns.
- `docs/CONTRACTS.md`, `scale_context` and `scale_down_qualification` field
  contracts.
- `docs/PROFILES.md`, `scale_up`, `scale_down`, and `scale_down_qualification`
  profile definitions.
- `src/biosymphony_ferm_doe/scale_recipe.py`, engine implementation of Eqs. 1–4
  that this document is the reference text for.
