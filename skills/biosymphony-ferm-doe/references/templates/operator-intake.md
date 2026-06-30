# Operator Intake

Use this template before campaign compilation when the starting request is messy or incomplete. The goal is to capture enough context to compile a draft campaign, not to block until every detail is known.

## Intake Mode

- Mode: `interview | skip_and_assume | file_first`
- Operator preference:
- Compute preference: `local-stdlib | local-extras | approved-remote-dry-run | approved-remote-serverless | external-container-adapter`
- Remote launch allowed now: `false`

## Known Inputs Read First

- Manifest:
- Run ledger or shake-flask data:
- Recipe/media/feed notes:
- Reagent inventory:
- Equipment capacity:
- Assay/protocol notes:
- Evidence tables or literature notes:

## Known Campaign Facts

- Organism or host:
- Product or response class:
- Current format and scale:
- Target format and scale:
- Objective:
- Primary response:
- Secondary responses:
- Max run duration:
- Run budget:
- Cost limit:

## High-Leverage Questions

Ask no more than three at a time.

1. Question:
   - Why it matters:
   - Default if skipped:
2. Question:
   - Why it matters:
   - Default if skipped:
3. Question:
   - Why it matters:
   - Default if skipped:

## Operator Answers

- Answer 1:
- Answer 2:
- Answer 3:

## Missing Operator Items

| item | severity | default_or_assumption | impact |
| --- | --- | --- | --- |
|  | blocker/warning/assumed_for_wave0 |  |  |

## Research Or Evidence Tasks

| task | lane | expected_artifact | priority |
| --- | --- | --- | --- |
|  | literature_prior/prior_data/assay/process/cost | evidence_table.csv | high/medium/low |

## Draft Manifest Handoff

- Draft manifest path:
- Evidence table path:
- Assumption summary path:
- Ready to compile state: `yes | no`
