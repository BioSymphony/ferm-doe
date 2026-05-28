# Diagnostic Walkthrough Handoff

This demo is intentionally incomplete. Do not try to "fix" the manifest unless you intend to demonstrate a clean run; the diagnostic value is in the warnings themselves.

When resuming, run:

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary
```

Inspect `failed_check_ids` and `worst_axis`. Each entry corresponds to a real validator branch you can reach in your own campaigns.
