# Adaptive follow-up + Assay Power Issue Pack

This public issue pack breaks adaptive follow-up planning into bounded work items. It is safe to copy into GitHub Issues, Linear, or another tracker after replacing repository-specific labels.

The pack keeps the lane versatile:

- users can confirm, narrow, expand, pause, stop, or plan a scale/downscale branch
- assay-power checks are response-level and do not invent wet-assay requirements for derived cost, duration, or calculated responses
- negative memory is arm-scoped by default
- planned follow-up artifacts never claim validated optimization or validated scale transfer

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli audit .
```

## Work Items

1. Result ingestion and trust/QC gating.
2. Response-level assay-power policy and CLI utility.
3. Adaptive recommendation and augment-row artifacts.
4. Self-learning ledger and hiccup review runbook.
5. Public docs, schema, and non-claim review.

## Public-Safety Rules

- Do not include private process records, unpublished strain data, confidential media formulations, or credentials.
- Use synthetic or public-source examples.
- Keep paths relative inside issue descriptions and artifacts.
- Treat any scale/downscale output as planning candidates only until bridge evidence is reviewed.
