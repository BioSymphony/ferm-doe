# Cross-Campaign Lessons

**Scope:** Public-safe methodology lessons for BioSymphony Ferm DoE campaigns.
These are distilled into reusable patterns, not copied campaign records. Use
them as review prompts when adapting the public examples to a private workspace.

---

## 1. Keep The Manifest Authoritative

The campaign manifest is the shared state between human, agent, CLI, and any
external orchestrator. Every handoff should preserve:

- declared profiles
- response contracts
- factor bounds and constraints
- arm scope
- scale context
- decision rules
- evidence provenance
- claim level

If an adapter, issue pack, or report needs a different shape, translate at the
boundary and keep a pointer back to the manifest field that produced it.

## 2. Do Not Trust Structural Metadata Until It Is Projected

Multi-arm campaigns, categorical factors, equipment limits, and blocking
constraints are easy to describe and easy to mishandle. Treat them as explicit
projection steps:

- project design rows per arm before execution review
- audit categorical aliasing after projection
- validate every generated row against the declared constraint set
- keep per-arm CSVs authoritative when horizontal review tables are generated

The validator can catch many errors, but it cannot infer a campaign team's
operational intent when the manifest is ambiguous.

## 3. Label Simulator Fidelity Before Ranking

A simulator is a planning prior, not observed evidence. Before a simulator can
rank candidates, the manifest should declare one of:

- `linear_placeholder`
- `dose_response_v2`
- `surrogate_on_observed`

`linear_placeholder` surfaces may rank recipe families, but they should not
make strong claims about fine-grained factor-level optima. When a load-bearing
factor lacks a dose-response term, run the literature pressure-test template
before sealing a planning packet.

## 4. Make Cost Claims Five-Layer

Single cost-per-mg numbers are misleading unless the reader can see what is
included. Every cost claim should show:

- simulator media-only number
- bulk material number with inducer or other held-constant process factors
- fully loaded bench-scale cost
- process-scale benchmark range
- explicit caveat about whether the number is a ranking metric or COGS

The reusable template is [`templates/cost_stack.template.md`](../templates/cost_stack.template.md).

## 5. Prefer Feasible-By-Construction Routes

When a DoE or BO backend cannot enforce a declared constraint directly, the
report should say so and either:

- route to a backend that can enforce it
- emit a documented post-hoc feasibility filter
- refuse to generate candidates

Silent fallback is worse than a blocked plan. BoFire, ENTMOOT, OMLT, BoTorch,
and stdlib generators all have different constraint surfaces; the adapter
report should name the route reason and the non-claim.

## 6. Evidence Should Accumulate In One Dossier

Do not scatter literature notes across isolated reports. A campaign should
converge on one dossier with:

- `CITATIONS.json`
- `SOURCES.bib`
- `NOTES.md`
- per-corpus `EVIDENCE.csv` files when multiple evidence lanes are used

That structure makes contradictions, stale assumptions, and missing assay
evidence visible during review.

## 7. Gate follow-up With Predeclared Rules

follow-up decisions should be boring and deterministic. Before results arrive,
write down:

- response thresholds
- assay noise policy
- stop rules
- minimum evidence for promotion
- how ties and missing rows are handled

If the rules block follow-up, preserve that as a planning outcome. Do not invent a
stronger claim to make the campaign look complete.

## 8. Public Release Rules

Public examples must stay synthetic or public-source-derived. Do not publish:

- private strain details
- customer batch records
- unpublished sequences
- confidential media formulations
- provider IDs or runtime logs
- private tracker IDs
- raw private campaign artifacts

When a private campaign produces a reusable lesson, promote the lesson as a
generic rule, fixture, or validator. Do not backport the raw campaign record.
