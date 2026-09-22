# AI And Research Tool Review, 2026-09-22

Evaluate document extraction and uncertainty-aware surrogate models before adding another optimization platform. The existing registry covers the main optimizer families. The remaining gaps concern evidence traceability, predictive uncertainty, and compatibility with recent releases.

## Release Changes

These are source checks. Supported dependency ranges remain in `pyproject.toml`.

| Tool | Verified release | Consequence |
| --- | --- | --- |
| TabPFN | [9.0.0, September 15](https://pypi.org/project/tabpfn/9.0.0/) | Outside the supported `>=8,<9` range. Review API behavior and checkpoint terms before a separate compatibility test. |
| TabICL | [2.2.0, September 2](https://pypi.org/project/tabicl/2.2.0/) | Refresh the comparison candidate; measure regression uncertainty and memory use on small tables. |
| Xopt | [3.2.2, September 3](https://pypi.org/project/xopt/3.2.2/) | Retain the external-evaluator comparison; a release check does not establish constraint parity. |
| PEtab | [0.9.0, September 7](https://pypi.org/project/petab/0.9.0/) | Requires Python 3.12 or newer; keep calibration evaluation in a separate environment. |
| pyPESTO | [0.7.0, September 9](https://pypi.org/project/pypesto/0.7.0/) | Requires Python 3.11 or newer; test the PEtab/model round trip before using outputs. |
| SMT | [2.15.0, September 8](https://pypi.org/project/smt/2.15.0/) | Keep surrogate diagnostics optional; evaluate SMT-optim separately for constrained multi-fidelity comparisons. |

The [OpenAlex authentication guide](https://help.openalex.org/api/authentication/) permits basic keyless queries and offers a larger allowance with a key. Check endpoint budgets before harvesting. [Europe PMC](https://europepmc.org/RestfulWebService) remains a source for references, article status, and open-access full text. Record reuse rights per article.

## AI Evidence Candidates

| Candidate | Proposed evaluation | Required evidence |
| --- | --- | --- |
| [Docling](https://github.com/docling-project/docling), [2025 report](https://arxiv.org/abs/2501.17887) | Extract tables with page coordinates and structured JSON. | Exact cells, units, footnotes, and page anchors on a small public fixture. MIT code; review model terms separately. |
| [olmOCR 2](https://github.com/allenai/olmocr), [2025 preprint](https://arxiv.org/abs/2510.19817) | Compare a vision fallback on scanned pages. | Numeric fidelity and runtime cost. Its 7B checkpoint stays outside the package. |
| [PaperQA2](https://github.com/Future-House/paper-qa), [2024 preprint](https://arxiv.org/abs/2409.13740) | Draft source-linked answers for review. | Passage support, contradictory evidence, and resolved citations. Configure inference explicitly before any service call. |

A registry entry records a candidate, not an implemented adapter. Keep extraction outputs separate from accepted evidence. For each accepted value, retain the source URL, document hash, page or table locator, unit, extraction method, and review state. Model text and retrieved documents are untrusted input to the planning workflow.

## Surrogate And Scale Comparisons

[TabTune](https://github.com/Lexsi-Labs/TabTune) is an evaluation candidate for shared model comparisons, conformal intervals, and grouped or temporal splits. Its [November 2025 preprint](https://arxiv.org/abs/2511.02802) introduces the library. Model checkpoint terms still apply. [MAPIE 1.5.0](https://pypi.org/project/mapie/1.5.0/), released August 5, is a narrower calibration comparison for existing estimators. Its [scikit-learn-compatible interface](https://github.com/scikit-learn-contrib/MAPIE) avoids adding a new foundation-model wrapper. Neither calibration route has been evaluated here.

Compare a GP, the supported TabPFN route, and TabICL quantiles using held-out error, interval coverage, interval width, and compute cost. Include small samples and shifted groups. Conformal guarantees rely on exchangeability, which sequentially selected observations may violate. The [2026 uncertainty preprint](https://arxiv.org/abs/2606.01427) and [GPvsPFN code](https://github.com/kianswarehouse/GPvsPFN) supply an external comparison reference; their findings have not been reproduced here.

[SMT-optim](https://github.com/SMTorg/smt-optim) adds a constrained, mixed-variable, multi-fidelity comparison to the existing SMT entry. The [September 9 revision of the scale BO preprint](https://arxiv.org/abs/2508.10970v2) is a relevant simulation study. Evaluate cost-normalized recommendations on a repository-owned synthetic fixture before proposing an adapter. Simulation results do not establish physical scale transfer.

## Language-Informed Optimization

[GOLLuM](https://github.com/schwallergroup/gollum), published [August 28, 2026](https://doi.org/10.1038/s42256-026-01283-z), trains language representations through a Gaussian-process objective. Its 23-task study makes it a useful comparison candidate. Test constraint preservation, uncertainty, and compute cost against existing GP and TabPFN routes on synthetic data before adding an adapter.

The [2025 LLAMBO reproducibility preprint](https://arxiv.org/abs/2511.18891) supports benchmark-specific contextual warmstart findings. It does not establish a general early-trial advantage or transfer to fermentation. The registry now scopes LLAMBO to a warmstart comparison. The [zero-shot TabPFN BO implementation](https://github.com/amazon-science/tabpfn-automl2026) extends the existing surrogate evaluation; its reproduced model version differs from the supported adapter range.

The [August 2026 Sara/lenz preprint](https://arxiv.org/abs/2608.00316) describes an agent revising a Bayesian optimization strategy. The inspected record did not establish an installable release or software license. Retain it as a reading reference until those artifacts are available.

## Evaluation Order

1. Compare Docling with the existing extraction workflow on source-linked public fixtures.
2. Measure GP, TabPFN, and TabICL predictive error and interval coverage; use TabTune only if its dependencies and checkpoint terms fit.
3. Compare GOLLuM on a small synthetic objective after defining a compute budget and deterministic constraint checks.
4. Revisit additional parsers and agent frameworks only when the preceding fixtures show an unmet need.

Store links, metrics, and small fixtures in the repository. Keep models, full paper collections, and upstream repository snapshots in an external artifact store. Existing optional dependencies and adapter claims remain unchanged.
