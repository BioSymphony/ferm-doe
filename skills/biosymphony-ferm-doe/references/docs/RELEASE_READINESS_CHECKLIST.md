# Release Readiness Checklist

Use this checklist before a public switch, public handoff, or public-facing demo. It is intentionally local-first: passing this checklist means the checkout is ready for review, not that anything has been pushed or published.

## 1. First-Run Surface

- [ ] README banner, workflow image, and agent-loop image render.
- [ ] README quickstart runs from a fresh checkout.
- [ ] [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) has a copy-paste prompt that keeps work local by default.
- [ ] [`USE_CASES.md`](USE_CASES.md) maps newcomer jobs to examples.
- [ ] [`examples/README.md`](../examples/README.md) names the first command for every public fixture.

## 2. Public-Safe Claims

- [ ] Public examples use `claim_level: public_synthetic_demo` or another explicit public-safe claim label.
- [ ] Synthetic rows and public-source rows are labeled in inputs and evidence tables.
- [ ] Handoff-like files say they are planning artifacts unless separate execution evidence exists.
- [ ] README, docs, and generated artifacts avoid claims such as optimized, validated, production-ready, or GxP-ready unless the claim is explicitly negated.
- [ ] Lab-facing wording uses pre-experiment planning, lab work, handoff packet, and physical execution language.

## 3. Newcomer Demo Loop

Run the fastest closed-loop path:

```bash
ferm-doe validate examples/demo-pb-screening-public --summary
ferm-doe generate-design examples/demo-pb-screening-public \
  --out /tmp/demo-pb/wave1_design.csv \
  --metadata-out /tmp/demo-pb/wave1_design.metadata.json \
  --seed 0
ferm-doe analyze examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/wave1_analysis.json \
  --md-out /tmp/demo-pb/wave1_analysis.md \
  --seed 0
ferm-doe plan-wave2 examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out-dir /tmp/demo-pb/wave2 \
  --remaining-budget 3
ferm-doe finalize examples/demo-pb-screening-public \
  --results examples/demo-pb-screening-public/inputs/wave1_results.csv \
  --out /tmp/demo-pb/run_packet.md \
  --json-out /tmp/demo-pb/run_packet.json
```

Expected result: commands complete locally, generated artifacts carry claim levels, and no command requires credentials or cloud access.

## 4. Release Gates

Run the public-ready target:

```bash
make public-ready
```

`make public-ready` requires `gitleaks`. If it is not installed, the gate fails closed; install it or use CI before public sharing. The secret scan covers both history and the current working tree.

For an explicit full-tree audit:

```bash
PYTHONPATH=src python -m biosymphony_ferm_doe.public_release --json .
ferm-doe audit .
python scripts/check_markdown_links.py .
git diff --check
```

Expected result:

- `make release-check` passes.
- Every top-level public example has `error_count == 0`.
- `ferm-doe audit .` reports `PASS`.
- The public release scanner reports zero findings.
- Local Markdown links resolve.
- `git diff --check` is clean.

## 5. Remote Decision

Before any actual public switch, decide:

- [ ] Public remote URL and repository visibility.
- [ ] Initial release tag and changelog entry.
- [ ] Whether package publishing is in scope now or later.
- [ ] Whether generated social preview and README images are final enough for public launch.
- [ ] Who owns issue triage and private vulnerability reporting after launch.

If the project is staying local, stop after the local gates. Do not push as a cleanup step.
