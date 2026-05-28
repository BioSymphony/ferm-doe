# Self-Learning DoE Runbook

Self-learning in the public scaffold means disciplined memory, not autonomous physical-execution control. The planner records what happened, what was excluded, what should not be repeated, and what needs review before the next experiment round.

## Artifacts

`ferm-doe plan-wave2` writes three learning artifacts:

- `learning_ledger.csv`: structured events an agent can carry forward.
- `hiccup_review.md`: human-readable review notes.
- `negative_result_memory.json`: arm-scoped regions that should not be repeated by default.

## Learning Ledger Fields

| Field | Purpose |
|---|---|
| `learning_id` | Stable row id. |
| `scope` | `campaign`, `arm`, `results`, `responses`, or `wave2`. |
| `event_type` | `monitor`, `hiccup`, `assay_power`, `decision`, or a user-defined type. |
| `trigger` | Why the event exists. |
| `observation` | What happened. |
| `action_taken` | What the agent or scientist did next. |
| `status` | `open`, `monitoring`, `closed`, or user-defined. |
| `owner_role` | Human or agent role responsible for closeout. |
| `follow_up_ref` | Artifact or issue reference. |

## Hiccup Policy

Record a hiccup when:

- First-batch rows fail QC or are excluded.
- Trust scores are low.
- assay-power policy is missing or weak.
- a requested scale or downscale move lacks bridge eligibility.
- a recommendation is `pause` or `stop`.
- the agent changes factor space because the best row is on a boundary.

Do not convert a hiccup into a hard failure automatically. The public lane should remain versatile: a scientist may decide to confirm, narrow, expand, pause, stop, or branch depending on goals and practical constraints.

## Negative Memory

Negative memory is arm-scoped by default. A bad plate condition should not automatically block reactor planning unless a bridge policy explicitly says the signal transfers.

Recommended policy:

```json
{
  "adaptive_wave2": {
    "self_learning": {
      "enabled": true,
      "negative_memory_scope": "arm",
      "learning_ledger_path": "wave2/learning_ledger.csv",
      "hiccup_review_path": "wave2/hiccup_review.md",
      "closeout_rule": "Every open hiccup must either be closed with evidence or carried into the later campaign manifest."
    }
  }
}
```

## Agent Loop

1. Run `ferm-doe validate`.
2. Run `ferm-doe plan-wave2` after first-batch results exist.
3. Read `result_ingestion_report.json` and `assay_power_results.json`.
4. Review `wave2_recommendation.md`.
5. Update or accept `wave2_manifest.patch.json`.
6. Carry `learning_ledger.csv` and `negative_result_memory.json` into the next planning wave.

The learning setup is designed for handoff. A later agent should be able to tell which decisions were evidence-backed, which were caveated, and which need human review.
