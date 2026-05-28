# Adaptive Backend Evaluation Smoke Surface

This directory is the handoff point for agents comparing free/open adaptive
design backends for BioSymphony Ferm DoE.

Authoritative files:

- `docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md`
- `docs/adaptive-backend-evaluation.json`
- `docs/tool-registry.json`

Scenario fixture directories:

- `static_constrained_media/` - BoFire default constrained static DoE/BO.
- `low_data_hybrid_transfer/` - BayBE comparison for low-data hybrid transfer.
- `cost_aware_multiobjective/` - direct BoTorch/Ax cost-aware pilot.
- `adaptive_orchestration/` - Ax trial-lifecycle pilot.
- `cardinality_heavy_media/` - ENTMOOT exact NChooseK fallback.
- `scale_bridge_planning/` - backend support with BioSymphony-owned scale bridge.

Each scenario has `campaign_manifest.json`, `inputs/prior_runs.csv`, and
`smoke_plan.json`. Generated outputs belong under `.runtime/adaptive-backend-eval/`.

Minimum offline smoke:

```bash
python3 skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py \
  docs/adaptive-backend-evaluation.json

python3 skills/biosymphony-ferm-doe/scripts/tool_registry_check.py \
  docs/tool-registry.json

nox -s adaptive_backend_surface
```

Optional live import smoke:

```bash
nox -s adaptive_backend_live_imports
```

Manual equivalent, using Python 3.11-3.13 because BayBE 0.14.3 declares
`python <3.14`:

```bash
python3.11 -m venv .runtime/backend-eval-venv
.runtime/backend-eval-venv/bin/python -m pip install -e ".[adaptive,backend-eval,entmoot,dev]"
.runtime/backend-eval-venv/bin/python skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py \
  docs/adaptive-backend-evaluation.json \
  --live-imports
```

Live import success does not promote a backend. A promoted adapter needs a
fixture campaign, route report, fallback report, candidate-table validation,
and a clear statement that BioSymphony keeps ownership of scale bridge, assay
readiness, evidence dossier, cost stack, and lab handoff packet.
