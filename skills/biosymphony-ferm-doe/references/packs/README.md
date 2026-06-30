# Sidecar Packs

Packs are swappable modules for campaign construction. They let the same Symphony + Linear wave graph run against different upstream bioprocess goals, factor spaces, input sources, and remote execution modes.

Issue packs:

- `fermentation-readiness-v0` - default readiness and lab-packet graph.
- `doe-parity-v0` - focused worker campaign for raising reference DOE mechanics while preserving BioSymphony fermentation guardrails.
- `scientific-swarm-v0` - optional evidence swarm, assumption attack, factor universe, observability, and control-run strategy graph.

Pack classes:

- `goal-packs/`: objective, response policy, stop policy, and readiness gates
- `input-packs/`: source mode, data safety policy, and required artifacts
- `issue-packs/`: reusable Linear issue DAGs
- compute profiles: local stdlib by default, with approved remote adapters only when explicit
- provider handoffs: workers validate and prepare; the trusted orchestrator performs paid create/verify/cleanup when remote mutation is required
- evidence executor: optional research-worker pack for turning PubMed, bioRxiv, Scholar/manual-citation, vendor, protocol, and sanitized prior-run evidence into local `evidence_table.csv` rows

Campaign instances select packs explicitly. Workers should not infer pack compatibility from names alone.
