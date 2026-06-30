# Cost-Stack 5-Way Honesty Check

**Template version:** 1.0
**Purpose:** Force every campaign that reports a unit cost ($/mg, $/L, $/dose, $/batch) to stack it five ways so a reader can see what is included, what is excluded, and which audience the number is fit for. A single quoted $/mg figure is forbidden in any handoff packet, lab brief, dossier, presentation, or commit message.

## Why this template exists

Internal Pareto winners can ship a quoted cost-per-mg from the engine's media-only,
bulk-priced, inducer-excluded simulator while the fully-loaded shake-flask cost
sits several orders of magnitude higher. Both figures are internally consistent
with their own model, but quoting the simulator figure standalone materially
understates lab-scale execution cost and misrepresents the campaign to any
audience above the engine itself. See
[`docs/COST_MODEL_REALISM_CHECK.md`](../docs/COST_MODEL_REALISM_CHECK.md) for the
full rationale.

## When to fill

Any time the campaign reports a unit cost ($/mg, $/L, $/dose, $/batch) in any of:

- Handoff packet (`lab_team_brief.md`, `design_table.csv`, `cost_tradeoff.html`).
- Dossier (`dossier.html`, `dossier/NOTES.md`).
- Presentation or one-pager.
- Commit message or PR description.
- External-facing artifact (poster, manuscript, blog, demo portal).

Fill this template once per campaign and link to it from every artifact that
quotes a unit-cost number. A single completed instance can cover multiple
recipes inside one campaign; repeat Section 2 through Section 5 per recipe,
then aggregate in Section 6.

## Conventions

- Fields marked `REQUIRED` fail the check if blank.
- Fields marked `OPTIONAL` may be omitted but their absence should be deliberate.
- Placeholders use `{{double-braces}}`; replace inline.
- Tables expand with as many rows as the campaign has components or recipes.
- This is a DOE planning artifact, not a batch record. Do not add operator
  initials, lot tracking, IPC alert/action runtime, deviation logs, or
  21 CFR 211.188 scaffolding.

---

## Section 1: Campaign and cost-claim identification

| Field | Value |
|---|---|
| Campaign ID (REQUIRED) | {{campaign_id}} |
| Recipe or candidate ID (REQUIRED) | {{e.g., `CAND-001` or `CandidateA`}} |
| Cost claim location (REQUIRED) | {{file path + section, e.g., `handoff-packet/lab_team_brief.md §3` or `dossier/dossier.html "Cost" card`}} |
| Cost unit being claimed (REQUIRED) | {{one of: `$/mg` \| `$/L` \| `$/dose` \| `$/batch` \| other (specify)}} |
| Target audience for this claim (REQUIRED) | {{e.g., `internal optimization target` \| `process team handoff` \| `CFO budget` \| `investor pitch` \| `manuscript`}} |
| Modality (REQUIRED) | {{e.g., `E. coli BL21 microbial`, `CHO mAb fed-batch`, `Pichia`, `cell-free`}} |
| Scale being costed (REQUIRED) | {{e.g., `50 mL shake flask`, `1 L stirred-tank`, `200 L pilot fed-batch`, `2000 L GMP`}} |

---

## Section 2. Stack 1: Simulator output (media-only, bulk price, no inducer)

This is what the campaign's BoFire or simulator model evaluates against its cost
constraint. It is always the lowest of the five stacks and is not a realistic
execution cost.

| Field | Value |
|---|---|
| Formula source (REQUIRED) | {{file:line or json path, e.g., `bofire_phase2_report.json :: simulator_coefficients.cost_per_L`}} |
| Cost constraint manifest path (REQUIRED) | {{e.g., `campaign_manifest.json :: constraints[].media_cost_lte_120_per_L`}} |
| Components included (REQUIRED) | {{enumerate, e.g., `glucose, glycerol, lactose, sucrose, xylose, ammonium_sulfate, corn_steep_liquor, yeast_extract, tryptone`}} |
| Components explicitly excluded (REQUIRED) | {{e.g., `IPTG, induction temperature, induction OD600`}} |
| Bulk-vs-catalog annotation (REQUIRED) | {{must be `bulk industrial`; if catalog-grade, this is not Stack 1, move to Stack 3}} |

### 2.1 Component costs

| Component | Concentration (g/L) | Bulk $/kg (cite source) | $/L contribution |
|---|---|---|---|
| {{component_1}} | {{g/L}} | {{$/kg}} | {{$/L}} |
| {{component_2}} | {{g/L}} | {{$/kg}} | {{$/L}} |
| {{component_3}} | {{g/L}} | {{$/kg}} | {{$/L}} |
| **Total $/L** | | | **{{$/L}}** |

### 2.2 Stack 1 output

| Field | Value |
|---|---|
| Predicted titer (REQUIRED for $/mg claims) | {{mg/L}} |
| Stack 1 unit cost (REQUIRED) | {{e.g., `$0.0000228/mg` or `$0.001025/L`}} |
| Caveat banner text (REQUIRED, verbatim or equivalent) | "This figure is a within-campaign ranking metric, not an execution COGS. It excludes inducer, consumables, labor, QC, and depreciation. See Stacks 2 through 4 for honest lab-scale and process-scale ranges." |

---

## Section 3. Stack 2: +Inducer at production concentration (bulk industrial)

If the recipe uses no inducer (autoinduction with no IPTG, no arabinose, no
tetracycline), mark this section `NOT_APPLICABLE` and document why.

| Field | Value |
|---|---|
| Inducer choice (REQUIRED) | {{one of: `IPTG` \| `lactose` \| `arabinose` \| `tetracycline` \| `other (specify)` \| `NOT_APPLICABLE`}} |
| Inducer concentration (REQUIRED) | {{e.g., `1 mM IPTG = 0.2383 g/L`}} |
| Concentration source citation (REQUIRED) | {{free text: protocol reference, PMID/DOI, or campaign manifest field}} |
| Industrial bulk $/kg (REQUIRED) | {{e.g., `IPTG ~$50/kg fermentation-grade midpoint`}} |
| Per-L inducer cost (REQUIRED) | {{$/L, e.g., `$0.011915/L for 1 mM IPTG`}} |
| Per-L total (Stack 1 + Stack 2) (REQUIRED) | {{$/L sum}} |
| Stack 2 unit cost (REQUIRED) | {{e.g., `$0.29/mg`}} |
| Inducer share of material cost (REQUIRED) | {{% e.g., `92% of material cost at 1 mM IPTG`}} |

**Note:** IPTG at 1 mM typically dominates material cost (>= 90%) for E. coli
expression. If the inducer share is below roughly 50%, double-check the bulk
price; research-grade catalog pricing leaks into Stack 3, not Stack 2.

---

## Section 4. Stack 3: Fully-loaded shake-flask material cost

This adds consumables, labor, QC, and depreciation to bulk materials + inducer.
This is the most realistic cost number for a campaign that has not yet scaled
above shake flasks.

| Cost component | $/flask | Basis |
|---|---|---|
| Media + inducer (bulk, from Stack 2 x flask volume) | {{$/flask}} | {{Stack 2 $/L x flask volume}} |
| Skilled tech labor | {{$/flask}} | {{hours x loaded rate, e.g., `3 h @ $80/h = $240`}} |
| QC (ELISA / SEC-HPLC / SDS-PAGE / titer assay) | {{$/flask}} | {{per-batch assay cost}} |
| Equipment depreciation (shaker, centrifuge, AKTA, etc.) | {{$/flask}} | {{amortized over expected campaign volume}} |
| Consumables (flasks, plugs, sterile filters, antibiotics, sampling tubes, DO patches, sterile media filtration) | {{$/flask}} | {{itemized below or summary}} |
| Water (RO/USP grade if costed) | {{$/flask}} | {{optional; usually < $1/flask}} |
| **Total $/flask** | **{{$/flask}}** | |

| Field | Value |
|---|---|
| Yield per flask (REQUIRED if claim is $/mg) | {{mg, e.g., `2.25 mg = 45 mg/L x 50 mL`}} |
| Stack 3 unit cost (REQUIRED) | {{e.g., `$171/mg`}} |
| Internal benchmark check (REQUIRED) | {{free text: does this fall in the lab's historical $/mg corridor? Cite prior campaign}} |
| Literature benchmark check (REQUIRED) | {{cite at least one paper, e.g., `PMID 38198230 reports $52.50 to $559.80/g for E. coli BL21 lab-to-pilot vaccine antigens`}} |

---

## Section 5. Stack 4: CMO benchmark range

This is what a real customer would pay a contract manufacturer for the same
modality at gram-to-kilogram scale. CMOs publish list prices rarely; cite
publicly disclosed rate cards, vendor pages, or recent peer-reviewed
techno-economic papers.

| Field | Value |
|---|---|
| Modality category (REQUIRED) | {{e.g., `E. coli microbial non-GMP`, `E. coli microbial GMP`, `mAb-grade CHO fed-batch`, `mAb-grade CHO perfusion`, `cell-free` }} |
| CMO benchmark range low (REQUIRED) | {{$/unit, e.g., `$0.10/mg`}} |
| CMO benchmark range high (REQUIRED) | {{$/unit, e.g., `$2/mg`}} |
| Source 1 (REQUIRED, PMID/DOI/URL) | {{e.g., `BioPharm International, Economic Drivers and Trade-Offs in Antibody Purification Processes, EUR 59/g fed-batch mAb`}} |
| Source 2 (REQUIRED, PMID/DOI/URL) | {{e.g., `PMC7049567, $96.5/kg PspA4Pro E. coli BL21 defined-medium bioreactor`}} |
| Source 3 (OPTIONAL) | {{e.g., `Vendor microbial platform, list price not published; industry estimate $1 to $10/mg GMP recombinant protein`}} |
| Honest framing for this stack (REQUIRED, verbatim or equivalent) | "This is what a real customer would pay at scale, not what this campaign's math says. It assumes 10 to 40 times higher titer than shake-flask and amortized labor; the campaign's stage-1 numbers should not be compared 1:1 with this stack." |

---

## Section 6. Stack 5: Range across stacks 1 to 4

| Stack | Unit cost | What's included | What's excluded |
|---|---|---|---|
| 1. Simulator (media-only bulk, no inducer) | {{$/unit}} | {{e.g., 9 bulk media components}} | {{e.g., IPTG, consumables, labor, QC}} |
| 2. Bulk materials + inducer | {{$/unit}} | {{Stack 1 + inducer at industrial bulk}} | {{consumables, labor, QC}} |
| 3. Fully-loaded shake-flask COGS | {{$/unit}} | {{Stack 2 + consumables + labor + QC + depreciation}} | {{scale-up amortization, GMP overhead}} |
| 4. CMO benchmark | {{$/unit}} | {{process-scale fed-batch, amortized labor}} | {{this campaign's actual recipe}} |

### 6.1 Spread

| Field | Value |
|---|---|
| Spread (highest / lowest, REQUIRED) | {{e.g., `10^5x`}} |
| Spread interpretation (REQUIRED, min 2 sentences) | {{free text: what does this spread tell a reader? Is the simulator number a useful ranking metric despite being unrealistic? Does the CMO benchmark suggest a scale-up path? Is the shake-flask COGS the right anchor for the current campaign phase?}} |

### 6.2 Audience-fit recommendation

For each audience, recommend which stack to lead with. Other stacks should
appear as supporting context, not be silently dropped.

| Audience | Lead with stack # | Support with stacks | Rationale |
|---|---|---|---|
| Internal optimization target (engine, BoFire) | {{1}} | {{2 for sanity check}} | {{ranking metric only}} |
| Process team handoff | {{3}} | {{1, 2, 4}} | {{lab will actually spend this; needs to see what's excluded}} |
| CFO budget | {{3 or 4}} | {{1 and 2 for context}} | {{depends on stage; pre-scale-up Stack 3; post-scale-up Stack 4}} |
| Investor pitch | {{4}} | {{3 for current state}} | {{aspirational scale; CMO benchmark anchors credibility}} |
| Manuscript / poster | {{3 and 4 paired}} | {{1 if simulator is the methodology contribution}} | {{honest range + scale-up trajectory}} |

---

## Section 7. Biggest cost lever

Identify the single highest-leverage cost driver for this campaign's chemistry.
This is the recommendation that the lab team or process team should evaluate
first if they want to reduce cost-per-unit by an order of magnitude or more.

| Field | Value |
|---|---|
| Lever name (REQUIRED) | {{e.g., `IPTG induction to lactose autoinduction`, `shake flask to 1 L fed-batch`, `catalog reagents to bulk industrial sourcing`}} |
| Mechanism (REQUIRED, min 2 sentences) | {{free text: why does this lever produce its cost reduction? Cite the dominant component or scale-effect.}} |
| Estimated cost reduction (REQUIRED) | {{e.g., `~10x material-cost reduction by eliminating IPTG`, `~22x fully-loaded-cost reduction by switching to 1 g/L fed-batch`}} |
| Citation (REQUIRED, PMID/DOI/URL) | {{e.g., `Studier 2005 PMID 15915565, classical lactose autoinduction recipe`}} |
| Already enabled by current campaign? (REQUIRED) | {{YES \| PARTIALLY \| NO}} |
| If `PARTIALLY` or `NO`: ticket or handoff item to propagate (REQUIRED) | {{e.g., `Add lactose-autoinduction arm to the next campaign's design space`}} |

---

## Section 8. Cost-claim provenance footer

For every dollar number that appears in the campaign's deliverables, link it to
the stack it came from. This is the table a reviewer reads first when they spot
a quoted number and want to know what it includes.

| Deliverable | $ value (verbatim) | Stack # | Citation (artifact path) |
|---|---|---|---|
| {{e.g., `lab_team_brief.md §3`}} | {{`$0.0000228/mg`}} | {{1}} | {{`bofire_phase2_report.json :: simulator_coefficients`}} |
| {{e.g., `CAVEAT-<winner_id>.md §"Cost Model Caveats"`}} | {{`$0.29/mg`}} | {{2}} | {{`docs/COST_MODEL_REALISM_CHECK.md §1.B`}} |
| {{e.g., `CAVEAT-<winner_id>.md §"Cost Model Caveats"`}} | {{`$140 to $170/mg`}} | {{3}} | {{`docs/COST_MODEL_REALISM_CHECK.md §2 Stack 4`}} |
| {{e.g., `dossier/NOTES.md "Cost model limitations"`}} | {{`$0.10 to $2/mg`}} | {{4}} | {{`docs/COST_MODEL_REALISM_CHECK.md §3 industry table`}} |

### 8.1 Signoff

| Field | Value |
|---|---|
| Operator name (REQUIRED) | {{name or role, the person who filled this template}} |
| Operator date (REQUIRED) | {{YYYY-MM-DD}} |
| Reviewer name (REQUIRED for campaign closeout) | {{name or role, independent of the operator}} |
| Reviewer date (REQUIRED for campaign closeout) | {{YYYY-MM-DD}} |
| Commit SHA where this completed file lands (REQUIRED) | {{git commit SHA; fill after the commit lands}} |
