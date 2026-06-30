# Tool Registry Refresh - 2026-06-21

Public-safe research sweep for recent or currently active tools, repos, and preprints related to the BioSymphony Ferm DoE tool knowledge base.

## Selected Entries

These were added to `docs/tool-registry.json` because they have a clear public route and fail-closed boundary.

| Entry | Why it belongs | Primary sources |
| --- | --- | --- |
| `xopt` | Constrained, parallel, and multi-objective Bayesian optimization for arbitrary scientific objectives. Useful as a comparison backend for constrained public fixtures. | [repo](https://github.com/xopt-org/Xopt), [docs](https://xopt.xopt.org/), [PyPI](https://pypi.org/project/xopt/) |
| `trieste` | Active TensorFlow BO toolbox with ask-tell, batch/asynchronous, constrained, multi-fidelity, and multi-objective routes. Kept as watch due to stack weight. | [repo](https://github.com/secondmind-labs/trieste), [docs](https://secondmind-labs.github.io/trieste/), [PyPI](https://pypi.org/project/trieste/) |
| `tabicl_v2` | Recent open tabular foundation model to watch next to the existing TabPFN adapter, especially for larger public result tables. | [repo](https://github.com/soda-inria/tabicl), [docs](https://tabicl.readthedocs.io/), [arXiv v2](https://arxiv.org/abs/2602.11139), [PyPI](https://pypi.org/project/tabicl/) |
| `petab_libpetab` | Contract layer for parameter-estimation fixtures around SBML/ODE sidecars. | [repo](https://github.com/PEtab-dev/libpetab-python), [docs](https://petab.readthedocs.io/), [PyPI](https://pypi.org/project/petab/) |
| `pypesto` | Parameter-estimation and uncertainty sidecar for public or synthetic mechanistic models. | [repo](https://github.com/ICB-DCM/pyPESTO), [docs](https://pypesto.readthedocs.io/), [PyPI](https://pypi.org/project/pypesto/), [paper](https://doi.org/10.1093/bioinformatics/btad711) |
| `pseudobatch` | Fed-batch sample-withdrawal correction reference for preprocessing public ledgers before growth-rate or response modeling. | [repo](https://github.com/biosustain/pseudobatch), [docs](https://biosustain.github.io/pseudobatch/), [PyPI](https://pypi.org/project/pseudobatch/), [preprint](https://doi.org/10.1101/2024.05.27.596043) |
| `eln_file_format` | ELN/LIMS-neutral run-packet interchange candidate built on RO-Crate conventions. | [repo/spec](https://github.com/TheELNConsortium/TheELNFileFormat), [IANA media type](https://www.iana.org/assignments/media-types/application/vnd.eln+zip), [RO-Crate use case](https://www.researchobject.org/ro-crate/eln) |
| `grobid_fulltext` | Public scholarly PDF structuring sidecar for open-access evidence and citation-context extraction. | [repo](https://github.com/grobidOrg/grobid), [docs](https://grobid.readthedocs.io/), [releases](https://github.com/grobidOrg/grobid/releases) |
| `openalex_official` | Broad public metadata and citation-graph context beyond PubMed. Kept as watch because API access/rate limits can change. | [docs](https://developers.openalex.org/), [PyPI](https://pypi.org/project/openalex-official/), [paper](https://arxiv.org/abs/2205.01833) |
| `europe_pmc_api` | Life-science literature, preprint, open full-text, and annotation source. Kept as watch due to source-license variance. | [developers](https://europepmc.org/developers), [REST API](https://europepmc.org/RestfulWebService), [annotations API](https://europepmc.org/AnnotationsApi) |

The existing `ro_crate` entry was also refreshed to mention Workflow Run RO-Crate, `ro-crate-py`, and `rocrate-validator` as optional profile-aware context.

## Deferred Notes

These remain notes rather than immediate registry additions or dependencies.

| Candidate | Reason deferred |
| --- | --- |
| OpenBox | Relevant black-box optimizer, but its service/AutoML surface overlaps orchestration and is less directly lab-facing than Xopt. |
| NIMO / NIMO Controller | Useful self-driving-lab reference, but robotics/control-plane concepts should not replace BioSymphony manifest or safety gates. |
| Optuna and SMAC3 | Mature optimizers; useful benchmarks, but less DoE/lab-specific than current BayBE, Ax, BoFire, Xopt, and ENTMOOT surface. |
| HEBO / MCBO and GIT-BO | Interesting mixed/combinatorial and tabular-surrogate research, but package cadence, repo shape, or GPU requirements make them watch notes. |
| Multi-stage BO for SDLs | Conceptually useful for intermediate observables; no clear code license found, so keep as literature note. |
| BiRD, IDAES, GEKKO, do-mpc | Useful process/model/control sidecars, but solver and domain weight would need a concrete public fixture before registry promotion. |
| ISA-API and DataPLANT ARC | Strong metadata patterns; license/platform breadth need a narrower export target before adoption. |
| Datalad, PaperQA2, A2A | Useful for large artifacts, research automation, or agent handoff; not needed until a concrete dossier or handoff adapter exists. |
