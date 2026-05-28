# Evidence Executor Issue Pack

This public-safe pack defines bounded work for collecting evidence rows that can
feed Ferm DoE planning. It is intentionally tracker-neutral and local-only.

## Work Items

1. Evidence contract and source scope.
2. Public literature evidence extraction.
3. Public protocol, vendor method, or sanitized-reference extraction.
4. Evidence table normalization and handoff.

## Expected Artifacts

- `evidence_executor_plan.md`
- `evidence_table.csv`
- `evidence_source_ledger.csv`
- `evidence_search_log.md`
- `evidence_executor_report.md`

## Validation Commands

```bash
test -f templates/evidence-table.template.csv
test -f templates/evidence-executor-agent-brief.md
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli audit .
```

## Public-Safety Rules

- Use public, synthetic, or sanitized sources only.
- Do not copy article text, credentials, private process records, unpublished strain data, confidential media formulations, or private artifacts.
- Keep paths relative.
- Treat evidence rows as planning support, not validation evidence.
