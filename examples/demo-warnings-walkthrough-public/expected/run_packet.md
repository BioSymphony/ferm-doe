# Diagnostic Walkthrough Run Packet

This is **not** a runnable packet. The campaign is intentionally underspecified.

## Why this exists

The other three demos (xylanase, scale-bridge, split-plot) all validate to YELLOW with `warning_count = 0`. That is correct behavior, but it does not show what the validator looks like when it has guidance to give.

This demo exists so a long-running agent can see, without breaking anything, what the failed-check ids and the worst-axis output look like before producing them in a real campaign.

## Expected validator output

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary
```

You should see `warning_count > 0`, `error_count == 0`, status `YELLOW`, and a populated `failed_check_ids` list.

## How to "pass" this demo

Fill in the missing fields in the manifest. The validator will tell you which ones in `failed_check_ids`. When all warnings are resolved, this demo will look like the other three.
