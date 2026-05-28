# Pareto Literature-Validation Check

**Template version:** 1.0
**Purpose:** Force every campaign to validate its top-K Pareto winners against published literature BEFORE sealing. A winner that falls outside the literature corridor must be surfaced as either a simulator gap, a novel finding, or a structural error, and not silently shipped in the handoff packet.

## Why this template exists

A Pareto winner can contradict decades of published literature when the
simulator's structural form has a gap on the load-bearing factor (e.g., a
synergy term gated on a co-factor that is zero at the winning recipe, with no
direct dose-response term to push back). If that contradiction is caught only
by a post-seal literature scan, the ordering is lucky, not designed. This
template makes the catch a mandatory sealing gate, not a courtesy review. See
[`docs/CROSS_CAMPAIGN_LESSONS.md`](../docs/CROSS_CAMPAIGN_LESSONS.md) §5.1 for
rationale.

## When to fill

Post-design-tournament, pre-seal. This must be the last gate before any
campaign closeout commit. The handoff packet's sealing commit blocks unless a
completed copy of this file is present and Section 5 verdict is `SEAL` or
`SEAL_WITH_ERRATA` (not `DO_NOT_SEAL`).

## Conventions

- Fields marked `REQUIRED` fail the seal if blank.
- Fields marked `OPTIONAL` may be omitted but their absence should be deliberate.
- Placeholders use `{{double-braces}}`; replace inline.
- Tables expand with as many rows as the campaign has factors or winners.
- This is a DOE planning artifact, not a batch record. Do not add operator
  initials, lot tracking, IPC alert/action runtime, deviation logs, or
  21 CFR 211.188 scaffolding.

---

## Section 1: Campaign identification

| Field | Value |
|---|---|
| Campaign ID (REQUIRED) | {{campaign_id}} |
| Sealing date target (REQUIRED) | {{YYYY-MM-DD}} |
| Seal scope (REQUIRED) | {{which artifacts and handoffs depend on this check passing, e.g., `handoff-packet/design_table.csv`, `lab_team_brief.md`, `dossier.html`}} |
| K (number of winners checked, REQUIRED) | {{K}} |
| K justification (REQUIRED if K < 3) | {{free text: why fewer than 3 winners were checked. Default expectation is K >= 3 so that cross-winner concordance in Section 4 is computable.}} |
| Pareto source artifact (REQUIRED) | {{path to the file from which the K winners were drawn, e.g., `bofire_phase2_report.json` or `handoff-packet/design_table.csv`}} |
| Objective(s) being optimized (REQUIRED) | {{e.g., `min cost_per_mg`, `max titer_mg_per_l`, or both as a Pareto front}} |

---

## Section 2: Simulator fidelity self-declaration

Fill this section **before** examining the winners. If the simulator's
fidelity level is `linear_placeholder`, the winners are not trustworthy on
factor *levels* without literature validation; they may only be ranked on
recipe *families*. See [`docs/CROSS_CAMPAIGN_LESSONS.md`](../docs/CROSS_CAMPAIGN_LESSONS.md)
§5.2 and [`docs/SIMULATOR_V2_SPEC.md`](../docs/SIMULATOR_V2_SPEC.md) §1.

| Field | Value |
|---|---|
| `simulator.fidelity_level` (REQUIRED) | {{one of: `linear_placeholder` \| `dose_response_v2` \| `surrogate_on_observed`}} |
| Manifest declaration path (REQUIRED) | {{path to the campaign manifest field where this is recorded}} |
| Simulator implementation path (REQUIRED) | {{path to the simulator code or coefficient file, e.g., `bofire_phase2_report.json :: simulator_coefficients` or `src/biosymphony_ferm_doe/simulators/v2m1.py`}} |

### 2.1 Per-factor dose-response coverage

For each factor in the design space, declare whether the simulator carries a
published-form dose-response term. A factor with `N` here is a likely artifact
source for winners that pile onto that factor's allowed range.

| Factor name (REQUIRED) | Dose-response term present? (Y/N, REQUIRED) | Code path or coefficient block citation (REQUIRED) | Reference for term shape (REQUIRED if Y, OPTIONAL if N) |
|---|---|---|---|
| {{factor_1}} | {{Y/N}} | {{file:line or json path}} | {{PMID/DOI/none}} |
| {{factor_2}} | {{Y/N}} | {{file:line or json path}} | {{PMID/DOI/none}} |
| {{factor_3}} | {{Y/N}} | {{file:line or json path}} | {{PMID/DOI/none}} |

### 2.2 Gate-before-the-gate verdict

| Field | Value |
|---|---|
| Number of factors with `Y` (REQUIRED) | {{n}} |
| Number of factors with `N` (REQUIRED) | {{n}} |
| Proceed to Section 3? (REQUIRED) | {{YES \| YES_WITH_INCREASED_SCRUTINY \| HALT_AND_REPLACE_SIMULATOR}} |
| If `HALT_AND_REPLACE_SIMULATOR`: blocker rationale (REQUIRED) | {{free text: which factors with N are load-bearing on the Pareto winners and why the simulator must be replaced before sealing}} |

---

## Section 3: Per-winner literature check

**Repeat this section for each of the K winners. Each winner gets its own
sub-block 3.A, 3.B, 3.C, ... through 3.K.**

### 3.{{i}}. Winner ID: {{winner_id}}

| Field | Value |
|---|---|
| Rank in Pareto (REQUIRED) | {{rank, e.g., 1 of 16}} |
| Objective value(s) (REQUIRED) | {{e.g., `cost_per_mg = $0.000503`, `titer = 54 mg/L`}} |
| Source CSV row (REQUIRED) | {{file:row reference}} |

#### Factor values

| Factor name | Value | Units |
|---|---|---|
| {{factor_1}} | {{value}} | {{units}} |
| {{factor_2}} | {{value}} | {{units}} |
| {{factor_3}} | {{value}} | {{units}} |

#### Per-factor literature check

Minimum 2 references per factor, each with PMID or DOI. If 2 references
cannot be found, that itself is a finding; record it as
`insufficient_literature_to_validate` and treat the factor as failing the
check.

| Factor | Winner value | Published optimum (low) | Published optimum (high) | Units | Reference 1 (PMID/DOI) | Reference 2 (PMID/DOI) | In range? (Y/N) | If N: distance from range edge | If N: which simulator term explains discrepancy |
|---|---|---|---|---|---|---|---|---|---|
| {{factor_1}} | {{val}} | {{low}} | {{high}} | {{units}} | {{ref1}} | {{ref2}} | {{Y/N}} | {{distance + units}} | {{code-path citation or `none, novel finding suspected`}} |
| {{factor_2}} | {{val}} | {{low}} | {{high}} | {{units}} | {{ref1}} | {{ref2}} | {{Y/N}} | {{distance + units}} | {{code-path citation or `none, novel finding suspected`}} |
| {{factor_3}} | {{val}} | {{low}} | {{high}} | {{units}} | {{ref1}} | {{ref2}} | {{Y/N}} | {{distance + units}} | {{code-path citation or `none, novel finding suspected`}} |

#### Per-winner verdict

| Field | Value |
|---|---|
| Verdict (REQUIRED) | {{PROCEED \| CAVEAT_REQUIRED \| SUPERSEDED}} |
| Verdict rationale (REQUIRED, min 2 sentences) | {{free text: explain which factors drove the verdict and what the implication is for the handoff packet}} |
| Errata or caveat path (REQUIRED if `CAVEAT_REQUIRED` or `SUPERSEDED`) | {{e.g., `examples/<campaign>/ERRATA-<winner_id>.md`}} |
| Replacement winner ID (REQUIRED if `SUPERSEDED`) | {{ID of the candidate that replaces this one in the handoff packet}} |

---

## Section 4: Cross-winner concordance

| Field | Value |
|---|---|
| Do the K winners cluster on factor values? (REQUIRED) | {{CLUSTER \| DIVERGE \| MIXED}} |
| Clustering evidence (REQUIRED) | {{free text, e.g., "all 5 winners sit at lactose <= 5 g/L and IPTG <= 0.5 mM; ammonium sulfate spreads 0.1 to 2 g/L", or "winners split into two regimes: lactose-dominant vs glycerol-dominant"}} |
| Model-quality concern? (REQUIRED if `DIVERGE` or `MIXED`) | {{YES \| NO}} |
| If `YES`: nature of concern (REQUIRED) | {{e.g., "Pareto front is flat; the BO acquisition function cannot discriminate between regimes, suggesting the simulator's objective surface is under-determined in this region"}} |

Concordance is a model-quality signal that complements per-winner lit-check.
Tight clustering across K winners corroborates a robust optimum; divergence
suggests either Pareto-front flatness (acceptable, document) or a model
artifact (escalate to simulator review).

---

## Section 5: Seal verdict

| Field | Value |
|---|---|
| Verdict (REQUIRED) | {{SEAL \| SEAL_WITH_ERRATA \| DO_NOT_SEAL}} |
| Justification (REQUIRED, min 3 sentences) | {{free text: explain which per-winner verdicts and concordance findings drove the seal-level verdict. Reference the specific winners and factors load-bearing on the decision.}} |

Verdict rules:

- **`SEAL`**: all K winners returned `PROCEED` in Section 3, no errata
  required, Section 4 either `CLUSTER` or `DIVERGE` with no model-quality
  concern.
- **`SEAL_WITH_ERRATA`**: at least one winner returned `CAVEAT_REQUIRED` or
  `SUPERSEDED`. Errata file(s) must be authored and linked from Section 3
  AND from the handoff packet's `lab_team_brief.md`.
- **`DO_NOT_SEAL`**: at least one winner is structurally indefensible (e.g.,
  contradicts load-bearing biology AND has no replacement candidate in the
  Pareto set), OR Section 2's gate-before-the-gate returned
  `HALT_AND_REPLACE_SIMULATOR`. Campaign requires redesign before sealing.

### 5.1 Open items propagated to other artifacts (REQUIRED if `SEAL_WITH_ERRATA`)

| Artifact | What gets updated | Owner |
|---|---|---|
| {{e.g., `handoff-packet/design_table.csv`}} | {{e.g., "row for SUPERSEDED winner annotated with `simulator_artifact = TRUE`"}} | {{role or name}} |
| {{e.g., `handoff-packet/lab_team_brief.md`}} | {{e.g., "headline candidate replaced with Candidate A/B; caveat linked in §1"}} | {{role or name}} |
| {{e.g., `dossier/dossier.html`}} | {{e.g., "visible caveat banner added; superseded row struck through"}} | {{role or name}} |

---

## Section 6: Signoff

| Field | Value |
|---|---|
| Operator name (REQUIRED) | {{name or role, the person who filled this template}} |
| Operator date (REQUIRED) | {{YYYY-MM-DD}} |
| Reviewer name (REQUIRED if verdict is `SEAL` or `SEAL_WITH_ERRATA`) | {{name or role, independent of the operator}} |
| Reviewer date (REQUIRED if verdict is `SEAL` or `SEAL_WITH_ERRATA`) | {{YYYY-MM-DD}} |
| Commit SHA where this completed file is committed (REQUIRED) | {{git commit SHA; fill after the commit lands}} |

For `DO_NOT_SEAL` verdicts, reviewer signoff is OPTIONAL; the operator's
decision to halt the seal stands on its own, and the redesign loop will
produce a new copy of this file.
