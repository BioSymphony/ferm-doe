# Scientific Swarm Issue Pack

This public-safe pack sketches optional pre-DOE review lanes. It is a planning
contract, not an orchestration implementation.

## Work Items

1. Swarm contract and artifact schema.
2. Evidence prior and source-trust review.
3. Assay and product-class skeptic review.
4. Process, scale-transfer, cost, runability, and sampling review.
5. Factor-universe integration.
6. Assumption attack and contradiction reconciliation.
7. Observability and control strategy.
8. Dossier handoff and follow-up memory notes.

## Expected Artifacts

- `evidence_swarm_plan.json`
- `factor_universe.json`
- `factor_universe.md`
- `assumption_attack_report.json`
- `observability_plan.json`
- `control_run_strategy.json`
- `swarm_adjudication_brief.md`

## Validation Commands

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli audit .
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli check-dossier examples/demo-xylanase-public
```

## Public-Safety Rules

- Use pack-local ids and relative paths.
- Keep shared synthesis files single-writer during merge.
- Do not include private data, provider launch fields, private tracker ids, or execution approvals.
- Treat swarm output as planning evidence and caveat memory, not optimization proof.
