# Dossier Generation

`dossier_generate.py` creates a deterministic lightweight baseline `ferm-doe-dossier/` from a campaign manifest and CSV run ledger.

For the normal orchestrator, issue-tracker, remote-compute, or cloud success path, use `compile_ferm_doe_dossier.py` plus `dossier_check.py` and `ferm_doe_contract_self_check.py`. The lightweight generator is useful for legacy smoke tests and quick summaries. It does not produce the full contract proof artifacts.

## Demo Command

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py \
  --manifest examples/xylanase-wxz1-2012/campaign_manifest.json \
  --out ferm-doe-dossier \
  --run-budget 8

python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py ferm-doe-dossier
python3 skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py ferm-doe-dossier
```

Legacy lightweight command:

```bash
python3 skills/biosymphony-ferm-doe/scripts/dossier_generate.py \
  --manifest examples/xylanase-wxz1-2012/campaign_manifest.json \
  --ledger examples/xylanase-wxz1-2012/inputs/historical_run_ledger.csv \
  --output ferm-doe-dossier
```

If `--ledger` is omitted, the script uses the first ledger-like CSV input listed in the manifest.

## Outputs

The lightweight output directory contains:

- `data_trust_report.md`
- `factor_space_audit.md`
- `model_summary.md`
- `provenance.md`
- `readiness_verdict.md`

The generator reports run count, objective response, best observed run, best observed response, trust status, and readiness status. It does not fit a predictive model or produce lab-execution recommendations.

## Determinism

The Markdown output avoids timestamps and environment-specific randomness. Re-running the command with the same manifest, ledger, and output path should produce identical file content.
