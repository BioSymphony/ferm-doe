# Public Security Model

BioSymphony Ferm DoE is local-first by default. The public repo should be useful without requiring credentials, cloud accounts, private data, or network access.

## Local-First Boundary

- The core CLI uses local files and standard-library paths by default.
- Optional scientific dependencies are installed only when a user chooses the matching extra.
- Public examples use synthetic, public-paper-derived, or source-metadata-only rows.
- Deployment scaffolds are reference adapters, not default execution paths.

## Data Boundary

Do not store API keys, tokens, private process records, private strain details, customer batch records, unpublished sequences, supplier quotes under NDA, or confidential media formulations in this repo.

Use one of these public-safe substitutes:

- synthetic rows with clear `claim_level: public_synthetic_demo`
- public-source summaries with source, license, and transformation notes
- source-metadata-only rows when reuse rights are unclear
- secure-store references in private campaign workspaces

## Scanner Boundary

The public release scanner is intentionally conservative and standard-library only:

```bash
PYTHONPATH=src python -m biosymphony_ferm_doe.public_release --json .
ferm-doe audit .
make public-ready
```

It blocks workstation paths, key-like values, bearer-token headers, tracker identifiers, private orchestration markers, provider runtime identifiers, and unsupported private-campaign markers. `make public-ready` also requires gitleaks history and working-tree scans. `audit-skip` is line-scoped and rule-specific; use it only for synthetic scanner fixtures or documentation examples that name the exact rule being skipped.

## CI Boundary

Public CI should keep secret scanning independent of the test matrix and should run on pull requests as well as pushes. The release gate should fail closed when examples stop validating, optional backend surfaces drift, or public-safety scans find blockers.

## Deployment Boundary

Reference deployment examples must be treated as scaffolds:

- keep auth in provider secrets or upstream identity, not request bodies
- prefer `Authorization: Bearer <token>` over payload fields
- compare shared tokens with constant-time comparison
- reject oversized requests and unexpected payload shapes
- add spend, rate, and logging-retention controls before serving other users
- pin dependency ranges or build from a reviewed local source

Cloud providers should execute bounded artifact tasks only. They should not become the campaign brain, hold private biological data by default, or silently fall back to a different execution route.

## Public Worked Examples

Worked examples should teach planning, validation, and claim boundaries. They should not read as executable operator packets. If an example includes a handoff-like artifact, it must say that the artifact is a non-executable public case study unless a separate private workspace adds execution evidence, operator approval, and lab-specific controls.
