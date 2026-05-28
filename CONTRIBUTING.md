# Contributing

Thanks for helping improve `biosymphony-ferm-doe`.

## Ground rules

- Public-safe synthetic / public-source examples only. No private strain details, customer records, unpublished sequences, or confidential formulations.
- Label synthetic rows clearly (`source_type: synthetic_demo` etc.).
- Preserve non-claims: this project is for pre-experiment planning unless executed result rows are ingested with provenance. See [`NON_CLAIMS.md`](NON_CLAIMS.md).
- Prefer small, auditable artifacts over large opaque reports.
- Validator philosophy is **guidance, not gating**. Most checks should emit warnings; reserve errors for structural or public-safety failures.

## Local checks

```bash
make help                   # list every common target with a one-line summary
make release-check          # tests + demos + contract-check + tool-registry + audit + public-release scan
make public-ready           # release-check + required gitleaks history/tree scan
make secret-scan-optional   # best-effort local diagnostic when gitleaks may be absent
make show-warnings          # see what the diagnostic walkthrough surfaces
```

The dependency-free `release-check` catches structural and public-safety blockers. `public-ready` is the sharing gate; it fails if `gitleaks` is missing.

## Adding a new profile

1. Open a `[profile]` issue using the `new_profile` template.
2. Once direction is agreed:
   - Add the profile entry to `src/biosymphony_ferm_doe/profiles.py` under `PROFILE_REGISTRY`. Required fields: `description`, `advised_inputs`, `advised_expected`, `advised_blocks`, `required_blocks`, `advised_doe_families`. Profile-specific structural flags as needed.
   - Add the profile name to the JSON Schema enum at `schemas/campaign_manifest.schema.json` → `properties.profiles.items.enum`.
   - Add a snippet under `templates/profiles/<name>.snippet.json`.
   - Add a row to `docs/PROFILES.md`.
3. If structural validation differs from the existing profiles, update `src/biosymphony_ferm_doe/validators.py` accordingly. Default to warnings.
4. Optionally ship `examples/demo-<name>-public/` with synthetic data illustrating the profile.
5. `make release-check` must stay green.

## Adding a new DoE family

1. Open a `[family]` issue using the `new_doe_family` template.
2. Once direction is agreed:
   - Add the family entry to `src/biosymphony_ferm_doe/doe_families.py` under `FAMILY_REGISTRY` with `description`, `min_runs_formula`, supports/requires flags, and `typical_use`.
   - If the formula is computable in closed form, extend `minimum_runs(...)`.
   - Add the family name to the JSON Schema enum at `schemas/campaign_manifest.schema.json` → `$defs.doe.properties.family.enum`.
   - Add a section to `docs/DOE_FAMILIES.md`.
3. If new structural fields are needed (e.g. `n_blocks`, `whole_plot_count`), add them to `$defs.doe` in the schema and to the `_validate_doe(...)` function.
4. Add a unit test in `tests/test_validators.py` exercising the family's structural requirements.

## Writing a public-safe demo

1. Create `examples/demo-<name>-public/`.
2. Use synthetic numerical values. If anchored to a public paper, cite by DOI in `inputs/evidence_table.csv` (citation metadata only; do not paste article text).
3. Required files:
   - `campaign_manifest.json`
   - `inputs/historical_run_ledger.csv`, `inputs/evidence_table.csv`
   - `expected/readiness_summary.json`, `expected/AGENTS.md`
   - `README.md` describing scope and verdict
4. Set `claim_level: public_synthetic_demo` and `system.privacy: synthetic_or_public_only`.
5. Verdict should be `YELLOW` or `RED`. Forced `GREEN` on a synthetic demo is dishonest.
6. Run `make release-check`; the demo should validate with `error_count == 0`.

## Public-safety patterns

- The `audit` command catches private paths, secret-like values, and forbidden file names. Add `# audit-skip: <reason>` to a documentation example line that legitimately matches a pattern.
- The `make secret-scan` target requires `gitleaks`; `make secret-scan-optional` is only for best-effort local diagnostics.
- If a contribution requires a new `claim_level` value, propose it in the issue first. `claim_level` is a provenance label, not a sanitization control; public examples should still use synthetic or public-source rows.

## Pull request checklist

The `PULL_REQUEST_TEMPLATE.md` has the full checklist; the high points:

- `make release-check` passes
- public-safety items confirmed
- schema changes are backwards-compatible (optional fields), or breaking changes are flagged in `CHANGELOG.md`
- demos still validate to expected verdicts
- `SKILL.md` / `agents/*.md` updated when refuse-vs-warn behavior changes

## Style

- Stdlib only at runtime. The JSON Schema is for consumers; do not add a runtime dep on `jsonschema`.
- One short docstring per module / function maximum. No multi-paragraph docstrings, no decorative line wrapping in comments.
- Keep validator severities consistent: warnings for absence and for advisory shortfalls; errors for contradictions and public-safety violations.
