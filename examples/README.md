# Public Examples

All top-level examples are public-safe fixtures. They are useful for learning the contract, testing agent harnesses, and checking optional adapter routes. They are not proof of physical execution, assay validation, production readiness, or scale-transfer success.

Run every top-level example:

```bash
make validate-all
```

## Which Example Should I Run?

| Need | Example | First command |
|---|---|---|
| Fastest end-to-end tutorial | [`demo-pb-screening-public/`](demo-pb-screening-public/) | `ferm-doe validate examples/demo-pb-screening-public --summary` |
| Smallest manifest to inspect | [`demo-xylanase-public/`](demo-xylanase-public/) | `ferm-doe validate examples/demo-xylanase-public --summary` |
| Scale-down qualification shape | [`demo-scale-bridge-public/`](demo-scale-bridge-public/) | `ferm-doe bridge-qualification examples/demo-scale-bridge-public --out /tmp/bridge.csv` |
| Split-plot fed-batch shape | [`demo-split-plot-fedbatch-public/`](demo-split-plot-fedbatch-public/) | `ferm-doe validate examples/demo-split-plot-fedbatch-public --summary` |
| Validator guidance path | [`demo-warnings-walkthrough-public/`](demo-warnings-walkthrough-public/) | `ferm-doe validate examples/demo-warnings-walkthrough-public --summary` |
| BoFire constrained media-cost route | [`demo-media-cost-bofire/`](demo-media-cost-bofire/) | `ferm-doe validate examples/demo-media-cost-bofire --summary` |
| Scale transfer with historical ledger ingest | [`demo-shakeflask-to-2l-bofire/`](demo-shakeflask-to-2l-bofire/) | `ferm-doe validate examples/demo-shakeflask-to-2l-bofire --summary` |
| Multi-arm scale-transfer fixture | [`engine-multi-arm-scale-transfer-public/`](engine-multi-arm-scale-transfer-public/) | `ferm-doe validate examples/engine-multi-arm-scale-transfer-public --summary` |
| Reference DOE utility fixture | [`reference-doe-custom-design/`](reference-doe-custom-design/) | `ferm-doe engine utility custom-optimal --manifest examples/reference-doe-custom-design/campaign_manifest.json --out /tmp/custom-optimal --run-budget 12` |
| Public-paper starter | [`xylanase-wxz1-2012/`](xylanase-wxz1-2012/) | `ferm-doe validate examples/xylanase-wxz1-2012 --summary` |
| Product-class starter | [`yeast-isoprenoid-2l-fedbatch/`](yeast-isoprenoid-2l-fedbatch/) | `ferm-doe validate examples/yeast-isoprenoid-2l-fedbatch --summary` |
| ENTMOOT NChooseK smoke | [`entmoot-nchoosek-smoke/`](entmoot-nchoosek-smoke/) | `python examples/entmoot-nchoosek-smoke/smoke.py` |
| Backend comparison surface | [`adaptive-backend-eval/`](adaptive-backend-eval/) | `python skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py docs/adaptive-backend-evaluation.json` |

## Expected Status

Most examples intentionally report `YELLOW`: they are planning artifacts with synthetic or public-source evidence, not completed lab evidence. A healthy public checkout means `error_count == 0` for every top-level example. Warnings are expected where an example is designed to teach guidance, optional inputs, or profile-advised artifacts.

## Public-Safety Rules

- Use synthetic, public-paper-derived, or source-metadata-only rows.
- Do not include exact private recipes, strains, customer records, unpublished sequences, supplier quotes under NDA, or API credentials in this repo.
- Keep public worked examples labeled with `claim_level: public_synthetic_demo`.
- Treat handoff packets in this repo as planning artifacts unless a separate private workspace adds execution evidence and approvals.
