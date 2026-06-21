# Open-Data Publication Strategy

> **Status: STRATEGY, not authorization to publish.**
> This document describes the path the user could take *if* they decide to release a BioSymphony Ferm DoE campaign as a citable open scientific data bundle. No deposit, no remote push, and no DOI minting should happen without explicit user authorization.

**Audience:** future operator (likely the user, possibly a delegated agent) deciding whether and how to publish a BioSymphony Ferm DoE campaign.

**Scope:** packaging, venue choice, license, redaction, and citation, for the *computational planning dossier* (not for any physical-execution results).

---

## 0. Decision Tree (Read Me First)

Before any of the sections below, the user should answer these gates:

1. **Is the campaign *intended* to be public?** A campaign authored under `claim_level: public_synthetic_demo` carries no proprietary biology, so the structural answer is yes; final approval is the user's.
2. **Is the user ready to mint a DOI?** A DOI is permanent. Once issued, the version it points to should be considered immutable from a citation standpoint, even if the *concept DOI* allows newer versions.
3. **Is a methodology narrative ready to stand alongside the data, or does the data ship alone first?** Data-only deposits are valid and citable; a manuscript can follow as a separate DOI that cites the data DOI.
4. **What audience matters more: software-DOE peers (Digital Discovery, Zenodo SDL community) or bioprocess peers (JCTB, *Biotechnol Bioeng*, *Biotechnol Prog*)?** Different venues, different bundle shapes.

If any gate is "no" or "not yet," stop here and revisit after that gate closes.

---

## 1. Target Venue Analysis

### 1.1 Comparison matrix

| Criterion | Zenodo | Figshare | Dryad | Journal Supplementary |
|---|---|---|---|---|
| **DOI minting** | Yes, automatic, concept + version DOIs | Yes, per-file or per-collection DOIs | Yes, per-package DOI | Yes, but tied to the article DOI; no granular concept versioning |
| **File-size limit** | 50 GB/record (soft); higher on request | 20 GB/file standard | 300 GB/dataset | Publisher-dependent, often ≤ 1 GB |
| **License choice** | Full Creative Commons + open-source ladder; CC-BY 4.0 default | CC-BY 4.0 default, choices available | CC0 required (Dryad policy) | Publisher-dependent, often CC-BY 4.0 or restrictive |
| **Indexing** | DataCite, OpenAIRE, Google Dataset Search, Crossref Event Data | DataCite, GDS, ORCID | DataCite, GDS, journal cross-link | DataCite via journal; usually indexed |
| **Versioning** | Concept-DOI + version-DOI (preserves citation if v2 ships) | Per-file DOI; collection-level updates allowed | Versioning supported, but CC0 lock is permanent | None; supplementary updates require errata |
| **GitHub integration** | Native (release-triggered deposits, exact-tree archive) | Via API only | None | None |
| **RO-Crate support** | Profile recognized; `conformsTo` honored in metadata; native ZIP upload | RO-Crate ZIP uploadable, but profile not surfaced in UI | RO-Crate ZIP uploadable; CC0 forced | Not standardized |
| **Cost** | Free (CERN-hosted, EU grant funded) | Free for ≤ 20 GB, paid above | Free if linked to a partner journal; otherwise $120 | Bundled with article processing charge |
| **Embargo support** | Yes, time-bounded | Yes | No | Pre-publication only |
| **Withdrawal** | Tombstone with reason, DOI persists | Tombstone, DOI persists | Tombstone after curator review | Editor-mediated |
| **Curatorial review** | Light (community-curated for thematic collections) | None | Yes (Dryad curators check completeness) | Peer review at article level |

### 1.2 Recommendation

**Primary: Zenodo, with the campaign deposited in the `bofire-community` or `digital-discovery` community.**

Justification, in one sentence: Zenodo is the only venue that combines (a) free hosting, (b) DataCite 4.5 metadata emission automatically, (c) explicit recognition of RO-Crate `conformsTo` profiles in record metadata, and (d) concept-DOI + version-DOI semantics that match how a campaign would actually evolve (v0 → corrected v1 → expanded v2).

**Why not the alternatives:**

- **Figshare:** comparable on most axes, but lacks the GitHub-release-triggered deposit integration that lets `git tag v1.0.0` produce a deposit deterministically. Higher friction to script.
- **Dryad:** CC0-only is too aggressive for a project that may want CC-BY 4.0 attribution and may have a downstream software component that benefits from MIT.
- **Journal supplementary:** locks the data to one article DOI, no concept versioning, and most bioprocess journals impose file-size limits incompatible with a typical campaign bundle, never mind a future multi-campaign release.

**Secondary (recommended only when a methods note publishes):** Quarto Manuscript → MECA bundle → submit to *Digital Discovery* (RSC, open access, DOE/BO/AI-for-science scope) with the Zenodo DOI cross-linked as the data citation. *Digital Discovery* already accepts MECA from Quarto and explicitly endorses Zenodo for code+data.

**Tertiary fallback if the venue conversation stalls:** Strieth-Kalthoff et al. (*Science* 2024, doi:10.5281/zenodo.8357375) and Boyle et al. (ProcessOptimizer, doi:10.5281/zenodo.14179617) are precedent for Zenodo-only deposits without a parallel journal article. They are still highly citable.

---

## 2. DOI Minting Plan (Zenodo)

Concrete steps for getting a Zenodo DOI on a campaign bundle. **None of these should run until the user authorizes.**

1. **Create a Zenodo account** under the user's ORCID. Use the production server, not Sandbox, *only* on the final deposit; do the rehearsal on `sandbox.zenodo.org` first.
2. **Generate a personal access token** with `deposit:actions` and `deposit:write` scopes. Store in a local password manager. Never commit to the repo.
3. **Reserve a concept DOI** by creating a deposit draft (no files yet) and clicking "Reserve DOI." Zenodo returns both the version DOI (e.g. `10.5281/zenodo.XXXXXXX`) and the concept DOI (`10.5281/zenodo.YYYYYYY`, always one lower). The concept DOI is what external citations should point to if the user expects to publish v1, v2, etc.; the version DOI is what an *individual* citation pins to.
4. **Author the deposit metadata** (DataCite 4.5 fields): title, creators (ORCID-linked), description, publication date, resource type = "Dataset" with subtype "Computational Notebook" or "Scientific Workflow," keywords (mirror the RO-Crate `keywords` array), license (`CC-BY-4.0` for the data; declare MIT separately for code if bundled), funding, references.
5. **Embed the concept DOI back into the RO-Crate** (`identifier` field at `./` dataset root) *before* uploading the ZIP. This creates a stable internal-vs-external identifier match.
6. **Upload the RO-Crate ZIP** via the deposit UI or REST API. The ZIP must contain `ro-crate-metadata.json` at the root and everything `hasPart` references. Use `curl` against the deposit API for reproducibility; do not drag-and-drop.
7. **Publish.** This action is irreversible; the DOI activates and propagates to DataCite within minutes and to Google Dataset Search within ~24 h.
8. **Cross-link from GitHub** (only if/when the repo goes public) using the Zenodo–GitHub integration so future `v*` tags automatically deposit a new version under the concept DOI.

**Rehearsal first:** before step 1, the user should walk through steps 2–7 on `sandbox.zenodo.org` to confirm metadata renders, file count matches, and `conformsTo` displays in the Zenodo metadata block. Sandbox DOIs look real but resolve nowhere; they are disposable.

---

## 3. RO-Crate Authoring Workflow

A publication-ready campaign needs a passing RO-Crate (RO-Crate 1.2 + Process Run Crate 0.5 profiles) before deposit. The `rocrate_retrofit.py` helper under `skills/biosymphony-ferm-doe/scripts/` builds a starting crate from a campaign manifest; the steps below describe what to do *on top of* that crate before publication.

### 3.1 Tooling

| Tool | Role | When to run |
|---|---|---|
| `ro-crate-py` (the canonical Python library) | Programmatic crate editing, packing to ZIP | When updating entities or repacking before deposit |
| **Describo** (browser app, https://describo.github.io) | Visual review of the JSON-LD graph | Sanity-check pass before deposit |
| **CheckMyCrate** (https://checkmycrate.research-software.org) | Profile-aware validator | Gate before submission; must pass for both `ro-crate/1.2` and `wfrun/process/0.5` |
| `roc-tools validate` (CLI counterpart of CheckMyCrate) | CI-friendly validator | Use in `make release-check` once profile-locked |

### 3.2 Profiles to declare

Required:
- `https://w3id.org/ro/crate/1.2`, base profile
- `https://w3id.org/ro/wfrun/process/0.5`, Process Run Crate (records `CreateAction` for each phase)

Optional before publication:
- `https://w3id.org/biocompute/1.4.2`, BioCompute Object profile, *if* the campaign is to be cross-referenced from a regulatory or QbD context.
- `https://w3id.org/ro/wfrun/workflow/0.5`, Workflow Run Crate, *if* the planning scripts are bundled as executable workflows rather than as software-application references. Process Run Crate is the lighter-weight default; do not switch without reason.

### 3.3 What to declare

A publication-ready crate should declare:
- Root `Dataset` with name, description, identifier, license, publisher, datePublished, keywords
- Phase-level `CreateAction` entities linking inputs, instruments, and results
- `SoftwareApplication` entities for `biosymphony-ferm-doe` and any optional adapters used (BoFire, ENTMOOT, OMLT, TabPFN, BoTorch)
- File-level entities for every dossier artifact (EVIDENCE/, CITATIONS.json, manifests)
- Any errata as separate `File` entities (matching the literal `@type: File` avoids ambiguity for consumers)

Add before publication:
- `funder`: none, unless a grant applies
- `creator`: individual `Person` entity with ORCID iri (replace any placeholder for human attribution)
- `citation`: any methods-note DOI once it exists, plus the published source citations that anchor the campaign biology
- `isPartOf`: the concept DOI of any parent collection (e.g. `bofire-community`)
- `version`: semantic version string for the campaign bundle (`1.0.0` if this is the first publication-ready cut; `0.x` is fine for sandbox rehearsal)

### 3.4 What `conformsTo` should look like at deposit

```json
"conformsTo": [
  { "@id": "https://w3id.org/ro/crate/1.2" },
  { "@id": "https://w3id.org/ro/wfrun/process/0.5" }
]
```

If the user later decides to also publish planning scripts as a Workflow Run Crate, add `wfrun/workflow/0.5` and demote the existing crate to a sibling. Do not edit the published crate in place.

### 3.5 Repack discipline

Before each deposit:

```text
1. ro-crate-py validate <campaign-dir>/
2. checkmycrate <campaign-dir>/   (or roc-tools validate)
3. zip -r -X <campaign-id>-v1.0.0.zip <campaign-dir>/
4. Verify zip contains ro-crate-metadata.json at the root, not nested
```

The `-X` flag strips macOS extended attributes that otherwise show up as `__MACOSX/` directories in the published archive.

---

## 4. MECA Bundle Path (Manuscript Co-publication)

If a methods note is published alongside the data:

1. Author the note in Quarto-compatible Markdown with frontmatter pointing to `dossier/SOURCES.bib` and an appropriate CSL (e.g. `apa.csl`).
2. Build MECA via:
   ```text
   quarto render <methods-note>.md --to meca
   ```
   This emits a `.zip` containing manifest XML, the rendered article, and an asset bundle. Quarto 1.5+ supports MECA natively as of 2025.
3. The MECA bundle is what *eLife*, *PLOS One*, *PeerJ*, *Digital Discovery*, and *Journal of Open Source Software* accept as a submission packet.
4. The MECA manifest must include a `<dataset>` element pointing to the Zenodo DOI of the data crate. Add this manually if Quarto's MECA exporter does not emit it; it is the load-bearing cross-reference between manuscript and data.
5. The MECA package and the RO-Crate are **separate deposits**: the MECA goes to the publisher, the RO-Crate goes to Zenodo. The publisher's article DOI and the Zenodo data DOI cross-reference each other.

**Recommended target if the user pursues co-publication:** *Digital Discovery* (RSC) for a software-DOE audience, or *Biotechnology Progress* for a bioprocess audience. *Digital Discovery* explicitly accepts MECA and has indexed similar SDL/DOE methodology papers. *Biotechnology Progress* requires more domain framing but lends more credibility to the bioprocess implications.

---

## 5. ELN Export Path

The campaign needs to be loadable into electronic-lab-notebook systems for downstream practitioners. Two formats, two paths.

### 5.1 `.eln` (eLabFTW-compatible RO-Crate ZIP)

The `.eln` file format is, by specification, an RO-Crate ZIP with a constrained profile. A passing RO-Crate is already 95% of the way to `.eln`.

Steps:
1. Add `conformsTo` entry: `https://w3id.org/ro/wfrun/process/0.5` is already in the recommended profile set; also add the ELN consortium spec URL once it gets a permanent w3id URL. Currently the ELN spec is at `https://github.com/TheELNConsortium/TheELNFileFormat` v1.4.
2. Rename the output ZIP from `.zip` to `.eln`. That is the only required surface change.
3. Test import into eLabFTW (community instance or the user's own deployment). The dossier should appear as a hierarchical experiment with phase-by-phase subentries.

The `.eln` export is **not a separate deposit**; it is a *secondary download asset* on the Zenodo record. Upload the `.eln` alongside the canonical `.zip` (or replace the `.zip` with `.eln` if the user wants a single-format deposit; both work).

### 5.2 Benchling JSON

Benchling does not consume `.eln`. It exposes a REST API and an internal JSON-LD-adjacent representation. The path:

1. Author a one-off adapter (~150 lines) that walks the RO-Crate graph and maps `CreateAction` → Benchling "Run," `Dataset` → "Notebook Entry," `SoftwareApplication` → "Workflow Reference."
2. POST via Benchling's `/api/v2/entries` and `/api/v2/runs` endpoints under the user's Benchling tenant API key.
3. The Benchling-side notebook entry should link back to the Zenodo DOI in its description field; Benchling does not preserve external identifiers natively.

**Effort:** Benchling export is a separate project (~1 day) and not on the critical path for publication. Defer unless a specific Benchling tenant requests it. The `.eln` path is sufficient for the open-data audience.

---

## 6. License Recommendation

Three layers in this codebase need licenses, and they should not all be the same.

| Layer | Recommendation | Rationale |
|---|---|---|
| **Campaign data and dossier artifacts** (the RO-Crate at deposit time) | **CC-BY 4.0** | Attribution-required, redistribution-allowed; matches Zenodo default; compatible with reuse in textbooks, derivative datasets, and aggregation into community collections; the dossier carries narrative content (NOTES.md, methods reasoning) that benefits from attribution |
| **Manifest schemas** (`schemas/campaign_manifest.schema.json` and siblings) | **CC0 1.0** | Schemas should be maximally reusable; attribution requirements actively impede adoption; precedent: JSON Schema, OpenAPI, FAIR4RS all release schemas as CC0 |
| **Engine code** (`src/biosymphony_ferm_doe/`) | **MIT** | OSI-approved, GPL-compatible, no copyleft burden, no patent grant complications; matches the licensing posture of BoFire (BSD-3), `ro-crate-py` (MIT), and pyDOE (MIT) |
| **Brand/diagram assets** (`assets/images/*` AI-generated) | **CC-BY-NC 4.0** *or* explicit prompt disclosure under CC-BY 4.0 | AI-generated imagery has unsettled copyright status; the conservative choice is non-commercial CC-BY-NC; the maximally-open choice is CC-BY 4.0 with a clearly labeled "Generated with [model name]" attribution string |

**Legal implications to flag explicitly:**

- **CC-BY 4.0 on the dossier** means anyone can republish, redistribute, even productize, provided attribution is preserved. The user retains no veto over downstream use, only an attribution claim.
- **CC0 on the schemas** is irrevocable. Once a schema is CC0-licensed and published, the user cannot later re-restrict it (the *act* of relicensing fails; the prior CC0 copy continues to circulate freely).
- **MIT on the engine code** does **not** grant a patent license. If any factor model, surrogate term, or cost-bridging method is patentable and the user wants to retain that option, MIT is insufficient. Use Apache 2.0 instead, which does grant a patent license but is otherwise functionally identical for most consumers.

**License status today:** the repository code has an MIT `LICENSE`. Any separate data-crate deposit still needs explicit data and schema license files if those assets ship outside the code repository.

---

## 7. Redaction Checklist

Run this list before any deposit. Some items are checkbox-style; others require a judgment call.

### 7.1 Hard removals (must be gone)

- [ ] All tracker issue IDs (internal cycle/project references) in *user-facing* metadata. They should not appear in the RO-Crate `description`, in any methods-note abstract, or in EVIDENCE/ filenames.
- [ ] Workstation absolute paths. Replace with `<repo_path>` and `<external_artifact_root>` placeholders. `docs/PUBLIC_RELEASE_PREP.md` and the public-release scanner enforce this before any switch.
- [ ] Personal identifiers beyond what the user actively wants to publish (full name + ORCID is fine; email address in artifact metadata is not).
- [ ] Cloud provider pod IDs, runtime-specific UUIDs, and any container-registry credentials that may have leaked into logs.
- [ ] Private-deployment defaults. The doc itself is excluded from the public release; this redaction checklist is the redundant check.
- [ ] API keys, even revoked ones. `gitleaks detect --source . --no-banner --redact` (wired into `make secret-scan` and `make public-ready`) must pass clean.
- [ ] Internal team/project names from any tracker screenshots, dashboards, or ticket exports if they appear in EVIDENCE/.

### 7.2 Soft removals (judgment call)

- [ ] Intermediate WIP commits. The git history of the dossier path can include many commits during a campaign sprint, some of which document caught bugs.
  - **Option A:** publish the dossier as a `git archive` of `HEAD` only; no history, just the tree. Zenodo accepts ZIPs of any provenance.
  - **Option B:** publish a curated history (squash to a handful of commits: scope brief, each phase, handoff). Informative but requires a one-time rebase.
  - **Option C:** publish the full history. Most transparent but exposes the day-by-day debugging trail. Acceptable if the campaign is being held up as a methodology exemplar.
  - **Recommendation:** Option A for v1.0.0 unless the day-by-day record is itself part of the scientific contribution.
- [ ] Hero / cover imagery generated by AI. Either remove or attach explicit "AI-generated, prompt-disclosed" provenance under CC-BY 4.0.
- [ ] Names of human collaborators who have not opted in to public attribution.

### 7.3 Verification commands

Pre-deposit, run:

```text
1. rg -n "<repo_path>|<external_artifact_root>" <campaign-dir>/
2. make public-ready      # release checks + gitleaks history/tree
3. make release-check     # demo validators, if you need the shorter structural gate separately
4. ro-crate-py validate <campaign-dir>/
5. checkmycrate <campaign-dir>/
```

All five must report zero findings or all-PASS before the bundle ships.

---

## 8. Deposit Checklist

Concrete pre-deposit checklist. Each item is a discrete go/no-go gate.

### 8.1 Files to include in the ZIP

- [ ] `ro-crate-metadata.json` (root)
- [ ] `README.md` (campaign-level)
- [ ] `campaign_manifest.json` and any phase-specific manifests
- [ ] Scope brief (if separate from the README)
- [ ] `dossier/CITATIONS.json` (with the citation count current at deposit)
- [ ] `dossier/NOTES.md`
- [ ] `dossier/SOURCES.bib`
- [ ] `dossier/EVIDENCE/*.{md,json,html}`, all evidence files
- [ ] Any hero / illustrative imagery *only if* license-cleared
- [ ] `dossier/dossier.html` if a single-page rendering is included
- [ ] Any errata or correction documents
- [ ] `handoff-packet/*` if the campaign produced one (CPP register, QTPP, design-space PAR/NOR, risk register, scale-down qualification)
- [ ] Campaign portal `index.html` *optional*; useful for offline reviewers, but increases footprint
- [ ] `ro-crate-validation-report.json`, last validator output, for reviewer transparency

### 8.2 Files to exclude

- [ ] `inputs/*.csv` *only if* any input file contains private data; synthetic public inputs should be included
- [ ] `expected/*`, comparison-baseline files that are derivative of inputs; include only if narratively load-bearing
- [ ] Any `__pycache__/`, `.DS_Store`, or `.ipynb_checkpoints/`
- [ ] Local logs, debugging traces, not scientific output
- [ ] AI-generated brand imagery without prompt provenance
- [ ] Operator-only deployment notes (excluded from public release by `docs/PUBLIC_RELEASE_PREP.md` data rules)

### 8.3 Required external metadata (DataCite 4.5 fields)

- [ ] Title (max 250 chars, mirror any companion manuscript title)
- [ ] Creator(s) with ORCID
- [ ] Publisher = "Zenodo" (the platform sets this; user supplies organisational affiliation separately)
- [ ] Publication date (use `datePublished` from the crate root)
- [ ] Resource type = "Dataset" with subtype "Computational Notebook"
- [ ] Identifier = the Zenodo concept DOI (auto-issued on deposit)
- [ ] Subject keywords (mirror crate `keywords[]`)
- [ ] License URL (CC-BY 4.0 SPDX iri)
- [ ] Description (mirror crate `description`)
- [ ] Related identifiers, link any methods-note DOI if it exists; link the GitHub repo URL if/when the repo goes public
- [ ] Version (e.g. `1.0.0`)
- [ ] Funding (leave blank or declare self-funded)

### 8.4 Pre-flight gates

In order:

1. [ ] `make release-check` passes
2. [ ] `make secret-scan` passes
3. [ ] RO-Crate validator passes (no errors, warnings reviewed)
4. [ ] CheckMyCrate (or roc-tools) passes both `ro-crate/1.2` and `wfrun/process/0.5` profiles
5. [ ] Redaction checklist (§7) all-clear
6. [ ] License files (`LICENSE-data.txt` CC-BY 4.0, `LICENSE-schemas.txt` CC0, `LICENSE-code.txt` MIT) added to the repo and to the ZIP
7. [ ] Concept DOI reserved on Zenodo Sandbox; metadata renders correctly
8. [ ] User explicitly authorizes the production deposit
9. [ ] Deposit uploaded to production Zenodo
10. [ ] DOI propagation confirmed (check `https://doi.org/<concept_doi>` resolves) before publicising

---

## 9. Citation Strategy

### 9.1 How external researchers should cite

**Preferred citation block template** (to be embedded in the published `README.md` and crate root `description`):

```text
<campaign authors>. (<year>). <campaign title>:
<one-line subtitle> (Version 1.0.0) [Data set]. Zenodo.
https://doi.org/10.5281/zenodo.XXXXXXX
```

For BibTeX:

```text
@dataset{<bibkey>,
  author       = {<authors>},
  title        = {<campaign title>:
                  <one-line subtitle>},
  year         = <year>,
  publisher    = {Zenodo},
  version      = {1.0.0},
  doi          = {10.5281/zenodo.XXXXXXX},
  url          = {https://doi.org/10.5281/zenodo.XXXXXXX}
}
```

External researchers should cite the **concept DOI** when discussing the campaign in general, and the **version DOI** when referencing a specific result that could change in a later version.

### 9.2 How to cite a campaign in future internal work

For internal documents (subsequent campaigns, manifest changes, methods-note revisions), reference the campaign by:

1. The campaign identifier in the manifest (this is internal, stable, and predates any DOI).
2. The Zenodo concept DOI *once issued*.
3. A short-form tag for prose references.

Do not internally cite a companion manuscript DOI for data claims; cite the data DOI directly so corrections to the data don't appear to require manuscript-level errata.

### 9.3 Co-citation alongside reference precedents

When the campaign is described in any future writeup, co-cite with the methodology peer set:

- Strieth-Kalthoff et al. (2024), *Science*, `10.5281/zenodo.8357375`, closed-loop SDL precedent
- Boyle et al. (2024), ProcessOptimizer, `10.5281/zenodo.14179617`, BO toolkit precedent
- SDL benchmarking suite (2026), *Digital Discovery*, `10.5281/zenodo.17287854`, community-standard benchmark
- Lapierre (2025), *JCTB*, batch-BO growth media precedent in microbial fermentation

These anchor the campaign in an existing methodological lineage, which is essential for reviewer plausibility and for downstream re-use.

---

## 10. Risks to Flag Before Publication

These are the risks the user should consciously accept (or mitigate) before authorizing deposit.

1. **CC-BY 4.0 attribution-only license permits commercial reuse without notice.** A vendor could repackage the campaign as part of a paid bioprocess-DOE product. Acceptable under open-data norms; flag to the user. NC variant available if uncomfortable.
2. **DataCite metadata is permanent and indexed in Google Scholar within ~14 days.** Errors in the deposit metadata (misspelled creator name, wrong date, wrong license) are correctable but visible. Use Sandbox to rehearse.
3. **The MECA-bundle path requires a target journal commit.** Building MECA without a target adds work that isn't load-bearing for the data deposit. Decouple the two timelines.
4. **AI-generated brand imagery has unsettled copyright in some jurisdictions** (notably the U.S., where the Copyright Office has held that purely AI-generated work is uncopyrightable). Either remove imagery before deposit or disclose AI origin and acknowledge the imagery's public-domain status in those jurisdictions.
5. **Once published, withdrawing the deposit produces a tombstone, not a deletion.** Anyone who downloaded the v1 ZIP between deposit and withdrawal retains a perpetual copy. There is no undo.
6. **A simulator's coefficient set becomes part of the public record on deposit.** If a campaign's headline ranking turns out to be a simulator artifact (caught either before or after deposit), the errata must be surfaced wherever the headline is surfaced (crate `description`, README, methods-note abstract, Zenodo deposit description). The errata must not be a separate file the reader has to discover.

---

## Appendix A: What This Repo Provides

The repo today provides:

- A retrofit script (`skills/biosymphony-ferm-doe/scripts/rocrate_retrofit.py`) that builds a starting RO-Crate from a campaign manifest
- A public-release prep document (`docs/PUBLIC_RELEASE_PREP.md`) with public data rules
- A public-readiness checklist in `docs/RELEASE_READINESS_CHECKLIST.md`
- A `make release-check` target with demo validators and public-surface scans
- A `make public-ready` target that adds the required gitleaks history and working-tree secret scan

Things the repo does **not** yet have:

- `LICENSE-data.txt`, `LICENSE-schemas.txt`, or separate per-deposit license files
- A Zenodo deposit script or REST adapter
- A `.eln` packing helper (trivial: rename the validated ZIP)
- A Benchling export script

---

## Appendix B: Authorization Marker

This document is **strategy only**. No item in §§ 2, 3, 7, 8 or 9 should be executed until the user authorizes by:

1. Writing an explicit "GO" in a new commit message or in-session message,
2. Specifying the campaign(s) authorized for publication,
3. Confirming the license stack (default: CC-BY 4.0 data + CC0 schemas + MIT code, per §6),
4. Confirming the target venue (default: Zenodo, per §1.2).

Until all four are present, this document describes a path and nothing more.
