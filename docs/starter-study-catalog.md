# Starter Study Catalog

This catalog records actual fermentation or upstream bioprocess optimization studies that can become starter campaign problems. It separates `extract_ready` sources from `candidate_only` sources so workers do not silently copy numeric data from unclear licenses.

## Selection Criteria

- Published in the 2000s or 2010s.
- Fermentation, upstream bioprocess, or closely adjacent culture optimization.
- Contains DoE/RSM-style experimental design data or enough structure to seed a campaign.
- Prefer PLOS, MDPI, BMC/SpringerOpen, Frontiers, or PMC pages with clear table availability.
- Keep source metadata, license, and transformation notes beside any normalized ledger.

## Ranked Sources

| Rank | Study ID | Year | Problem Class | Organism/System | Method | Extraction Status | Why It Is Useful |
| ---: | --- | ---: | --- | --- | --- | --- | --- |
| 1 | `xylanase-wxz1-2012` | 2012 | Enzyme titer/media optimization | *Penicillium* sp. WX-Z1 | Plackett-Burman + Box-Behnken + RSM | `normalized_in_repo` | Already normalized; strong starter for medium-component optimization. |
| 2 | `eps-zunongwangia-2011` | 2011 | EPS yield and rheology | *Zunongwangia profunda* SM-A87 | Plackett-Burman + steepest ascent + CCD/RSM | `extract_ready` | Multi-response problem: EPS yield plus viscosity. Good for multi-objective planning. |
| 3 | `protease-pseudomonas-skg1-2011` | 2011 | Enzyme titer plus bioreactor validation | *Pseudomonas putida* SKG-1 | RSM + bench-scale validation | `extract_ready` | Older CC BY case with clear response table and bench-scale validation. |
| 4 | `pcps-paecilomyces-2014` | 2014 | Solid-state polysaccharide yield | *Paecilomyces cicadae* | Plackett-Burman + steepest ascent + Box-Behnken | `extract_ready` | Strong solid-state contrast to submerged fermentation; includes humidity, inoculum, and temperature. |
| 5 | `vanillin-ecoli-2007` | 2007 | Secondary metabolite bioconversion | engineered *E. coli* | RSM | `extract_ready` | Strong 2000s open-access starter; biomass/substrate to yield/productivity. |
| 6 | `biohydrogen-potato-waste-2016` | 2016 | Biofuel/waste valorization | mixed anaerobic sludge | Box-Behnken + RSM | `extract_ready` | Good process-setpoint optimization: substrate, pH, temperature, and time. |
| 7 | `biosurfactant-candida-2017` | 2017 | Waste feedstock multi-response | *Candida tropicalis* UCP0996 | CCRD/RSM + scale-up validation | `extract_ready` | Multi-response surface tension/yield plus 2 L and 50 L scale-up. |
| 8 | `dha-thraustochytrium-2018` | 2018 | High-value lipid production | *Thraustochytrium* sp. ATCC 26185 | Plackett-Burman + Box-Behnken + RSM | `extract_ready` | Compact high-value product case with clean Box-Behnken follow-up. |
| 9 | `streptomyces-antibacterial-2018` | 2018 | Secondary metabolite production | *Streptomyces* sp. 1-14 | Plackett-Burman + steepest ascent + Box-Behnken | `extract_ready_with_supplement` | Good assay-readiness case because response is inhibition-zone or activity based. |
| 10 | `glucoamylase-humicola-2014` | 2014 | Enzyme media optimization | *Humicola grisea* MTCC 352 | Plackett-Burman + steepest ascent + CCD/RSM | `extract_ready` | Full workflow with predicted/observed values and permissive reuse. |
| 11 | `rpdt-ecoli-2018` | 2018 | Recombinant protein expression | engineered *E. coli* | Box-Behnken | `extract_ready` | Excellent process case: temperature, DO, and IPTG in a 5 L fermenter. |
| 12 | `alpha-galactosidase-fusarium-2016` | 2016 | Solid-state enzyme optimization | *Fusarium moniliforme* NCIM 1099 | Plackett-Burman + CCRD/RSM | `extract_ready` | Solid-state fermentation with agro-substrate and CC BY 4.0 terms. |
| 13 | `dna-vaccine-ecoli-2018` | 2018 | Plasmid DNA production | engineered *E. coli* DH5alpha | Plackett-Burman + steepest ascent + Box-Behnken | `extract_ready` | High-value biopharma-like upstream problem; good for quality/yield constraints. |
| 14 | `cowdung-ssf-cmcase-protease-2016` | 2016 | Solid-state multi-enzyme production | *Bacillus* sp. on cow dung | factorial screening + CCD | `extract_ready` | Multi-response cellulase/protease and unusual low-cost substrate. |
| 15 | `pha-ralstonia-2019` | 2019 | Biopolymer/PHA production | *Ralstonia solanacearum* RS | central composite rotational design | `extract_ready` | Bioreactor process variables and multiple responses: OD, dry cell weight, and P(3HB). |
| 16 | `citric-acid-ccd-data-2017` | 2017 | Organic acid data paper | *Aspergillus niger* NCIM 705 | Plackett-Burman + CCD | `extract_ready_verify_license` | Data-paper style CCD, useful for extraction/model stress tests after license check. |
| 17 | `gsh-lactobacillus-2017` | 2017 | Intracellular product/stress optimization | *Lactobacillus plantarum* | Plackett-Burman + Box-Behnken | `extract_ready` | Good stressor-factor and food-grade organism case. |
| 18 | `eps-pseudoalteromonas-2019` | 2019 | Marine EPS production | *Pseudoalteromonas agarivorans* Hao 2018 | Plackett-Burman + Box-Behnken + RSM | `extract_ready` | Good process-factor EPS case with downstream characterization. |
| 19 | `bioflocculant-mixed-culture-2014` | 2014 | Mixed-culture bioflocculant | *Streptomyces* + *Brachybacterium* consortium | Plackett-Burman + CCD/RSM | `extract_ready` | Intentionally messy/weak-fit case for YELLOW/RED model logic. |
| 20 | `pha-methylosinus-2018` | 2018 | Methane-to-PHB biopolymer | *Methylosinus trichosporium* OB3b | second-order regression + RSM | `extract_ready_partial_product_tables` | Good gas-fermentation/biopolymer case; product extraction is less table-complete. |
| 21 | `pyruvic-acid-2007` | 2007 | Organic acid medium optimization | *Torulopsis glabrata* TP19 | response surface methodology | `candidate_metadata_only` | Valuable 2000s problem; current check did not confirm open reuse for numeric tables. |

## Problem Classes To Preserve

- `enzyme_titer`: xylanase, inulinase, protease, cellulase
- `eps_rheology`: EPS yield plus viscosity or functional properties
- `solid_state`: humidity, inoculum, substrate matrix, temperature
- `biofuel_waste`: biohydrogen, ethanol, waste valorization
- `biopolymer`: PHA/PHB, lipid, storage polymers
- `recombinant_expression`: protein, plasmid DNA, vaccine construct
- `secondary_metabolite`: antibiotic or antimicrobial activity
- `multi_response`: biomass plus product, quality plus yield, activity plus purity
- `waste_feedstock_multi_response`: biosurfactants and waste substrate valorization
- `mixed_culture_low_fit`: consortium cases where weak model fit is a useful readiness stress test

## Extraction Rule

Numeric ledgers may be added under `examples/<study_id>/inputs/` only when one of these is true:

- source license clearly allows reuse with attribution
- data are user-provided and sanitized
- data are synthetic and labeled as synthetic
- source is used only as metadata and no table values are copied
