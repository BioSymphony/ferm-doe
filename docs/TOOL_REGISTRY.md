# Tool Registry

`docs/tool-registry.json` is the repo's curated tool memory. It is not an
auto-updating package index. It records which external tools are useful for
BioSymphony Ferm DoE, how they should be routed, what claim level they support,
what license boundary applies, and how the engine should fail closed when a
tool is absent.

The `last_checked` dates and `current_signal` text on each entry are baselines
captured on a specific day. Before relying on a finding tied to one of these
tools, re-confirm the installed version matches the `current_signal` text,
especially for upstream branches under active development like `bofire main`
(see [`BACKEND_EVAL_FINDINGS.md`](BACKEND_EVAL_FINDINGS.md) for the as-of
dates that anchor each verified backend).

Use it before:

- adding or changing optional dependencies in `pyproject.toml`
- deciding whether a campaign should use BoFire, pydoe/pyDOE3, SALib, or a sidecar
- comparing BoFire, BayBE, Ax/BoTorch, ENTMOOT, OMLT, or TabPFN on the adaptive-backend fixture surface
- preparing an optional remote-compute run that installs external packages
- promoting a watchlist repo into an adapter
- making a current-version, active-maintenance, archived, or deprecated claim

Validation:

```bash
python3 skills/biosymphony-ferm-doe/scripts/tool_registry_check.py docs/tool-registry.json
python3 skills/biosymphony-ferm-doe/scripts/tool_registry_check.py docs/tool-registry.json \
  --out .runtime/validation/tool-registry-report.json \
  --md-out .runtime/validation/tool-registry-summary.md
nox -s tool_registry
```

The companion adaptive-backend surface is validated separately:

```bash
python3 skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py \
  docs/adaptive-backend-evaluation.json
nox -s adaptive_backend_surface
```

The validator treats stale `last_checked` values as warnings by default. Use
`--fail-on-stale` when preparing a dependency change or a paid remote run.

The validator also checks that adopted optional packages appear in the declared
`pyproject.toml` extra, that declared Nox lanes exist, that remote-compute lane
manifests exist, and that the BoFire route reasons match the adapter constants.
