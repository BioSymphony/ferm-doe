# Evidence Executor Agent Brief

Use this brief when a research worker is asked to produce evidence rows for BioSymphony Ferm DoE.

## Boundary

The worker may perform bounded public-source or operator-approved research. The core DOE engine does not browse, fetch private data, or decide from prose notes. Its input is a local `evidence_table.csv` with provenance and quality fields.

## Sources

Allowed source classes:

- PubMed or publisher metadata pages
- bioRxiv or other preprint landing pages
- Google Scholar or manual citation lookup summaries
- vendor protocols, reagent methods, assay protocols, and equipment manuals
- sanitized prior-run summaries or local ledgers explicitly provided by the operator

Do not store API keys, full copyrighted papers, private strain details, customer batch records, unpublished sequences, or confidential media recipes in the repo or in any tracker.

## Output Rows

Start from `templates/evidence-table.template.csv`. Keep the header order unchanged.

Rules:

- One decision-relevant claim per row.
- Use a stable `source_ref`: DOI, PMID, URL, vendor document id, or sanitized local ledger reference.
- Put the smallest useful claim in `claim`; do not paste source passages.
- Map `factor_or_response` to a campaign factor or response id when possible.
- Use `suggested_role` only when the claim affects factor selection: `doe_factor`, `fixed_control`, `block`, `monitor_only`, `wave2_candidate`, or `exclude`.
- Use `suggested_min` and `suggested_max` only when the source supports a range.
- Use `contradiction_group` to link conflicting claims across rows.
- Use `review_status`, `confidence`, `source_trust`, `license`, and `extraction_method` so weak evidence is downgraded rather than treated as truth.

## Required Artifacts

- `evidence_table.csv`
- `evidence_source_ledger.csv`
- `evidence_search_log.md`
- `evidence_executor_report.md`

## Validation

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py \
  --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json \
  --out /tmp/biosymphony-evidence-check \
  --evidence-table evidence_table.csv
```

Rows with missing claims, unmapped factors/responses, nonnumeric ranges, rejected review status, or unknown factor roles will be downgraded or excluded by evidence ingestion.
