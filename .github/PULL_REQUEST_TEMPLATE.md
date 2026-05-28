## What changed

One-line summary.

## Why

The user-visible problem this PR solves. Link issues / discussions.

## Public-safety checklist

- [ ] No private strain details, sequences, customer data, or confidential formulations.
- [ ] No API keys, tokens, or credentials.
- [ ] No private workstation paths or private issue/team identifiers.
- [ ] Synthetic / public-source rows are clearly labeled.
- [ ] `make release-check` passes.
- [ ] `make secret-scan` passes (or gracefully reports gitleaks not installed).

## Validator / schema impact

- [ ] No schema change.
- [ ] Schema change is backwards-compatible (adds optional fields only).
- [ ] Schema change is breaking; `CHANGELOG.md` updated under a clearly-labeled breaking-changes section.

## Demo impact

- [ ] No demo changes.
- [ ] Existing demos still validate to expected verdicts.
- [ ] New demo added under `examples/demo-<name>-public/`.

## Long-running agent impact

- [ ] No agent-facing change.
- [ ] `SKILL.md` / `agents/*.md` updated where the loop, refuse-vs-warn, or hand-off behavior changes.
