# Public Release Prep

Clean, no-history public-prep workspace for BioSymphony Ferm DoE.

## Status

- [x] Public-safe `SKILL.md` with long-agent loop.
- [x] Profile registry (screening, optimization_rsm, mixture, split_plot_fed_batch, scale_up_bridge, scale_down_qualification, confirmation, sequential_augmentation, custom).
- [x] Multi-criterion `scale_context` block.
- [x] `arms[]` multi-arm campaigns.
- [x] Per-axis `readiness` state.
- [x] DoE family taxonomy with minimum-runs guidance.
- [x] `decision_rules`, `stop_rules`, `risk_register`, `assumptions` blocks.
- [x] JSON Schema (`schemas/campaign_manifest.schema.json`).
- [x] Public demos covering screening, scale bridge, split-plot, closed-loop follow-up, warning guidance, constrained BoFire routes, adaptive backend fixtures, and starter-study shapes.
- [x] CLI `--summary`, `--out`, `# audit-skip:` markers.
- [x] Adaptive follow-up planning CLI (`plan-wave2`) with public-safe artifacts.
- [x] Response-level assay-power CLI (`assay-power`).
- [x] Self-learning ledger, hiccup review, and arm-scoped negative memory runbook.
- [x] Public task request schema and validator (`validate-task-request`).
- [x] Compact public dossier contract check (`check-dossier`).
- [x] Public-safe evidence and scientific-swarm issue-pack contracts.
- [x] Canonical `NON_CLAIMS.md`.
- [x] Local validation gate (`make release-check`).
- [x] Public adaptive-backend evaluation surface (`docs/adaptive-backend-evaluation.json`) with fixture matrix and validator.
- [x] Optional OMLT and TabPFN adapter surfaces stay inert without runtime extras/tokens.
- [x] Smoke-artifact semantic contract blocks `PASS` artifacts with constraint violations or invalid route/fallback state.
- [x] Public-ready local gate (`make public-ready`) chains release checks and required secret scan.
- [x] Newcomer docs: agent quickstart, use cases, docs index, and release readiness checklist.
- [x] Paid-provider evidence stays out of the public snapshot; this repo carries sanitized backend fixtures, adapter-boundary docs, registry metadata, and validators rather than raw RunPod closeouts or provider packets.
- [ ] Decide the public remote, repository visibility, and release tag.
- [ ] Re-run history and tree scans immediately before first push.

## Local Release Checks

```bash
make release-check
```

For a public-switch local rehearsal that also invokes the required secret scan:

```bash
make public-ready
```

Or:

```bash
python3 -m unittest discover -s tests
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/demo-xylanase-public
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py templates/task_request.template.json
make validate-all
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate-task-request templates/task_request.template.json
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli check-dossier examples/demo-xylanase-public
PYTHONPATH=src python3 skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py docs/adaptive-backend-evaluation.json
```

Expected outcomes:

- All top-level example manifests validate to `GREEN` or `YELLOW` with `error_count == 0`.
- The diagnostic walkthrough intentionally reports guidance warnings; other warnings are public planning caveats, not privacy or schema failures.
- The scoped public-release scanner in `nox -s public_release` reports `PASS`.
- A full-tree `ferm-doe audit .` reports `PASS` in this public checkout.
- Local Markdown links resolve via `python scripts/check_markdown_links.py .`.
- Adaptive follow-up artifacts must carry `planned_wave2_design` and must not claim validated optimization or validated scale transfer.
- Adaptive backend fixtures are comparison surfaces only; they must preserve the BioSymphony manifest as source of truth and must not claim lab-ready candidates without readiness, assay, scale, evidence, cost, and handoff checks.

## Secret Scan

Run the required history and tree scan:

```bash
make secret-scan
```

This runs:

```bash
gitleaks detect --source . --no-banner --redact --verbose
gitleaks dir . --no-banner --redact --verbose
```

`detect` checks committed history. `dir` checks the current working tree, including public-release draft files that may not be committed yet.

Use `make secret-scan-optional` only for local diagnostics on machines where `gitleaks` may not be installed. Public release rehearsal should use `make public-ready` and fail closed if the scanner is unavailable.

## Scrub Rules

Do not publish:

- private strain details
- unpublished sequences
- customer batch records
- confidential media formulations
- API keys or provider credentials
- private workstation paths
- private issue-tracker / team / project details
- raw private campaign artifacts

## Public Positioning

- Validates measurement readiness, manifest structure, and profile fit; does not validate lab measurements unless result rows are ingested.
- Produces planning packets, not filled execution records.
- Exports DoE tables but does not claim full commercial DoE parity.
- Local orchestration is the control plane; remote compute is optional and bounded.

## Asset Notes

Diagrams in the README and [`VISUAL_OVERVIEW.md`](VISUAL_OVERVIEW.md) are now inline Mermaid (rendered by GitHub), so they carry no image assets. The remaining raster assets are AI-generated brand images for public-release review:

- `assets/images/biosymphony-ferm-doe-banner.png` (README banner)
- `assets/images/social-preview.png` (GitHub social preview)

The README renders these diagrams inline now, but the raster files are retained and tracked by the release scanner (`Makefile`, `noxfile.py`, `tests/test_public_scaffold.py`): `biosymphony-ferm-doe-pipeline.png`, `biosymphony-agent-loop.svg`, `experiment-design-map.png`, `scale-transfer-criteria.png`, `doe-family-selector.png` (all under `assets/images/`). Removing them would also mean updating that scanner coverage.

## Demo Constraints

- Historical rows must be public-derived or clearly synthetic.
- Source and transformation notes must be explicit in `evidence_table.csv`.
- No private strains, sequences, media formulations, customer records, or unpublished protocols.
- Readiness verdict allowed to be `YELLOW` or `RED`; do not force a fake `GREEN`.
- Include at least one useful caveat per demo so each proves the system can warn or block.

## What each demo proves

| Demo | Proves |
|---|---|
| `demo-xylanase-public` | response/measurement separation; assay-readiness gating; YELLOW with explicit reasons |
| `demo-scale-bridge-public` | scale_context with multi-criterion bridge; multi-arm; recapitulation criterion declared |
| `demo-split-plot-fedbatch-public` | hard-to-change vs easy-to-change factor distinction; whole-plot id in design rows |
| `demo-pb-screening-public` | Plackett-Burman screening loop with synthetic first-batch results and follow-up planning |
| `demo-warnings-walkthrough-public` | intentional validator guidance warnings; non-blocking YELLOW with `error_count == 0` |

## Adaptive follow-up Constraints

- `plan-wave2` may recommend confirm, narrow, expand, pause, stop, or scale/downscale planning.
- Rows with failed QC, explicit exclusion, or low trust must not drive the recommendation.
- Multiple arms must not be pooled into one narrowing decision unless an active arm or per-arm policy is explicit.
- Derived cost, duration, and calculated responses must not receive fake assay requirements.
- Scale/downscale recommendations remain planning candidates until bridge evidence is reviewed.
