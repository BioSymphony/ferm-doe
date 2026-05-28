# Cost-Model Realism Check

**Issued:** 2026-05-16
**Verdict:** **The simulator's cost-per-mg figures are correct for what they measure but materially understate lab-scale execution cost by 3–6 orders of magnitude.** Cost-model caveats must accompany any cost-per-mg recommendation that comes out of a media-only-bulk-pricing simulator.
**Scope:** pressure-test cost-per-mg numbers against bulk, Sigma, and fully-loaded lab-scale stacks; identify dominant cost component; sensitivity analysis.

This note uses a synthetic *E. coli* BL21 periplasmic-protein media-optimisation example to walk through the methodology. The principle generalises to any IPTG-induced or lactose-autoinduced microbial expression campaign with a small-N initial screen.

---

## TL;DR

| Cost model | Candidate A ($/mg) | Candidate B ($/mg) | Note |
|---|---|---|---|
| **Simulator (media-only, bulk, NO IPTG)** | **0.0000228** | **0.0000255** | What the headline number cites |
| Material-only, bulk prices, **including IPTG @ $50/kg** | 0.29 | 0.25 | IPTG dominates (92%) |
| Material-only, Sigma research-grade | 533.72 | 445.97 | If the lab orders from Sigma |
| **Fully-loaded shake-flask COGS** (bulk materials + labor + QC + depreciation) | **171** | **143** | What it actually costs to execute one flask |
| Industry process-scale CMO benchmark (E. coli rec-protein, fed-batch, 1 g/L titer) | 0.10 – 0.56 | 0.10 – 0.56 | Lonza/WuXi commercial scale, after amortization |

The headline number is internally consistent with the simulator's cost constraint (see section 1.B), but the cost constraint excludes IPTG entirely. That is acceptable only when the manifest explicitly treats IPTG as a negligible micromolar process aid. It does not hold at the 1 mM induction level Candidate A/B specify.

---

## 1. Bill-of-Materials Decomposition

### 1.A, Candidate A & B factor levels

| Factor | Candidate A | Candidate B | Unit |
|---|---|---|---|
| Lactose | 1.0 | 1.0 | g/L |
| Glucose | 0.0 | 0.5 | g/L |
| Glycerol | 0.0 | 0.0 | g/L |
| Ammonium sulfate | 0.5 | 0.5 | g/L |
| IPTG | 1.0 | 1.0 | **mM** (= 0.2383 g/L) |
| Induction temperature | 30 | 30 | °C |
| Induction OD600 | 1.5 | 1.5 | (dimensionless) |
| Predicted titer | 45 | 54 | mg/L |

### 1.B, Per-component contribution ($/L)

**Bulk process-grade prices** match the canonical fermentation media costs corridor audited 2026 Q1–Q2. **Sigma research-grade prices** taken from the current MilliporeSigma catalog at the 500 g–1 kg pack size, midpoint of typical published listing.

| Component | g/L (A) | g/L (B) | Bulk $/kg | Sigma $/kg | $/L bulk (A) | $/L Sigma (A) | $/L bulk (B) | $/L Sigma (B) |
|---|---|---|---|---|---|---|---|---|
| Lactose | 1.0 | 1.0 | 0.90 | 150 | 0.000900 | 0.1500 | 0.000900 | 0.1500 |
| Glucose | 0 | 0.5 | 0.70 | 130 | 0 | 0 | 0.000350 | 0.0650 |
| Glycerol | 0 | 0 | 1.70 | 200 | 0 | 0 | 0 | 0 |
| Ammonium sulfate | 0.5 | 0.5 | 0.25 | 75 | 0.000125 | 0.0375 | 0.000125 | 0.0375 |
| **IPTG (1 mM = 0.2383 g/L)** | 0.2383 | 0.2383 | **50** (bulk industrial midpoint) | **100 000** (Sigma I6758 dioxane-free ≥99%, ~$60–150/g) | **0.011915** | **23.8300** | **0.011915** | **23.8300** |
| **Total material $/L** | | | | | **0.012940** | **24.0175** | **0.013290** | **24.0825** |
| **Cost-per-mg ($/mg)** at predicted titer | | | | | **0.2876** | **533.72** | **0.2461** | **445.97** |

IPTG bulk prices vary widely: Made-in-China.com Q2 2026 listings span **$1–450/kg** depending on purity and MOQ; mid-range 99% bulk is ~$25–100/kg. The $50/kg midpoint is conservative for fermentation-grade 1 kg orders.

### 1.C, Why the simulator's $/mg is 12 600× lower than bulk-with-IPTG

The synthetic manifest's cost constraint (`media_cost_lte_120_per_L`) includes only 9 components: glucose, glycerol, lactose, sucrose, xylose, ammonium_sulfate, corn_steep_liquor, yeast_extract, tryptone. **IPTG, induction temperature, and induction OD600 are explicitly excluded.** This is a useful stress test because it shows how a media-only cost objective can understate execution cost when a non-media inducer is held constant but expensive.

This is true at the **µM** IPTG concentrations used in some autoinduction protocols. It is **not** true at the **1 mM** level Candidate A/B specify. At 1 mM, IPTG contributes $0.011915/L at bulk price, 12× the entire Candidate A media cost.

The simulator therefore ranks candidates on a cost figure that excludes the dominant material expense.

---

## 2. Three-Stack Cost-Model Comparison

### Stack 1, simulator current model (media-only, bulk, IPTG excluded)

| | Candidate A | Candidate B |
|---|---|---|
| $/L | 0.001025 | 0.001375 |
| Titer (mg/L) | 45 | 54 |
| **$/mg** | **0.0000228** | **0.0000255** |

This matches the headline numbers exactly. It is what a BoFire `cost_per_mg` response would evaluate and rank against in this kind of campaign.

### Stack 2, material-only, bulk prices, IPTG included

| | Candidate A | Candidate B |
|---|---|---|
| Media $/L (bulk) | 0.001025 | 0.001375 |
| IPTG $/L (bulk @ $50/kg) | 0.011915 | 0.011915 |
| Total material $/L | 0.012940 | 0.013290 |
| Titer (mg/L) | 45 | 54 |
| **$/mg** | **0.288** | **0.246** |

IPTG is **92% of material cost** in Candidate A and **90%** in Candidate B. Adding IPTG to the cost stack inverts the ranking only marginally (Candidate B becomes cheaper per-mg than Candidate A because its higher titer dilutes the fixed IPTG cost faster than the 0.5 g/L glucose adds).

### Stack 3, material-only, Sigma research-grade

| | Candidate A | Candidate B |
|---|---|---|
| Media $/L (Sigma) | 0.1875 | 0.2525 |
| IPTG $/L (Sigma @ ~$100k/kg) | 23.83 | 23.83 |
| Total $/L | 24.02 | 24.08 |
| **$/mg** | **534** | **446** |

A demo flask ordered "everything from Sigma" pays roughly **20 000–25 000× more per L** than the bulk model and roughly **20 000× more per mg product**. This is the corridor that catches first-time bioprocess teams: if they Google IPTG and order Sigma's I6758 ($60–$150/g), one 50 mL induction costs them $1.20 in inducer alone before media, plastics, or labor.

### Stack 4, fully-loaded lab-scale shake-flask COGS

Anchored on the [Cost analysis of E. coli BL21(DE3) recombinant protein production paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7049567/) which reports **$96.5/kg PspA4Pro = $0.097/g** for defined-medium bioreactor production at industrial scale (excludes labor, depreciation, QC). At 50 mL shake-flask scale the labor, QC and depreciation overheads inflate this 1000–5000×:

| Cost component | $/flask (50 mL) | Basis |
|---|---|---|
| Media (bulk, with IPTG) | $0.0006 | Stack 2 × 0.05 L |
| Skilled tech labor (3 h @ $80/h) | $240 | Inoculate, induce, harvest, lyse, IMAC-purify |
| QC (ELISA + SEC-HPLC + SDS-PAGE) | $100 | Per-batch acceptance |
| Equipment depreciation | $45 | Shaker, centrifuge, ÄKTA amortized |
| **Total $/flask** | **$385** | |
| Yield (mg per flask) | 2.25 (A) / 2.70 (B) | titer × 50 mL |
| **Fully-loaded $/mg** | **$171 (A) / $143 (B)** | |

These numbers fall in the same order-of-magnitude as the [published cost estimation paper for E. coli BL21 vaccine antigens](https://pubmed.ncbi.nlm.nih.gov/38198230/), which reports **$52.50–$559.80/g** depending on protein and culture mode for lab-to-pilot scale.

### Stack summary

| Stack | Candidate A $/mg | Candidate B $/mg | Order of magnitude vs simulator |
|---|---|---|---|
| 1. Simulator (bulk media only, no IPTG) | 0.0000228 | 0.0000255 | 1× (baseline) |
| 2. Bulk material + IPTG | 0.288 | 0.246 | 10 000× higher |
| 3. Sigma research-grade | 534 | 446 | 20 000 000× higher |
| 4. Fully-loaded shake-flask COGS | 171 | 143 | 6 000 000× higher |
| 5. Industry CMO process-scale (Lonza/WuXi style, 1 g/L fed-batch) | 0.10–0.56 | 0.10–0.56 | 4 400× to 25 000× higher |

---

## 3. Industry Benchmarks

| Source | Modality | Cost reported | Notes |
|---|---|---|---|
| [Cost analysis E. coli BL21(DE3) ScienceDirect](https://pmc.ncbi.nlm.nih.gov/articles/PMC7049567/) | E. coli BL21 soluble PspA4Pro | **$96.5/kg = $0.097/g** | Defined medium, bioreactor, IPTG identified as single largest media-cost line at 1 mM induction. Excludes labor + depreciation + QC. |
| [E. coli BL21 vaccine antigen production](https://pubmed.ncbi.nlm.nih.gov/38198230/) | rEipB / rOmp25 | **$52.50–$559.80/g** | Range across two proteins and operational scenarios. Raw materials = ~60% of total. |
| [Cost evaluation of antibody production processes](https://www.biopharminternational.com/view/economic-drivers-and-trade-offs-antibody-purification-processes-1) | mAb fed-batch | **€59/g (= ~$64/g)** | Continuous mode €84/g (~$91/g). Fed-batch is the cheaper mode at this scale. |
| [Lonza XS Technologies microbial](https://www.lonza.com/biologics/expression-technologies/xs-technologies) | E. coli / Pichia | List price not published | Same. |
| [GFI techno-economic analysis](https://gfi.org/resource/techno-economic-insights-on-fermentation-ingredients/) | Precision-fermentation proteins, projected 2025 | **$10/kg = $0.01/g** at scale | Aspirational floor; only applicable at 100 m³ continuous fermentation. |
| Public high-titer microbial expression reports | E. coli recombinant protein, 1 L+ bioreactor | Titer up to low g/L | Not cost papers; useful only as titer-ceiling context. |

**Illustrative industry COGS corridor for E. coli microbial recombinant protein at gram-to-kilogram scale: $0.10–$2/mg ($100–$2 000/g) for non-GMP material; GMP material can be materially higher depending on product, release testing, and facility model. Process-scale fed-batch at 1+ g/L titer pushes this toward the lower bound; 50 mL shake flasks at 50 mg/L push it toward the upper bound.**

The simulator's number ($0.0000228/mg = $0.023/g) is **roughly 4 000–87 000× cheaper than the best published industry benchmark** for this modality.

---

## 4. Reusable Disclosure Block For Planning Packets

Use the following block whenever a planning packet reports a simulator-derived cost-per-mg figure from a media-only cost model:

> ### Cost Model Caveats
>
> The cost-per-mg figures cited above (**$0.0000228/mg** for Candidate A, **$0.0000255/mg** for Candidate B) are produced by the simulator's material-only cost model at bulk process-grade pricing **with IPTG excluded**. Those figures should be treated as **relative rankings**, not absolute COGS, unless the manifest separately proves that inducer concentration and cost are negligible.
>
> Including IPTG at bulk industrial pricing (~$50/kg), Candidate A material cost is **$0.29/mg** and Candidate B is **$0.25/mg**. IPTG accounts for **~92% of material cost** at these factor levels. If the execution team orders inducer from Sigma Aldrich (catalog price ~$60–150/g), material cost rises to **$534/mg (Candidate A)** and **$446/mg (Candidate B)**. Fully-loaded shake-flask COGS at 50 mL scale, bulk materials plus labor, QC, and equipment depreciation, is on the order of **$140–$170/mg**, consistent with published E. coli rec-protein cost analyses ($52–$560/g).
>
> Industry process-scale CMOs (Lonza, WuXi, etc.) achieve **$0.10–$2/mg** for non-GMP microbial recombinant protein at the kilogram scale, primarily through 10–40× higher titer (1–2 g/L fed-batch versus 45–54 mg/L shake flask) and amortized labor. **A "Stack 1 only" headline number is therefore valid as a within-campaign ranking of media compositions but should not be quoted as a standalone process-scale achievement.** That figure is an artifact of an inducer-blind cost model at shake-flask titer.

Cross-reference this note from the campaign dossier or planning packet under "Cost model limitations."

---

## 5. Sensitivity Analysis, Dominant Cost Component & Flip Points

**Dominant cost component at Candidate A/B factor levels (bulk pricing):** IPTG at 1 mM. Contributes **$0.01192/L = 92% of material cost** in Candidate A.

### 5.A, Flip thresholds (how much $/L of any other component before it equals IPTG bulk cost)

| Component | Bulk $/kg | g/L needed to equal IPTG-bulk @ 1 mM |
|---|---|---|
| Glucose | 0.70 | **17.0 g/L** |
| Lactose | 0.90 | **13.2 g/L** |
| Glycerol | 1.70 | 7.0 g/L |
| Xylose | 2.00 | 6.0 g/L |
| Yeast extract | 3.50 | 3.4 g/L |
| Tryptone | 12.00 | **0.99 g/L** |

At Candidate A levels (lactose=1, AS=0.5, IPTG=1 mM), **the cost ranking would only flip if lactose climbs above ~13 g/L**. That is a useful diagnostic for any high-lactose candidate: the media-cost story may look plausible while the titer simulator is still missing the dose-response curve that would make the recommendation biologically meaningful.

### 5.B, IPTG-concentration crossover

The IPTG cost contribution equals the Candidate A media cost (excluding IPTG, $0.001025/L) at **0.086 mM IPTG**. At the classical 1 mM induction strength, IPTG is **12× the entire media cost**. At 0.5 mM IPTG it is still ~6× the media cost.

**Practical implication:** any media optimisation campaign that holds IPTG at 1 mM and varies only carbon/N sources is optimising in the wrong dimension. One fast cost-per-mg lever is to test whether **IPTG induction can be replaced by lactose autoinduction**. At 1 g/L lactose and 0.5 g/L glucose (Candidate B's composition minus the IPTG), classical Studier autoinduction can achieve comparable titer in some systems with $0/L inducer cost, collapsing material $/L from $0.0133 to $0.001375 (10× cheaper). That hypothesis still requires local assay evidence before use.

### 5.C, Titer leverage dominates everything else

Cost-per-mg = $/L ÷ titer. At fully-loaded shake-flask scale (Stack 4):
- Doubling titer from 45 to 90 mg/L cuts $/mg by half ($171 → $86).
- Switching to a 1 g/L fed-batch bioreactor cuts $/mg by ~22× ($171 → $7.7).
- All media-composition optimisation combined caps out at <1% improvement at this scale because labor + QC + depreciation are fixed per flask.

**The largest cost lever is not media composition. It is titer and scale.** This is consistent with the [BioPharm International economic drivers analysis](https://www.biopharminternational.com/view/economic-drivers-and-trade-offs-antibody-purification-processes-1) which finds upstream:downstream cost ratio shifts from 55:45 to 30:70 as titer goes from 0.1 → 1 g/L.

---

## 6. Recommended Disclosure Range (1-line summary for the handoff)

> **Honest cost-per-mg range for Candidate A:** $0.000023/mg (simulator, IPTG excluded) → **$0.29/mg material at bulk industrial pricing** → **$140–$170/mg fully-loaded shake-flask COGS**. The simulator figure is a within-campaign ranking, not a quotable COGS.

---

## Sources

- [Cost analysis based on bioreactor cultivation conditions: E. coli BL21(DE3), PMC7049567](https://pmc.ncbi.nlm.nih.gov/articles/PMC7049567/), IPTG identified as single largest media-cost line at 1 mM induction; $96.5/kg PspA4Pro reference.
- [Recombinant protein production E. coli BL21 vaccine applications cost estimation, PubMed 38198230](https://pubmed.ncbi.nlm.nih.gov/38198230/), $52.50–$559.80/g range; raw materials = ~60% of total.
- [Economic Drivers and Trade-Offs in Antibody Purification Processes, BioPharm International](https://www.biopharminternational.com/view/economic-drivers-and-trade-offs-antibody-purification-processes-1), €59/g fed-batch mAb COGS.
- [Lonza XS Technologies microbial](https://www.lonza.com/biologics/expression-technologies/xs-technologies), CMO platform reference (no public pricing).
- [GFI techno-economic insights on fermentation ingredients](https://gfi.org/resource/techno-economic-insights-on-fermentation-ingredients/), $10/kg precision-fermentation aspirational floor.
- [IPTG bulk pricing, Made-in-China.com Q2 2026](https://www.made-in-china.com/price/iptg-price.html), $1–450/kg bulk range; $25–100/kg fermentation-grade midpoint.
- [Sigma Aldrich IPTG I6758 dioxane-free](https://www.sigmaaldrich.com/US/en/product/mm/420322), research-grade catalog reference (~$60–150/g).
