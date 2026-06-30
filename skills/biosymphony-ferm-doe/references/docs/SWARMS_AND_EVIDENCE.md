# Swarms And Evidence Contracts

Scientific swarms are optional public-safe planning lanes. They break evidence
collection, assumption review, factor-universe construction, observability, and
handoff writing into bounded work items while keeping the Python package local
and deterministic.

## Evidence Table Contract

Evidence workers write rows that match:

- `templates/evidence-table.template.csv`
- `templates/evidence-executor-agent-brief.md`

The compact public header is:

```text
evidence_id,source_type,source_ref,source_url,claim,confidence,review_status,decision_impact,reuse_notes,transformation_notes
```

Each row should contain one paraphrased decision-relevant claim, a stable source
reference, source type, confidence, review status, and transformation notes.
Public or reference evidence must not be represented as target-specific
experimental proof.

## Issue Packs

Public issue packs live under `packs/issue-packs/`. They use pack-local ids,
relative paths, and validation commands that run with stdlib Python. They do not
carry private tracker ids, provider launch fields, or private artifact paths.

Current public packs:

- `adaptive-wave2-assay-power-v0`
- `campaign-arms-v1`
- `doe-parity-v0`
- `doe-parity-v1`
- `evidence-executor-v0`
- `fermentation-readiness-v0`
- `scientific-swarm-v0`

The evidence executor pack is for source scoping, public literature or protocol
extraction, and evidence-table handoff. The scientific swarm pack is for using
those evidence rows to create planning artifacts such as factor universe,
assumption attack, observability, control strategy, and adjudication notes. The
DoE parity packs cover reference-software import / export and the high-ROI
parity upgrades. The fermentation readiness pack covers the readiness scoring
work that gates campaign launch. The campaign-arms pack covers first-class
multi-arm support for coupled campaigns.

## Activation Pattern

- Keep contract/setup work serial.
- Run independent evidence lanes in parallel only when touched areas are disjoint.
- Merge evidence rows serially before they influence factor-space or tournament decisions.
- Keep final dossier and claim-boundary review serial.

## Non-Claims

Evidence and swarm artifacts are planning inputs. They do not validate physical
execution, process performance, assay power, scale transfer, production
readiness, or regulatory compliance.
