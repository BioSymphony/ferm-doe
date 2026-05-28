# Open-source bioprocess tool survey

Date: 2026-05-15

Scope: practical open-source modeling, simulation, experiment-planning, data, and interchange tools relevant to BioSymphony Ferm DoE campaigns that bridge 10 mL shake flasks, plates, microbioreactors, and roughly 2 L controlled bioreactors. This survey intentionally excludes generic biology databases unless they supply executable model/spec infrastructure.

## Recommendation summary

| Priority | Tool/spec | Use in BioSymphony | Adoption posture |
|---|---|---|---|
| P0 | BoFire | Constrained DoE, multi-objective BO, mixed continuous/categorical spaces, later multi-fidelity plate/flask/reactor planning | Keep as optional adapter; already aligned with `docs/BOFIRE_POSITIONING.md` |
| P0 | pyDOE3 | Stdlib-adjacent canonical DOE families, optimal-design helpers, PB/CCD/Box-Behnken/LHS | Keep as lightweight optional DOE backend |
| P0 | SALib | Sensitivity and factor-prioritization diagnostics for scale and media uncertainty | Keep optional diagnostics adapter |
| P1 | FedBatchDesigner | Fed-batch growth-arrested process planning ideas and UI/reference model for feed schedules | Prototype a local reference import/example, not core dependency |
| P1 | PyPlate | Plate/deep-well recipe and transfer representation for high-throughput downscale arms | Use as a pattern or optional pack for plate execution exports |
| P1 | BioSTEAM | Biorefinery TEA/LCA/process context for fermentation-derived products and media-cost tradeoffs | Adapter/reference only; useful for cost and downstream context |
| P1 | libRoadRunner / Tellurium / AMICI + SBML/SED-ML/PEtab | SBML model execution, sensitivity, parameter-estimation interchange for mechanistic campaign sidecars | Support import/export sidecars before deep runtime integration |
| P1 | Pyomo.DAE | Dynamic fed-batch/feed-control optimization and constraint checking | Optional advanced adapter; useful when feed profiles become continuous decisions |
| P2 | DWSIM | Flowsheet/process simulation for biofuels, fermentation, downstream, TEA/LCA comparisons | Export/import boundary only; GPL and GUI/heavy runtime risk |
| P2 | CADET | Bioprocess unit-operation modeling, especially downstream chromatography/filtration; claims fermentation scope | Track for downstream and unit-operation packs; GPL limits embedding |
| P2 | COBRApy | Strain/metabolic feasibility priors, substrate/product yield bounds | Evidence-sidecar only; avoid making GEMs the planning core |
| Watch | AutoOED, OPTIMEO, Ax, BoTorch, Opti/mopti | BO/experiment orchestration ideas, UX, and low-level algorithm substrate | Learn from; avoid duplicating full platforms |
| Watch | OpenModelica/FMI | General dynamic process models and FMU interchange | Good future export target; high integration cost for v1 |

## Detailed survey

### BoFire

- Link: https://github.com/experimental-design/bofire
- License: BSD-3-Clause.
- Source signal: BoFire describes itself as an experimental design and Bayesian optimization framework for real experiments, with mixed continuous/discrete/categorical spaces, constraints, single- and multi-objective BO, constrained sampling, serializable problem/strategy objects, and an LLM warm-start strategy.
- Fit: strongest near-term match for media constraints, n-choose-k ingredient limits, multi-objective titer/productivity/byproduct tradeoffs, categorical factor spaces, and future multi-fidelity plate/flask/reactor planning.
- Risks: PyTorch/BoTorch runtime heft; must not replace BioSymphony's manifest, readiness, artifact, and lab-packet layer. Conditional biological constraints still need careful translation and fail-closed reports.
- Adoption priority: P0. Keep optional adapter-backed routing. Add fixture campaigns for constrained media, multi-objective reactor follow-up, and scale-fidelity labels before making claims.

### pyDOE3

- Link: https://pypi.org/project/pyDOE3/
- License: BSD-3-Clause.
- Source signal: current PyPI release is `1.6.2` from 2026-01-12. It provides classical designs and optimal-design utilities including Plackett-Burman, factorial, Box-Behnken, central composite, Latin hypercube, low-discrepancy sequences, Taguchi, sparse grid, and A/C/D/E/G/I/S/T/V optimal criteria.
- Fit: good lightweight source for canonical first-wave design families in screening, RSM, and space-filling scout workflows.
- Risks: generic DOE package, not fermentation-aware. Must run BioSymphony feasibility, aliasing, constant-factor, assay-readiness, and scale-bridge checks after any generated design.
- Adoption priority: P0. Keep as optional DOE backend and document claim levels as canonical-family generation, not lab validation.

### SALib

- Link: https://salib.readthedocs.io/
- License: MIT, per GitHub metadata checked 2026-05-15.
- Source signal: sensitivity-analysis library for methods such as Sobol, Morris, and FAST.
- Fit: useful for ranking uncertain factors in kLa/OTR/OUR bridge recipes, media-cost models, assay-power assumptions, and fed-batch parameter sweeps.
- Risks: sensitivity results can look more precise than the input assumptions deserve. Requires declared parameter ranges and response models.
- Adoption priority: P0/P1. Keep optional diagnostics adapter; emit `claim_level: sensitivity_screening`.

### FedBatchDesigner

- Link: https://github.com/julibeg/FedBatchDesigner and https://pubs.acs.org/doi/abs/10.1021/acssynbio.5c00357
- License: MIT.
- Source signal: ACS Synthetic Biology article describes a dashboard for modeling and optimizing growth-arrested fed-batch processes; the source is MIT licensed. It represents process stages as Python classes that compute biomass, product, and volume as feed volume/time change.
- Fit: directly relevant to fed-batch planning, feed-volume limits, growth-rate assumptions, and harvest/productivity projections at 2 L scale.
- Risks: current repository has low GitHub adoption signal. It is process-specific and may not cover ordinary growth-associated microbial fed-batch, mammalian fed-batch, oxygen limits, or kLa explicitly.
- Adoption priority: P1. Build a reference notebook or sanitized example pack that compares BioSymphony feed-policy fields against FedBatchDesigner concepts.

### PyPlate

- Link: https://pyplate-hte.readthedocs.io/
- License: Apache-2.0.
- Source signal: PyPlate designs and implements high-throughput chemistry and biology experiments, including parameter-space selection and liquid/solid handling steps in 96-well plates.
- Fit: strong pattern for plate/deep-well arm export, reagent inventory transforms, final well volume checks, and liquid-handling recipe artifacts.
- Risks: plate-centric, not a fermentation scale-bridge model. Shake flask and 2 L bioreactor semantics need separate bridge policies.
- Adoption priority: P1. Use as an optional plate-export pack or schema inspiration for `plate_arm_manifest.json`.

### BioSTEAM

- Link: https://github.com/BioSTEAMDevelopmentGroup/biosteam
- License: University of Illinois/NCSA Open Source License.
- Source signal: BioSTEAM supports design, simulation, TEA, and LCA under uncertainty, and its README says it has modeled fermentation-based bioproduct pathways from crops, waste, and flue gas to diols, organic acids, oleochemicals, and biofuels.
- Fit: useful for cost/L, downstream context, feedstock/media cost projections, and fermentation-derived product TEA/LCA examples.
- Risks: more biorefinery/process-economics oriented than 10 mL to 2 L upstream readiness. Thermodynamics and downstream flowsheets can distract from bench-run executability.
- Adoption priority: P1. Keep as optional cost/downstream sidecar, not campaign core.

### libRoadRunner, Tellurium, AMICI, SBML, SED-ML, and PEtab

- Links: https://github.com/sys-bio/roadrunner, https://github.com/sys-bio/tellurium, https://pypi.org/project/amici/0.26.1/, https://docs.biosimulators.org/Biosimulators_AMICI/about.html
- Licenses: libRoadRunner Apache-2.0, Tellurium Apache-2.0, AMICI BSD-3-Clause. SBML/SED-ML/PEtab are standards/ecosystem formats rather than a single runtime license.
- Source signal: libRoadRunner supports SBML model simulation with Python bindings; AMICI imports SBML/PySB, generates C++ code, uses CVODES/IDAS, and supports sensitivity analysis; Tellurium bundles SBML simulation workflows.
- Fit: mechanistic-model sidecars for growth/substrate/product kinetics, parameter-estimation handoffs, and simulation provenance. Good for reproducible example models and future simulator adapters.
- Risks: most public SBML models are intracellular/network models, not complete vessel/feed/oxygen-transfer models. Translating kLa, OUR, feed, volume, and sampling events into SBML/PEtab requires conventions.
- Adoption priority: P1. Define a `mechanistic_model_sidecar` contract with model file, solver, parameter table, event/feed schedule, oxygen-transfer assumptions, and output mapping.

### Pyomo.DAE

- Link: https://pyomo.readthedocs.io/en/6.9.3/explanation/modeling/dae.html
- License: BSD-style, per Pyomo repository license.
- Source signal: Pyomo.DAE supports ordinary/differential algebraic equation models, transformations for simultaneous discretization, simulation utilities, and dynamic-optimization initialization.
- Fit: suitable when BioSymphony needs to optimize continuous feed profiles, enforce volume/substrate/oxygen constraints, or solve dynamic feasibility checks for fed-batch campaigns.
- Risks: solver stack can become heavy and site-specific. Nonlinear dynamic optimization needs careful scaling and feasible initial guesses.
- Adoption priority: P1. Add only behind an advanced optional adapter and start with deterministic feasibility checks, not optimization claims.

### DWSIM

- Link: https://dwsim.org/ and https://github.com/DanWBR/dwsim
- License: GPL v3.
- Source signal: DWSIM advertises batch reactor design/scale-up plus biofuels, biotech, bioprocessing, fermentation and bioreactor design, downstream processing, biorefinery flowsheets, Python/.NET/COM automation, and CAPE-OPEN support.
- Fit: useful as an external flowsheet simulator for downstream, biorefinery, and process-economics scenarios.
- Risks: GPL v3 limits embedding in a permissive or mixed-license package. The runtime is heavy and broad; fermentation features may be less direct than custom upstream readiness models.
- Adoption priority: P2. Treat as export/import target or operator-run external reference, not a dependency.

### CADET

- Link: https://github.com/cadet
- License: GPL-3.0 for CADET-Core and listed ecosystem repositories.
- Source signal: CADET positions itself as a bioprocess modeling platform with hierarchical models, efficient solvers, computational engineering tasks, and unit operations including chromatography, filtration, crystallization, auxiliary components, and fermentation.
- Fit: valuable for downstream chromatography/filtration sidecars and advanced unit-operation modeling when dossiers grow beyond upstream planning.
- Risks: GPL embedding risk; upstream fermentation fit needs validation. It is not a shake-flask-to-2 L DoE planner.
- Adoption priority: P2. Track for downstream packet generation and model-calibration examples.

### COBRApy

- Link: https://github.com/opencobra/cobrapy
- License: GPL-2.0.
- Source signal: COBRApy is a Python package for constraint-based metabolic-network modeling.
- Fit: can provide substrate/product feasibility priors, yield-bound sanity checks, and strain/metabolic evidence rows.
- Risks: genome-scale model predictions are not process-readiness evidence. GPL-2.0 and model-license variance argue for sidecar-only usage.
- Adoption priority: P2. Use only through evidence rows and optional notebooks; do not make GEM simulation part of the default campaign engine.

### AutoOED, OPTIMEO, Ax, BoTorch, and Opti/mopti

- Links: https://github.com/yunshengtian/AutoOED, https://github.com/colinbousige/OPTIMEO, https://github.com/facebook/Ax, https://github.com/meta-pytorch/botorch, https://github.com/basf/mopti
- Licenses: AutoOED MIT per paper, OPTIMEO MIT, Ax MIT, BoTorch MIT, Opti/mopti BSD-3-Clause but deprecated in favor of BoFire.
- Source signal: AutoOED and OPTIMEO provide experiment-optimization applications; Ax is an adaptive-experimentation platform; BoTorch is the low-level PyTorch BO substrate; Opti/mopti is deprecated and points users to BoFire.
- Fit: useful for UX, orchestration, candidate-selection, and benchmark ideas. BoTorch remains important indirectly through BoFire.
- Risks: general optimization platforms do not encode assay readiness, scale bridges, reagent/equipment constraints, or lab packet handoff semantics.
- Adoption priority: Watch. Avoid turning BioSymphony into a generic BO app.

### OpenModelica and FMI/FMUs

- Link: https://openmodelica.org/
- License: mixed open-source stack under OSMC/EPL/GPL-style components; check component license before embedding.
- Source signal: OpenModelica is an open-source Modelica-based modeling, compilation, and simulation environment for industrial and academic usage, with ongoing 2026 releases.
- Fit: useful long-term for dynamic process models and FMU exchange if users bring Modelica vessel/control models.
- Risks: high integration cost; Modelica model availability for bench fermentation is uneven.
- Adoption priority: Watch/P2. Define export boundaries before runtime integration.

## Gaps and practical implications

- There is no single mature open-source package that cleanly handles 10 mL shake flask to 2 L bioreactor readiness with media constraints, kLa/OTR/OUR, fed-batch feed policies, assay readiness, DoE, and lab packet generation.
- The highest-value architecture remains a BioSymphony manifest and dossier core with optional adapters. BoFire, pyDOE3, SALib, SBML runtimes, PyPlate, BioSTEAM, and Pyomo.DAE should serve bounded tasks.
- kLa/OTR/OUR support should stay in BioSymphony as an explicit scale-bridge recipe layer. External tools can provide simulation or optimization backends, but they do not replace campaign-specific vessel geometry, correlation choice, broth qualification, offgas availability, or recapitulation criteria.
- Licenses matter. BSD/MIT/Apache/UIUC tools can be optional dependencies more easily. GPL tools such as DWSIM, CADET, and COBRApy should remain external or sidecar-oriented unless the repo's distribution posture changes.

## Proposed adoption backlog

1. P0: Lock optional-backend documentation for BoFire, pyDOE3, and SALib in `docs/engine-implementation.md` and examples.
2. P0: Add a machine-readable tool registry under `docs/` or `templates/` with tool name, license, package, route, claim level, and fail-closed behavior.
3. P1: Add a `mechanistic_model_sidecar` schema for SBML/PEtab/AMICI/libRoadRunner handoffs.
4. P1: Add a `plate_recipe_sidecar` or `plate_arm_manifest` extension inspired by PyPlate for well-volume and reagent-transfer checks.
5. P1: Add one fed-batch feed-policy reference example that compares BioSymphony's phase/feed fields to FedBatchDesigner-style stage math.
6. P1: Add BioSTEAM as an external cost/downstream reference in media-cost examples, not as a core dependency.
7. P2: Add exporter notes for DWSIM, CADET, OpenModelica/FMU, and COBRApy sidecars without embedding GPL runtimes.

## Sources checked

- BoFire: https://github.com/experimental-design/bofire
- pyDOE3: https://pypi.org/project/pyDOE3/
- BioSTEAM: https://github.com/BioSTEAMDevelopmentGroup/biosteam
- DWSIM: https://dwsim.org/ and https://github.com/DanWBR/dwsim
- Pyomo.DAE: https://pyomo.readthedocs.io/en/6.9.3/explanation/modeling/dae.html
- FedBatchDesigner: https://github.com/julibeg/FedBatchDesigner and https://pubs.acs.org/doi/abs/10.1021/acssynbio.5c00357
- PyPlate: https://pyplate-hte.readthedocs.io/
- libRoadRunner: https://github.com/sys-bio/roadrunner
- AMICI: https://pypi.org/project/amici/0.26.1/ and https://docs.biosimulators.org/Biosimulators_AMICI/about.html
- CADET: https://github.com/cadet
- OpenModelica: https://openmodelica.org/
- Ax: https://github.com/facebook/Ax
- BoTorch: https://github.com/meta-pytorch/botorch
- OPTIMEO: https://github.com/colinbousige/OPTIMEO and https://joss.theoj.org/papers/10.21105/joss.08510
- AutoOED: https://github.com/yunshengtian/AutoOED and https://arxiv.org/abs/2104.05959
- Opti/mopti: https://github.com/basf/mopti
- COBRApy: https://github.com/opencobra/cobrapy
